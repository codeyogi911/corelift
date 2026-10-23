"""Turn read-only ADT answers into a CoreLift inventory (schema 1.0.0).

One application per customer repository object with code (program, class,
interface, function module). Customer tables become extension-owned datasets.
Dependencies come from the same lexical scan the engine re-runs, so declared
and observed access always agree; anything the scan cannot resolve stays an
engine unknown. Source text is data: it is stored and scanned, never executed.
"""
import re

from ..engine import clean_abap, scan_abap
from .adt import SOURCE_TYPES, ADTError

# Z/Y names are customer code. Namespaced /XYZ/ objects can be SAP's or the
# customer's, so they count as customer code only when the user scoped them in.
CUSTOMER = re.compile(r"^[ZY]", re.I)
DB_TABLE_TYPES = {"TABL/DT", "TABL/DS", "TABL"}
DEFAULT_TARGET = {"family": "S4HANA", "edition": "private", "release": "2025", "fps": "FPS01"}
STATIC_CALL = re.compile(r"(?<![A-Z0-9_/])((?:/[A-Z0-9_]+/)?(?:CL|IF)_[A-Z0-9_]+)\s*=>", re.I)
COUPLING = re.compile(r"\b(?:CALL\s+SCREEN|CALL\s+TRANSACTION|LEAVE\s+TO\s+TRANSACTION|SET\s+SCREEN|MODULE\s+\w+\s+(?:INPUT|OUTPUT))\b", re.I)
SCREEN = re.compile(r"\bCALL\s+SCREEN\s+(\d+)", re.I)
TRANSACTION_TYPES = {"TRAN/T", "TRAN"}
# Screen behavior hints. Flow logic and layout are not readable over this
# connector, so module names, checks and messages are program-wide hints.
MODULE = re.compile(r"^\s*MODULE\s+(\w+)\s+(INPUT|OUTPUT)\s*\.", re.I | re.M)
AUTHORITY = re.compile(r"\bAUTHORITY-CHECK\s+OBJECT\s+'([A-Z0-9_/]+)'", re.I)
MESSAGE = re.compile(r"\bMESSAGE\s+([EWAX]\d{3}\([A-Z0-9_/]+\))", re.I)
LOCK = re.compile(r"\bCALL\s+FUNCTION\s+'(ENQUEUE_[A-Z0-9_/]+)'", re.I)
SELECTION = re.compile(r"^\s*(?:PARAMETERS|SELECT-OPTIONS)\s*:?\s*([A-Z][A-Z0-9_]*)", re.I | re.M)
MAX_ABAP = 500_000

# Software component releases -> S/4HANA release year. Unknown stays unknown.
S4CORE = {"100": "1511", "101": "1610", "102": "1709", "103": "1809", "104": "1909",
          "105": "2020", "106": "2021", "107": "2022", "108": "2023", "109": "2025"}
SAP_APPL = {"600": "2005", "602": "2007", "603": "2008", "604": "2008", "605": "2010",
            "606": "2011", "616": "2012", "617": "2013", "618": "2016"}


def source_system(components, override=None):
    if override:
        return override
    if "S4CORE" in components:
        return {"family": "S4HANA", "edition": "on-premise", "release": S4CORE.get(components["S4CORE"], "0000"),
                "fps": f"S4CORE {components['S4CORE']}"}
    if "SAP_APPL" in components:
        return {"family": "ECC", "edition": "on-premise", "release": SAP_APPL.get(components["SAP_APPL"], "0000"),
                "fps": f"SAP_APPL {components['SAP_APPL']}"}
    return {"family": "ECC", "edition": "on-premise", "release": "0000", "fps": "unknown (no SAP_APPL/S4CORE reported)"}


def collect(client, packages=(), query=None, max_objects=500):
    """Repository objects in scope, de-duplicated by (type, name)."""
    found = {}
    for package in packages:
        for node in client.package_contents(package.upper()):
            found[(node["type"], node["name"].upper())] = node
    if query or not packages:
        for pattern in ([query] if query else ["Z*", "Y*"]):
            for node in client.search(pattern, max_results=max_objects):
                if query or CUSTOMER.match(node["name"]):
                    found[(node["type"], node["name"].upper())] = node
    objects = list(found.values())
    objects.sort(key=lambda o: (o["name"].upper(), o["type"]))
    if len(objects) > max_objects:
        raise ADTError(f"{len(objects)} objects in scope exceed max_objects={max_objects}; narrow the packages or query")
    return objects


def discover(client, packages=(), query=None, target=None, source_override=None, max_objects=500, progress=None):
    components = client.components()
    source = source_system(components, source_override)
    objects = collect(client, packages, query, max_objects)
    tables = sorted({o["name"].upper() for o in objects if o["type"] in DB_TABLE_TYPES})
    code = [o for o in objects if o["type"] in SOURCE_TYPES]
    transactions = [{"name": o["name"].upper(), "description": o["description"]} for o in objects if o["type"] in TRANSACTION_TYPES]
    skipped = [{"name": o["name"], "type": o["type"], "reason": "object type not read by this connector"}
               for o in objects if o["type"] not in SOURCE_TYPES | DB_TABLE_TYPES | TRANSACTION_TYPES]
    sources, failures = {}, []
    for index, obj in enumerate(code, 1):
        if obj["name"].upper() in sources:
            failures.append({"name": obj["name"], "type": obj["type"], "reason": "same name as another object in scope; read once"})
            continue
        if progress:
            progress(f"reading {obj['name']} ({index}/{len(code)})")
        try:
            text = client.source(obj["uri"])
        except ADTError as error:
            failures.append({"name": obj["name"], "type": obj["type"], "reason": str(error)})
            continue
        sources[obj["name"].upper()] = text[:MAX_ABAP]
    owned = set(sources) | set(tables)
    applications, screens, screen_startup = [], [], {}
    seen = set()
    for obj in code:
        name = obj["name"].upper()
        if name not in sources or name in seen:
            continue
        seen.add(name)
        text = sources[name]
        deps, unresolved = {}, False
        for finding in scan_abap(text):
            if finding["kind"] == "dynamic-call":
                continue
            target_obj, op = finding["object"], finding["kind"]
            if op in ("read", "write"):
                kind = "table"
            elif target_obj in owned:
                kind = "custom"
            elif CUSTOMER.match(target_obj):
                kind, unresolved = "custom", True
            else:
                kind = "api"
            deps[(target_obj, kind, op)] = {"object": target_obj, "kind": kind, "operation": op}
            if op in ("read", "write") and CUSTOMER.match(target_obj) and target_obj not in owned:
                unresolved = True
        code = _code_only(text)
        for match in STATIC_CALL.finditer(code):
            ref = match[1].upper()
            kind = "custom" if CUSTOMER.match(ref) else "api"
            unresolved = unresolved or (kind == "custom" and ref not in owned)
            deps[(ref, kind, "call")] = {"object": ref, "kind": kind, "operation": "call"}
        dependencies = sorted(deps.values(), key=lambda d: (d["object"], d["kind"], d["operation"]))
        depends_on = sorted({d["object"] for d in dependencies if d["kind"] == "custom" and d["object"] in sources and d["object"] != name})
        datasets = sorted({d["object"] for d in dependencies if d["object"] in tables})
        writes_standard = any(d["operation"] == "write" and not CUSTOMER.match(d["object"]) for d in dependencies)
        applications.append({
            "id": name, "title": (obj["description"] or name)[:1000], "role": "extension", "usage": "unknown",
            "transaction_coupled": bool(COUPLING.search(code)) or writes_standard,
            "wrapper": False, "coverage_complete": not unresolved,
            "depends_on": depends_on, "datasets": datasets, "dependencies": dependencies, "abap": text})
        found = program_screens(name, code, has_selection_screen(text))
        screens += found
        if found:
            screen_startup[name] = startup(text)
    if not applications:
        raise ADTError("no customer code found in scope; check packages/query and display authorizations")
    inventory = {
        "schema_version": "1.0.0", "synthetic": False, "source_system": source,
        "target": target or dict(DEFAULT_TARGET),
        "applications": applications, "screens": screens,
        "datasets": [{"id": t, "classification": "unknown", "owner": "unknown",
                      "system_of_record": "source SAP system", "ownership": "extension"} for t in tables]}
    record = {"components": components, "packages": [p.upper() for p in packages], "query": query,
              "objects_in_scope": len(objects), "applications": len(applications), "tables": tables,
              "transactions": transactions, "screen_startup": screen_startup,
              "skipped": skipped, "read_failures": failures,
              "limitations": ["Usage statistics (SCMON/SUSG), ATC results, screen layouts, flow logic and DDIC details are not read by this connector yet",
                              "Screen behavior (modules, authorization objects, messages, locks) is a program-wide lexical hint, not per-screen flow logic",
                              "Dependencies are lexical hints from source; confirm with SAP ATC before decisions"]}
    return inventory, sources, record


def program_screens(name, code, selection_screen):
    """Dynpro screens one program calls, plus its selection screen 1000."""
    def unique(pattern, group=1):
        return sorted({m[group].upper() for m in pattern.finditer(code)})
    modules = [(m[1].upper(), m[2].upper()) for m in MODULE.finditer(code)]
    behavior = {"pbo": sorted({n for n, kind in modules if kind == "OUTPUT"}),
                "pai": sorted({n for n, kind in modules if kind == "INPUT"}),
                "validation": [f"MESSAGE {m}" for m in unique(MESSAGE)],
                "authorization": unique(AUTHORITY), "value_help": [], "locking": unique(LOCK), "errors": []}
    screens = [{"id": f"{name}_{number}", "application_id": name, "technology": "Dynpro", **behavior}
               for number in sorted(set(SCREEN.findall(code)), key=int)]
    fields = unique(SELECTION)
    if selection_screen and not any(s["id"] == f"{name}_1000" for s in screens):
        screens.append({"id": f"{name}_1000", "application_id": name, "technology": "Dynpro", **behavior,
                        "pbo": [f"selection screen field {f}" for f in fields] + behavior["pbo"]})
    return screens


# Statements that open a new processing block in a report or module pool.
BLOCK = re.compile(r"(LOAD-OF-PROGRAM|INITIALIZATION|START-OF-SELECTION|END-OF-SELECTION|TOP-OF-PAGE(?: DURING LINE-SELECTION)?"
                   r"|END-OF-PAGE|AT SELECTION-SCREEN(?: OUTPUT| ON .+)?|AT LINE-SELECTION|AT USER-COMMAND|AT PF\d+"
                   r"|FORM ([\w/]+).*|MODULE (\w+) (?:INPUT|OUTPUT).*|CLASS [\w/]+ (?:DEFINITION|IMPLEMENTATION).*|FUNCTION [\w/]+.*)")
BLOCK_END = re.compile(r"(ENDFORM|ENDMODULE|ENDCLASS|ENDFUNCTION)\b.*")
OPENING = {"LOAD-OF-PROGRAM", "INITIALIZATION", "AT SELECTION-SCREEN OUTPUT"}
WRITE = re.compile(r"(INSERT|UPDATE|MODIFY|DELETE)\s+(?:FROM\s+|INTO\s+)?(?:TABLE\s+)?(<?[\w/]+>?)")
CHANGES = [(re.compile(r"\bCOMMIT\s+WORK\b"), "COMMIT WORK"),
           (re.compile(r"\bIN\s+UPDATE\s+TASK\b"), "IN UPDATE TASK"),
           (re.compile(r"\bCALL\s+TRANSACTION\b"), "CALL TRANSACTION"),
           (re.compile(r"^SUBMIT\b"), "SUBMIT"),
           (re.compile(r"\bEXPORT\b.*\bTO\s+DATABASE\b"), "EXPORT TO DATABASE"),
           (re.compile(r"\bOPEN\s+DATASET\b.*\bFOR\s+(?:OUTPUT|APPENDING|UPDATE)\b"), "OPEN DATASET FOR OUTPUT"),
           (re.compile(r"^DELETE\s+DATASET\b"), "DELETE DATASET")]
# Code this scan cannot see into: the verdict is unclear, never display-only.
OPAQUE = [(re.compile(r"\bCALL\s+FUNCTION\s+'([\w/]+)'"), "CALL FUNCTION {}"),
          (re.compile(r"\bCALL\s+FUNCTION\s+(?!')"), "CALL FUNCTION (dynamic)"),
          (re.compile(r"\bCALL\s+METHOD\s+([\w/=>()-]+)"), "CALL METHOD {}"),
          (re.compile(r"([\w/]+\s*(?:=>|->)\s*[\w/]+)\s*\("), "{}"),
          (re.compile(r"\bNEW\s+([\w/]+)\s*\("), "NEW {}"),
          (re.compile(r"^CREATE\s+OBJECT\b"), "CREATE OBJECT"),
          (re.compile(r"^INCLUDE\s+([\w/]+)"), "INCLUDE {}"),
          (re.compile(r"^PERFORM\s+.*\bIN\s+PROGRAM\b"), "PERFORM IN PROGRAM"),
          (re.compile(r"^PERFORM\s*\("), "PERFORM (dynamic)")]


def statements(text):
    """ABAP statements from clean source, with chains (A: b, c.) expanded."""
    found = []
    for raw in " ".join(clean_abap(text)).split("."):
        statement = " ".join(raw.split())
        if ":" in statement:
            head, rest = statement.split(":", 1)
            found += [f"{head.strip()} {part.strip()}".strip() for part in rest.split(",")]
        elif statement:
            found.append(statement)
    return found


def has_selection_screen(text):
    """PARAMETERS or SELECT-OPTIONS a user sees (NO-DISPLAY ones do not count)."""
    return any(re.match(r"(PARAMETERS|SELECT-OPTIONS)\b", s) and "NO-DISPLAY" not in s for s in statements(text))


def _blocks(stmts):
    """(block name, statements) in order; code before any event is START-OF-SELECTION."""
    blocks, name, body = [], "START-OF-SELECTION", []
    for statement in stmts:
        start = BLOCK.fullmatch(statement)
        if start or BLOCK_END.fullmatch(statement):
            blocks.append((name, body))
            if not start:
                name = "START-OF-SELECTION"
            elif start[2]:
                name = f"FORM {start[2]}"
            elif start[3]:
                name = f"MODULE {start[3]} {'OUTPUT' if ' OUTPUT' in statement else 'INPUT'}"
            else:
                name = start[1]
            body = []
            continue
        body.append(statement)
    blocks.append((name, body))
    return blocks


def startup(text):
    """What runs when a user opens this program's transaction, and what it may change.

    Opening runs LOAD-OF-PROGRAM, INITIALIZATION, AT SELECTION-SCREEN OUTPUT and
    the PBO modules, plus the FORMs they PERFORM. A report without a visible
    selection screen runs START-OF-SELECTION straight away. Verdict:
    changes-data (a database write, commit, update task, file write or another
    program started), unclear (calls or includes code this scan cannot see
    into) or display-only. A transaction that skips its first screen or starts
    with a variant runs more than this; the scan cannot know that.
    """
    stmts = statements(text)
    blocks = _blocks(stmts)
    declared = {m[1] for s in stmts for m in [re.match(r"(?:DATA|STATICS|CONSTANTS|RANGES)\s+([\w/]+)", s)] if m}
    declared |= {m for s in stmts for m in re.findall(r"\bDATA\(([\w/]+)\)", s)}
    forms = {}
    for name, body in blocks:
        if name.startswith("FORM "):
            forms.setdefault(name, []).extend(body)
    opening = OPENING | (set() if has_selection_screen(text) else {"START-OF-SELECTION"})
    runs = [(n, b) for n, b in blocks if n in opening or (n.startswith("MODULE ") and n.endswith(" OUTPUT"))]
    names = {n for n, _ in runs}
    opaque = set()
    queue = list(runs)
    while queue:
        for statement in queue.pop()[1]:
            called = re.match(r"PERFORM\s+([\w/]+)", statement)
            if not called or "IN PROGRAM" in statement:
                continue
            form = f"FORM {called[1]}"
            if form not in forms:
                opaque.add(f"PERFORM {called[1]} (not in this source)")
            elif form not in names:
                names.add(form)
                runs.append((form, forms[form]))
                queue.append((form, forms[form]))
    changes = set()
    for statement in (s for _, body in runs for s in body):
        write = WRITE.match(statement)
        if write and not write[2].startswith("<") and write[2] not in declared and "DATASET" not in statement:
            changes.add(f"{write[1]} {write[2]}")
        changes |= {label for pattern, label in CHANGES if pattern.search(statement)}
        opaque |= {label.format(m[1]) if m.groups() else label for pattern, label in OPAQUE for m in [pattern.search(statement)] if m}
    opaque = {o for o in opaque if not o.startswith(("CALL FUNCTION ENQUEUE_", "CALL FUNCTION DEQUEUE_"))}
    verdict = "changes-data" if changes else "unclear" if opaque else "display-only"
    return {"runs_on_open": sorted(names), "effects": sorted(changes) + sorted(opaque), "verdict": verdict}


def _code_only(text):
    """Source without comments, string literals kept (authorization objects, messages)."""
    return "\n".join(_strip_comment(line) for line in text.splitlines())


def _strip_comment(line):
    if line.startswith("*"):
        return ""
    quote = None
    for i, char in enumerate(line):
        if quote:
            quote = None if char == quote else quote
        elif char in "'`|":
            quote = char
        elif char == '"':
            return line[:i]
    return line
