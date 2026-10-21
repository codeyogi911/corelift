"""SAP connection settings: the one thing a user has to provide.

Resolution order: CORELIFT_SAP_* environment variables (Claude Code fills them
from the plugin's userConfig prompt), then the local connection file written by
`corelift connect`. The file lives in the user's home, never in a project, and
is created with owner-only permissions. Settings returned to agents never carry
the password.
"""
import json
import os
import stat
from pathlib import Path

from .adt import ADTClient

FIELDS = ("url", "client", "user", "password", "verify_tls", "ca_file")
DEMO = "demo"


class NotConnected(Exception):
    pass


def home():
    return Path(os.environ.get("CORELIFT_HOME") or Path.home() / ".corelift")


def connection_file():
    return home() / "connection.json"


def _env(name):
    value = os.environ.get(f"CORELIFT_SAP_{name.upper()}", "").strip()
    # Unfilled host placeholders such as "${user_config.sap_url}" mean unset.
    return "" if value.startswith("${") else value


def load():
    """Return settings dict or None. Environment wins over the saved file."""
    settings = {name: _env(name) for name in FIELDS}
    if settings["url"]:
        settings["source"] = "environment"
    else:
        path = connection_file()
        if not path.is_file():
            return None
        if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PermissionError(f"{path} must be readable by its owner only (chmod 600)")
        saved = json.loads(path.read_text())
        settings = {name: str(saved.get(name, "")) for name in FIELDS}
        settings["source"] = str(path)
    settings["verify_tls"] = str(settings.get("verify_tls", "")).lower() not in ("false", "0", "no")
    return settings


def save(url, user, password, client="", verify_tls=True, ca_file=""):
    path = connection_file()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = {"url": url, "client": client, "user": user, "password": password,
            "verify_tls": verify_tls, "ca_file": ca_file}
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(data, handle, indent=2)
    os.chmod(path, 0o600)
    return path


def forget():
    path = connection_file()
    if path.is_file():
        path.unlink()
        return True
    return False


def public(settings):
    """What an agent may see about the connection."""
    if not settings:
        return {"configured": False}
    return {"configured": True, "url": settings["url"], "client": settings["client"] or "(default)",
            "user": settings["user"], "verify_tls": settings["verify_tls"], "source": settings["source"],
            "demo": settings["url"] == DEMO}


def client_for(settings):
    if not settings:
        raise NotConnected("No SAP system connected. Run `corelift connect` (or set the plugin's SAP settings).")
    if settings["url"] == DEMO:
        from . import mock
        return ADTClient(mock.shared_demo_url(), mock.USER, mock.PASSWORD)
    if not settings["user"] or not settings["password"]:
        raise NotConnected("SAP user and password are required; run `corelift connect` again.")
    return ADTClient(settings["url"], settings["user"], settings["password"], settings["client"],
                     settings["verify_tls"], settings["ca_file"] or None)
