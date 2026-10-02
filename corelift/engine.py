"""Pure assessment functions. No network, subprocesses, or customer writes."""
import hashlib
import json
import re

from . import __version__
from .contracts import ContractError, contract, unique

RANK = {"released": "A", "classic": "B", "internal": "C", "not-recommended": "D"}
STAGES = [
    ("discover", "Review inventory coverage against ATC, usage, screen and interface exports"),
    ("assess", "Architect signs decisions against target-specific SAP evidence"),
    ("design", "Approve ERP boundary, API pathway, ownership and data minimization"),
    ("build", "Implement reviewed extension in an isolated development environment"),
    ("migrate-data", "Rehearse approved subset; reconcile keys, counts, totals and checksums"),
    ("deploy", "Deploy reviewed artifact with transport, identity and cost scope"),
    ("checkpoint", "Record artifact hashes, backup/restore proof and rollback decision"),
    ("cutover", "Freeze writes, capture delta, reconcile and obtain business-owner signoff"),
    ("verify", "Compare transactions, authorization, performance and data reconciliation"),
    ("rollback", "Restore approved checkpoint; reconcile deltas and verify ERP consistency"),
]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def scan_abap(text):
    """Small lexical heuristic; never execute source, comments or embedded prompts.

    Strings are preserved as spaces except static CALL FUNCTION operands. This
    catches common exports, not ABAP grammar, dynamic calls, macros or SQL aliases.
    """
    findings = []
    clean_lines = []
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("*"):
            clean_lines.append("")
            continue
        clean = []
        i = 0
        while i < len(line):
            if line[i] == '"':
                break
            if line[i] in "'`|":
                quote = line[i]
                start = i
                i += 1
                while i < len(line):
                    if line[i] == quote:
                        if quote != "|" and i + 1 < len(line) and line[i+1] == quote:
                            i += 2
                            continue
                        i += 1
                        break
                    i += 1
                literal = line[start:i]
                if quote == "'" and re.search(r"\bCALL\s+FUNCTION\s*$", "".join(clean), re.I):
                    clean.append(literal)
                else:
                    clean.append(" " * len(literal))
            else:
                clean.append(line[i])
                i += 1
        code = "".join(clean).upper()
        clean_lines.append(code)
        for kind, pattern in [
            ("read", r"\bFROM\s+([A-Z_][A-Z0-9_/]*)"),
            ("write", r"\b(?:UPDATE|MODIFY|INSERT(?:\s+INTO)?|DELETE(?:\s+FROM)?)\s+([A-Z_][A-Z0-9_/]*)"),
            ("call", r"\bCALL\s+FUNCTION\s+'([A-Z0-9_/]+)'"),
        ]:
            for match in re.finditer(pattern, code):
                findings.append({"kind": kind, "object": match[1], "line": line_no})
    all_code = "\n".join(clean_lines)
    for pattern in (r"\bCALL\s+FUNCTION\s+(?!')[A-Z_(]",
                    r"\bCALL\s+METHOD\b",  # conservative: method dispatch needs a real parser
                    r"\bPERFORM\s*\(",
                    r"\b[A-Z_]\w*\s*(?:=>|->)\s*\("):
        for match in re.finditer(pattern, all_code):
            findings.append({"kind": "dynamic-call", "object": "UNKNOWN",
                             "line": all_code[:match.start()].count("\n") + 1})
    return sorted({(f['line'], f['kind'], f['object']): f for f in findings}.values(), key=lambda f: (f['line'], f['kind'], f['object']))


def assess(inventory, evidence, sources):
    contract("inventory", inventory)
    contract("api-evidence", evidence)
    contract("sources", sources)
    apps = {a["id"]: a for a in inventory["applications"]}
    unique(inventory["applications"], "application")
    unique(inventory["screens"], "screen")
    unique(inventory["datasets"], "dataset")
    unique(sources["sources"], "source")
    known_sources = {s["id"] for s in sources["sources"]}
    datasets = {d["id"]: d for d in inventory["datasets"]}
    for app in apps.values():
        if any(ref not in apps for ref in app["depends_on"]):
            raise ContractError(f"{app['id']}: dangling application dependency")
        if any(ref not in datasets for ref in app["datasets"]):
            raise ContractError(f"{app['id']}: dangling dataset reference")
    for screen in inventory["screens"]:
        if screen["application_id"] not in apps:
            raise ContractError(f"{screen['id']}: dangling screen application")
    records = {}
    for item in evidence["objects"]:
        if item["object"] in records:
            raise ContractError("duplicate API evidence object")
        if item["source_id"] not in known_sources:
            raise ContractError("API evidence has unknown source")
        records[item["object"]] = item
    if inventory["synthetic"] != evidence["synthetic"]:
        raise ContractError("synthetic evidence cannot assess customer inventory")
    target_match = inventory["target"] == evidence["target"]
    snapshot_pinned = inventory["synthetic"] or bool(re.fullmatch(r"[0-9a-f]{40}", evidence["snapshot_revision"]))
    for item in evidence["objects"]:
        if (item["verification"] == "synthetic") != evidence["synthetic"]:
            raise ContractError("evidence verification does not match synthetic flag")
    decisions = []
    for app in sorted(apps.values(), key=lambda a: a["id"]):
        closure = set()
        pending = [app["id"]]
        while pending:
            app_id = pending.pop()
            if app_id in closure:
                continue
            closure.add(app_id)
            pending.extend(apps[app_id]["depends_on"])
        deps = {}
        unknowns = []
        signals = []
        for app_id in sorted(closure):
            member = apps[app_id]
            declared = {d["object"] for d in member["dependencies"]}
            for dep in member["dependencies"]:
                deps.setdefault(dep["object"], []).append({"application_id": app_id, **dep})
            for finding in scan_abap(member["abap"]):
                signals.append({"application_id": app_id, **finding})
                if finding["kind"] == "dynamic-call" or finding["object"] not in declared:
                    unknowns.append(f"{app_id}: heuristic {finding['kind']} {finding['object']} on line {finding['line']} requires export/ATC confirmation")
                elif finding["kind"] in ("read", "write") and not any(
                    dep["object"] == finding["object"] and dep["kind"] == "table" and dep["operation"] == finding["kind"]
                    for dep in member["dependencies"]
                ):
                    unknowns.append(f"{app_id}: observed table {finding['kind']} {finding['object']} conflicts with declared access kind/operation")
                elif finding["kind"] == "call" and not any(
                    dep["object"] == finding["object"] and dep["kind"] in ("api", "custom") and dep["operation"] == "call"
                    for dep in member["dependencies"]
                ):
                    unknowns.append(f"{app_id}: observed call {finding['object']} conflicts with declared access kind/operation")
            if not member["coverage_complete"]:
                unknowns.append(f"{app_id}: dependency export coverage is incomplete")
        dependency_assessment = []
        for obj, uses in sorted(deps.items()):
            record = records.get(obj) if target_match and snapshot_pinned else None
            state = record["state"] if record else "unknown"
            if record and record["verification"] != "synthetic":
                state = "unknown"
                unknowns.append(f"{obj}: customer export claims require independent API/pathway verification; provider absent")
            if record and any(use["operation"] not in record["supported_operations"] for use in uses):
                state = "unknown"
                unknowns.append(f"{obj}: requested operation lacks capability evidence")
            if record and record["contract"] == "C2" and any(use["kind"] not in ("api", "custom") for use in uses):
                state = "unknown"
                unknowns.append(f"{obj}: remote API contract cannot endorse direct table/technology access")
            if any(signal["object"] == obj and signal["kind"] == "write" for signal in signals):
                state = "unknown"
                unknowns.append(f"{obj}: direct write hint requires ATC and transactional remediation review")
            if state == "unknown":
                unknowns.append(f"{obj}: no conclusive evidence for target edition/release")
            remote = record["remote_pathway"] if record else "unknown"
            if record and record["verification"] != "synthetic":
                remote = "unknown"
            if record and any(use["operation"] not in record["endorsed_operations"] for use in uses):
                remote = "unknown"
            dependency_assessment.append({"object": obj, "used_by": sorted({u['application_id'] for u in uses}),
                                          "state": state, "source_id": record["source_id"] if record else "",
                                          "claimed_state": record["state"] if record else "unknown",
                                          "verification": record["verification"] if record else "missing",
                                          "uses": uses, "remote_pathway": remote,
                                          "contract": record["contract"] if record else "unknown"})
        if not target_match:
            unknowns.append("Evidence target does not match inventory target; all API classifications withheld")
        if not snapshot_pinned:
            unknowns.append("Customer API evidence requires an immutable 40-character snapshot commit")
        if inventory["target"]["edition"] == "public" and any(d["state"] in ("classic", "internal", "not-recommended") for d in dependency_assessment):
            unknowns.append("Classic/internal exception is not a public-edition extension pathway")
        levels = [RANK[d["state"]] for d in dependency_assessment if d["state"] in RANK]
        level = max(levels) if levels and not unknowns else "unknown"
        if not levels and not unknowns:
            unknowns.append("No classified dependencies; clean-core level cannot be established")
        risks = []
        if any(d["state"] in ("internal", "not-recommended") for d in dependency_assessment):
            risks.append("Internal/not-recommended dependency requires remediation or documented risk acceptance")
        if app["wrapper"]:
            risks.append("Wrapper retains transitive dependency risk; it does not upgrade classification to A")
        if signals:
            risks.append("ABAP scan is a lexical hint; confirm full dependency and behavior coverage using SAP ATC")
        if app["role"] == "erp-core":
            disposition = "retain-core"
            reason = "ERP transactions and authoritative data remain in ERP; BTP extends the core"
        elif app["usage"] == "unused-confirmed" and not unknowns and not any(app["id"] in a["depends_on"] for a in apps.values()):
            disposition = "retire-candidate"
            reason = "Export marks unused with no incoming dependency; business owner must confirm retirement"
        elif unknowns:
            disposition = "investigate"
            reason = "Missing target-specific evidence or coverage prevents placement decision"
        elif level == "D":
            disposition = "rebuild-candidate"
            reason = "Not-recommended dependency requires redesign around a supported capability"
        elif level == "C":
            disposition = "retain-with-risk-review"
            reason = "Internal dependency: investigate successor or risk-reviewed on-stack exception"
        elif any(apps[x]["transaction_coupled"] for x in closure) or level == "B":
            disposition = "retain-on-stack-candidate"
            reason = "Transactional coupling/classic technology favors reviewed on-stack extension"
        elif all(d["remote_pathway"] == "endorsed" and d["contract"] == "C2" for d in dependency_assessment):
            disposition = "btp-sidecar-candidate"
            reason = "Released dependency and exported endorsed remote pathway permit sidecar design review"
        else:
            disposition = "retain-on-stack-candidate"
            reason = "Released local API does not establish remote BTP access; retain pending pathway review"
        if inventory["source_system"]["family"] == "ECC":
            risks.append("On-stack ABAP Cloud is unavailable in ECC; S/4 conversion is a separate workstream")
        target = inventory["target"]
        on_stack_cloud = target["family"] == "S4HANA" and target["edition"] in ("private", "on-premise") and int(target["release"]) >= 2022
        alternatives = [
            {"option": "Standard SAP replacement", "status": "requires-functional-coverage-review", "source_id": "sap-levels", "risk": "Business behavior and target availability must be confirmed"},
            {"option": "Released successor or key-user/developer extension", "status": "requires-target-verification", "source_id": "sap-levels", "risk": "Capability and edition parity must be proven"},
        ] if level in ("B", "C", "D", "unknown") else []
        if level in ("B", "C", "unknown") and target["edition"] != "public":
            alternatives.append({"option": "SAP-nominated classic successor / narrow reviewed wrapper", "status": "requires-target-verification", "source_id": "sap-api-enablement", "risk": "B-level dependency remains; owner, expiry, ATC/unit/auth/locking/transaction tests and replacement trigger required"})
        if level == "C" and target["edition"] != "public":
            alternatives.append({"option": "Governed internal-object retention with applicable changelog review", "status": "requires-risk-acceptance", "source_id": "sap-levels", "risk": "C-level stability risk; target-specific support, owner and expiry required"})
        decisions.append({"application_id": app["id"], "disposition": disposition, "reason": reason,
                          "clean_core_level_candidate": level, "unknowns": sorted(set(unknowns)),
                          "risks": risks, "dependencies": dependency_assessment, "signals": signals,
                          "transitive_applications": sorted(closure - {app["id"]}),
                          "screen_ids": sorted(s["id"] for s in inventory["screens"] if s["application_id"] == app["id"]),
                          "source_ids": ["sap-levels", "sap-cloudification"], "alternatives": alternatives,
                          "target_on_stack_abap_cloud_version_floor_met": on_stack_cloud,
                          "approval_state": "not-approved"})
    if not {"sap-levels", "sap-cloudification", "sap-api-enablement"} <= known_sources:
        raise ContractError("required policy evidence absent")
    data_plan = []
    for data in sorted(datasets.values(), key=lambda x: x["id"]):
        users = sorted(a["id"] for a in apps.values() if data["id"] in a["datasets"])
        move_candidates = [d["application_id"] for d in decisions if d["application_id"] in users and d["disposition"] in ("btp-sidecar-candidate", "rebuild-candidate")]
        data_plan.append({"dataset_id": data["id"], "classification": data["classification"],
                          "owner": data["owner"], "system_of_record": data["system_of_record"],
                          "ownership": data["ownership"],
                          "used_by": users, "extension_candidates": move_candidates,
                          "transfer_decision": "no-transfer-approved",
                          "required_actions": ["Owner approves minimal fields, purpose, retention and residency",
                                               "Keep ERP authoritative; separately evaluate extension-owned data versus reference cache",
                                               "Select supported extract/load pathway for target release",
                                               "Define keys, configurations, attachments, authorizations, currency, units and timezones",
                                               "Define referential integrity, counts, business totals, semantic checks and checksums",
                                               "Rehearse initial plus delta capture, rejects, idempotency, write freeze, cutover and rollback reconciliation"],
                          "unknowns": ["Field mapping, volume, retention/residency and reconciliation thresholds are unverified"] + (["Data owner unassigned"] if data["owner"] == "unknown" else [])})
    plan = {"state": "draft-not-executable", "stages": [
        {"id": stage, "purpose": purpose, "status": "pending-review" if stage in ("discover", "assess", "design") else "blocked-provider-not-implemented",
         "approval_required": stage not in ("discover", "assess"),
         "checkpoint_required": stage in ("migrate-data", "deploy", "cutover", "rollback"),
         "verification": "Evidence and business-owner review" if stage in ("discover", "assess", "design") else "Approved rehearsal and recorded verification results required"}
        for stage, purpose in STAGES], "data": data_plan}
    result = {"schema_version": "1.0.0", "synthetic": inventory["synthetic"], "engine_version": __version__,
              "source_system": inventory["source_system"],
              "target": inventory["target"], "decisions": decisions, "migration_plan": plan,
              "screen_plan": [{**s, "rebuild_required_for_btp": s["technology"] in ("Dynpro", "WebDynpro"),
                               "status": "behavior-export-requires-review"} for s in sorted(inventory["screens"], key=lambda x: x['id'])],
              "sources": sources["sources"], "run_record": {
                  "input_hashes": {"inventory": digest(inventory), "api_evidence": digest(evidence), "sources": digest(sources)},
                  "api_snapshot_revision": evidence["snapshot_revision"], "api_snapshot_target": evidence["target"],
                  "ruleset": "corelift-offline-0.1.0", "connector": "offline-exports",
                  "network_used": False, "customer_writes": False,
                  "limitations": ["Normalized exports only; no live discovery or connector verification",
                                  "Lexical ABAP hints are incomplete; ATC/usage/system export coverage required",
                                  "Classification candidates require technology and architect review",
                                  "Synthetic API records prove behavior, not SAP API availability"]}}
    contract("assessment", result)
    return result
