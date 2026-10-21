"""Read-only SAP ABAP Development Tools (ADT) REST client.

The client is the only code that talks to a customer SAP system. It speaks the
same HTTP endpoints SAP's own Eclipse ADT uses, and it refuses every request
that is not on a small read-only allowlist. One allowlisted request is a POST
(the repository tree read needs it); it never carries a body that changes
the system. Credentials stay in this object and are never returned or logged.
"""
import base64
import http.cookiejar
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

MAX_RESPONSE = 5_000_000
NS = {"adtcore": "http://www.sap.com/adt/core", "atom": "http://www.w3.org/2005/Atom",
      "asx": "http://www.sap.com/abapxml", "app": "http://www.w3.org/2007/app"}

# (method, path pattern). Anything else is refused before a socket opens.
READ_ONLY = [
    ("GET", r"/sap/bc/adt/discovery"),
    ("GET", r"/sap/bc/adt/system/components"),
    ("GET", r"/sap/bc/adt/repository/informationsystem/search"),
    ("POST", r"/sap/bc/adt/repository/nodestructure"),
    ("GET", r"/sap/bc/adt/(?:programs/programs|programs/includes|oo/classes|oo/interfaces)/[^/]+/source/main"),
    ("GET", r"/sap/bc/adt/functions/groups/[^/]+/fmodules/[^/]+/source/main"),
    ("GET", r"/sap/bc/adt/functions/groups/[^/]+/includes/[^/]+/source/main"),
]

# ADT object types whose ABAP source CoreLift reads.
SOURCE_TYPES = {"PROG/P", "PROG/I", "CLAS/OC", "INTF/OI", "FUGR/FF", "FUGR/I"}


class ADTError(RuntimeError):
    pass


class ReadOnlyViolation(ADTError):
    pass


def allowed(method, path):
    if any(segment in (".", "..") for segment in path.split("/")):
        return False
    return any(method == m and re.fullmatch(p, path) for m, p in READ_ONLY)


class ADTClient:
    def __init__(self, url, user, password, client="", verify_tls=True, ca_file=None, timeout=30):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname:
            raise ADTError("SAP URL must be http(s)://host[:port]")
        if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ADTError("plain http is accepted only for loopback test systems; use https")
        self.base = f"{parsed.scheme}://{parsed.netloc}"
        self.client = client
        self.timeout = timeout
        self._auth = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self._csrf = None
        context = None
        if parsed.scheme == "https":
            context = ssl.create_default_context(cafile=ca_file)
            if not verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
            urllib.request.HTTPSHandler(context=context) if context else urllib.request.HTTPHandler(),
            _NoRedirect())

    def __repr__(self):
        return f"ADTClient({self.base!r}, client={self.client!r})"

    def request(self, method, path, query=None, accept="*/*"):
        if not allowed(method, path):
            raise ReadOnlyViolation(f"{method} {path} is not on the CoreLift read-only allowlist")
        query = dict(query or {})
        if self.client:
            query["sap-client"] = self.client
        url = self.base + urllib.parse.quote(path) + ("?" + urllib.parse.urlencode(query) if query else "")
        headers = {"Authorization": self._auth, "Accept": accept, "User-Agent": "CoreLift-readonly"}
        if method == "POST":
            headers["x-csrf-token"] = self._csrf or self._fetch_csrf()
        req = urllib.request.Request(url, method=method, headers=headers, data=b"" if method == "POST" else None)
        try:
            return self._send(req, path)
        except _StaleToken:
            # SAP session expired during a long lift: fetch a new token once.
            headers["x-csrf-token"] = self._fetch_csrf()
            return self._send(urllib.request.Request(url, method=method, headers=headers, data=b""), path)

    def _send(self, req, path):
        try:
            with self._opener.open(req, timeout=self.timeout) as response:
                body = response.read(MAX_RESPONSE + 1)
        except urllib.error.HTTPError as error:
            if error.code == 403 and req.get_method() == "POST" and error.headers.get("x-csrf-token", "").lower() == "required":
                raise _StaleToken() from None
            if error.code in (401, 403):
                raise ADTError(f"SAP refused the request ({error.code}); check user, password, client and ADT authorizations (S_ADT_RES, S_DEVELOP display)") from None
            if error.code == 404:
                raise ADTError(f"SAP has no ADT resource at {path} (404)") from None
            raise ADTError(f"SAP returned HTTP {error.code} for {path}") from None
        except (urllib.error.URLError, OSError) as error:
            raise ADTError(f"cannot reach SAP at {self.base}: {getattr(error, 'reason', error)}") from None
        if len(body) > MAX_RESPONSE:
            raise ADTError(f"{path}: response exceeds 5 MB limit")
        return body.decode("utf-8", errors="replace")

    def _fetch_csrf(self):
        query = "?" + urllib.parse.urlencode({"sap-client": self.client}) if self.client else ""
        req = urllib.request.Request(self.base + "/sap/bc/adt/discovery" + query,
                                     headers={"Authorization": self._auth, "x-csrf-token": "fetch", "Accept": "*/*"})
        try:
            with self._opener.open(req, timeout=self.timeout) as response:
                response.read(MAX_RESPONSE)
                self._csrf = response.headers.get("x-csrf-token", "")
        except (urllib.error.URLError, OSError) as error:
            raise ADTError(f"cannot fetch ADT session token: {getattr(error, 'reason', error)}") from None
        return self._csrf

    # High-level reads -----------------------------------------------------

    def ping(self):
        """Discovery document; proves URL, credentials and ADT service activation."""
        root = _xml(self.request("GET", "/sap/bc/adt/discovery", accept="application/atomsvc+xml"))
        return len(root.findall(".//app:collection", NS))

    def components(self):
        """Installed software components, e.g. {'SAP_BASIS': '758', 'S4CORE': '108'}."""
        root = _xml(self.request("GET", "/sap/bc/adt/system/components", accept="application/atom+xml;type=feed"))
        found = {}
        for entry in root.findall("atom:entry", NS):
            name = (entry.findtext("atom:id", "", NS) or "").strip()
            title = entry.findtext("atom:title", "", NS) or ""
            release = re.search(r"\b(\d{3,4})\b", title)
            if name:
                found[name] = release[1] if release else "unknown"
        return found

    def search(self, query, object_type=None, max_results=200):
        params = {"operation": "quickSearch", "query": query, "maxResults": str(max_results)}
        if object_type:
            params["objectType"] = object_type.split("/")[0]
        root = _xml(self.request("GET", "/sap/bc/adt/repository/informationsystem/search", params, "application/xml"))
        results = []
        for ref in root.iter(f"{{{NS['adtcore']}}}objectReference"):
            name = ref.get(f"{{{NS['adtcore']}}}name", "")
            name = re.sub(r"\s*\(.*\)$", "", name)
            results.append({"name": name, "type": ref.get(f"{{{NS['adtcore']}}}type", ""),
                            "uri": ref.get(f"{{{NS['adtcore']}}}uri", ""),
                            "package": ref.get(f"{{{NS['adtcore']}}}packageName", ""),
                            "description": ref.get(f"{{{NS['adtcore']}}}description", "")})
        return results

    def package_contents(self, package):
        params = {"parent_type": "DEVC/K", "parent_name": package, "withShortDescriptions": "true"}
        root = _xml(self.request("POST", "/sap/bc/adt/repository/nodestructure", params, "application/vnd.sap.as+xml"))
        nodes = []
        for node in root.iter("SEU_ADT_REPOSITORY_OBJ_NODE"):
            nodes.append({"name": (node.findtext("OBJECT_NAME") or "").strip(),
                          "type": (node.findtext("OBJECT_TYPE") or "").strip(),
                          "uri": (node.findtext("OBJECT_URI") or "").strip(),
                          "description": (node.findtext("DESCRIPTION") or "").strip(),
                          "package": package})
        return [n for n in nodes if n["name"] and n["type"]]

    def source(self, uri):
        path = urllib.parse.unquote(urllib.parse.urlsplit(uri).path).rstrip("/")
        if not path.endswith("/source/main"):
            path += "/source/main"
        return self.request("GET", path, accept="text/plain")


class _StaleToken(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # A redirect could move credentials to another host; fail instead.
    def redirect_request(self, *args, **kwargs):
        return None


def _xml(text):
    if "<!DOCTYPE" in text[:2000] or "<!ENTITY" in text[:2000]:
        raise ADTError("SAP response contained a DTD; refused")
    try:
        return ET.fromstring(text)
    except ET.ParseError as error:
        raise ADTError(f"SAP returned malformed XML: {error}") from None
