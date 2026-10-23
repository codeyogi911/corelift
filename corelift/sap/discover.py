"""Turn read-only ADT answers into a CoreLift inventory (schema 1.0.0).

One application per customer repository object with code (program, class,
interface, function module). Customer tables become extension-owned datasets.
Dependencies come from the same lexical scan the engine re-runs, so declared
and observed access always agree; anything the scan cannot resolve stays an
engine unknown. Source text is data: it is stored and scanned, never executed.
"""
import re

from ..engine import scan_abap
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
        for match in STATIC_CALL.finditer(_code_only(text)):
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
            "transaction_coupled": bool(COUPLING.search(_code_only(text))) or writes_standard,
            "wrapper": False, "coverage_complete": not unresolved,
            "depends_on": depends_on, "datasets": datasets, "dependencies": dependencies, "abap": text})
        found = program_screens(name, _code_only(text))
        screens += found
        if found:
            screen_startup[name] = startup(_code_only(text), any(s["id"] == f"{name}_1000" for s in found))
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


def program_screens(name, code):
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
    if fields and not any(s["id"] == f"{name}_1000" for s in screens):
        screens.append({"id": f"{name}_1000", "application_id": name, "technology": "Dynpro", **behavior,
                        "pbo": [f"selection screen field {f}" for f in fields] + behavior["pbo"]})
    return screens


# Statements that open a new processing block in a report or module pool.
BLOCK = re.compile(r"^\s*(LOAD-OF-PROGRAM|INITIALIZATION|START-OF-SELECTION|END-OF-SELECTION|TOP-OF-PAGE(?:\s+DURING\s+LINE-SELECTION)?"
                   r"|END-OF-PAGE|AT\s+SELECTION-SCREEN(?:\s+OUTPUT|\s+ON\s+[\w-]+(?:\s+[\w-]+)?)?|AT\s+LINE-SELECTION|AT\s+USER-COMMAND"
                   r"|AT\s+PF\d+|FORM\s+[\w/]+|MODULE\s+\w+\s+(?:INPUT|OUTPUT)|CLASS\s+[\w/]+\s+(?:DEFINITION|IMPLEMENTATION)"
                   r"|FUNCTION\s+[\w/]+)\b", re.I)
BLOCK_END = re.compile(r"^\s*(ENDFORM|ENDMODULE|ENDCLASS|ENDFUNCTION)\b", re.I)
PERFORM = re.compile(r"\bPERFORM\s+([\w/]+)", re.I)
CHANGES = [(re.compile(r"\bCOMMIT\s+WORK\b", re.I), "COMMIT WORK"),
           (re.compile(r"\bIN\s+UPDATE\s+TASK\b", re.I), "IN UPDATE TASK"),
           (re.compile(r"\bCALL\s+TRANSACTION\s+'?([\w/]+)", re.I), "CALL TRANSACTION {}"),
           (re.compile(r"\bSUBMIT\s+([\w/]+)", re.I), "SUBMIT {}")]
CALLS = [(re.compile(r"\bCALL\s+FUNCTION\s+'([\w/]+)'", re.I), "CALL FUNCTION {}"),
         (re.compile(r"\bCALL\s+METHOD\s+([\w/=>-]+)", re.I), "CALL METHOD {}"),
         (re.compile(r"(?<![\w/])([\w/]+(?:=>|->)[\w/]+)\s*\(", re.I), "{}")]


def _blocks(code):
    """(block name, lines) in source order; code before any event is START-OF-SELECTION."""
    blocks, name, lines = [], "START-OF-SELECTION", []
    for line in code.splitlines():
        start = BLOCK.match(line)
        if start or BLOCK_END.match(line):
            blocks.append((name, lines))
            name = " ".join(start[1].upper().split()) if start else "START-OF-SELECTION"
            lines = []
            continue
        lines.append(line)
    blocks.append((name, lines))
    return blocks


def startup(code, has_selection_screen):
    """What runs when a user opens this program's transaction, and what it may change.

    Opening runs LOAD-OF-PROGRAM, INITIALIZATION, AT SELECTION-SCREEN OUTPUT and
    the PBO modules, plus the FORMs they PERFORM. A report without a selection
    screen runs START-OF-SELECTION straight away. Verdict: display-only, unclear
    (it calls code this scan cannot see into) or changes-data.
    """
    blocks = _blocks(code)
    forms = {}
    for name, lines in blocks:
        if name.startswith("FORM "):
            forms.setdefault(name, []).extend(lines)
    opening = {"LOAD-OF-PROGRAM", "INITIALIZATION", "AT SELECTION-SCREEN OUTPUT"}
    if not has_selection_screen:
        opening.add("START-OF-SELECTION")
    runs = [(n, l) for n, l in blocks if n in opening or (n.startswith("MODULE ") and n.endswith(" OUTPUT"))]
    seen = {n for n, _ in runs}
    queue = list(runs)
    while queue:
        for form in PERFORM.findall("\n".join(queue.pop()[1])):
            name = f"FORM {form.upper()}"
            if name in forms and name not in seen:
                seen.add(name)
                runs.append((name, forms[name]))
                queue.append((name, forms[name]))
    text = "\n".join(line for _, lines in runs for line in lines)
    changes = sorted({_statement(text, f["object"]) for f in scan_abap(text) if f["kind"] == "write"})
    changes += sorted({label.format(m[1].upper()) if m.groups() else label for pattern, label in CHANGES for m in pattern.finditer(text)})
    calls = sorted({label.format(m[1].upper()) for pattern, label in CALLS for m in pattern.finditer(text)
                    if not m[1].upper().startswith(("ENQUEUE_", "DEQUEUE_"))})
    verdict = "changes-data" if changes else "unclear" if calls else "display-only"
    return {"runs_on_open": sorted({n for n, _ in runs if n != "START-OF-SELECTION" or not has_selection_screen}),
            "effects": changes + calls, "verdict": verdict}


def _statement(text, table):
    """The verb that writes to a table, e.g. UPDATE ZDEMO_NOTES."""
    match = re.search(rf"\b(INSERT|UPDATE|MODIFY|DELETE)\b[^.]*?\b{re.escape(table)}\b", text, re.I)
    return f"{match[1].upper() if match else 'WRITE'} {table}"


def _code_only(text):
    # Drop full-line comments and trailing quote comments before regex hints.
    return "\n".join("" if line.startswith("*") else line.split('"', 1)[0] for line in text.splitlines())
