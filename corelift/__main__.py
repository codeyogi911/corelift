import argparse
import json
import sys
import stat
from pathlib import Path

from .capabilities import require_capability
from .contracts import ROOT, ContractError
from .engine import assess
from .rehearsal import rehearsal_demo


def render(result):
    lines = ["# CoreLift assessment", "", "SYNTHETIC DEMO — no customer system connected." if result["synthetic"] else "Offline export assessment — recommendations require review.",
             "", f"Current source: {result['source_system']['family']} / {result['source_system']['edition']} / {result['source_system']['release']} / {result['source_system']['fps']}",
             f"Future target: {result['target']['family']} / {result['target']['edition']} / {result['target']['release']} / {result['target']['fps']}",
             "", "ERP core remains ERP. Every recommendation is unapproved; migration is not executable.", ""]
    for d in result["decisions"]:
        lines += [f"## {d['application_id']}: {d['disposition']}", "", d["reason"], "",
                  f"Clean-core dependency level candidate: {d['clean_core_level_candidate']} (not certification).",
                  f"Screens: {', '.join(d['screen_ids']) or 'none exported'}", ""]
        for label in ("unknowns", "risks"):
            for detail in d[label]:
                lines.append(f"- {label[:-1].title()}: {detail}")
        lines.append("")
        for dep in d["dependencies"]:
            uses = ', '.join(f"{u['application_id']}:{u['kind']}/{u['operation']}" for u in dep['uses'])
            lines.append(f"- {dep['object']}: effective state {dep['state']}; exported claim {dep['claimed_state']}; verification {dep['verification']}; contract {dep['contract']}; effective remote pathway {dep['remote_pathway']}; uses {uses}; source {dep['source_id'] or 'missing'}")
        for a in d["alternatives"]:
            lines.append(f"- Alternative: {a['option']} — {a['status']}; {a['risk']} [{a['source_id']}]")
        lines.append("")
    lines += ["## Screen behavior reconstruction", ""]
    for screen in result["screen_plan"]:
        lines += [f"- {screen['id']} ({screen['technology']}): BTP behavior rebuild required: {screen['rebuild_required_for_btp']}; {screen['status']}."]
        lines.extend(f"  - {key}: {', '.join(screen[key]) or 'no behavior evidence exported'}" for key in ("pbo", "pai", "validation", "authorization", "value_help", "locking", "errors"))
    lines += ["", "## Data and cutover", ""]
    for data in result["migration_plan"]["data"]:
        lines += [f"- {data['dataset_id']}: {data['classification']}; owner {data['owner']}; ownership {data['ownership']}; system of record {data['system_of_record']}; {data['transfer_decision']}.",
                  f"  - Used by: {', '.join(data['used_by'])}; extension candidates: {', '.join(data['extension_candidates']) or 'none'}. ERP-owned data stays authoritative; reference cache is not a core migration."]
        lines.extend(f"  - {a}" for a in data["required_actions"] + data["unknowns"])
    lines += ["", "## Stage gates", ""]
    lines.extend(f"- {s['id']}: {s['status']}; approval required: {s['approval_required']}; {s['purpose']}" for s in result["migration_plan"]["stages"])
    lines += ["", "## Evidence", ""]
    lines.extend(f"- [{s['title']}]({s['url']}) — {s['id']}; checked {s['checked_at']}; revision {s['revision']}" for s in result["sources"])
    lines += ["", "## Run record", "", "```json", json.dumps(result["run_record"], indent=2, sort_keys=True), "```", ""]
    return "\n".join(lines)


def read_json(path):
    # Explicit local JSON files only: neither URL fetching nor source execution.
    path = Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ContractError("input must be a regular local JSON file")
    with path.open("rb") as source:
        data = source.read(5_000_001)
    if len(data) > 5_000_000:
        raise ContractError("input exceeds 5 MB prototype limit")
    return json.loads(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description="CoreLift offline SAP clean-core assessment")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("rehearse-demo", help="Reconcile two fake notes in an in-memory mock and verify rollback")
    demo = sub.add_parser("demo", help="Assess bundled synthetic ECC export")
    real = sub.add_parser("assess", help="Assess explicitly supplied normalized local exports")
    for arg in ("inventory", "evidence", "sources"):
        real.add_argument(f"--{arg}", required=True)
    for command in (demo, real):
        command.add_argument("--output", help="Create a NEW local report folder (never overwrite)")
        command.add_argument("--format", choices=("markdown", "json"), default="markdown")
    connect = sub.add_parser("connect", help="Connect your SAP system (the only setup step)")
    connect.add_argument("--url", help="SAP system URL, e.g. https://sap.example.com:44300")
    connect.add_argument("--client", default=None, help="SAP client (Mandant), e.g. 100")
    connect.add_argument("--user")
    connect.add_argument("--ca-file", default="", help="Company CA bundle for TLS")
    connect.add_argument("--insecure-skip-tls-verify", action="store_true")
    connect.add_argument("--demo", action="store_true", help="Use the fictional demo system")
    sub.add_parser("disconnect", help="Forget the saved SAP connection")
    sub.add_parser("status", help="Show and test the SAP connection")
    lift = sub.add_parser("lift", help="Discover, assess and plan migration of custom code into a workspace")
    lift.add_argument("--workspace", required=True)
    lift.add_argument("--package", action="append", default=[])
    lift.add_argument("--query")
    lift.add_argument("--target-edition", default="private", choices=("private", "on-premise", "public"))
    lift.add_argument("--target-release", default="2025")
    lift.add_argument("--target-fps", default="FPS01")
    lift.add_argument("--commit", help="Pin a Cloudification Repository commit")
    sub.add_parser("mcp", help="Serve the CoreLift SAP tools over MCP stdio")
    args = parser.parse_args(argv)
    if args.command in ("connect", "disconnect", "status", "lift", "mcp"):
        from .sap.cli import run
        return run(args)
    try:
        if args.command == "rehearse-demo":
            print(json.dumps(rehearsal_demo(), indent=2, sort_keys=True))
            return 0
        require_capability("offline-assess")
        if args.command == "demo":
            inventory = read_json(ROOT / "examples" / "synthetic-ecc" / "inventory.json")
            evidence = read_json(ROOT / "examples" / "synthetic-ecc" / "api-evidence.json")
            sources = read_json(ROOT / "evidence" / "sources.json")
        else:
            inventory, evidence, sources = [read_json(getattr(args, name)) for name in ("inventory", "evidence", "sources")]
        result = assess(inventory, evidence, sources)
        if args.output:
            destination = Path(args.output)
            destination.mkdir(parents=False, exist_ok=False)
            (destination / "assessment.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            (destination / "assessment.md").write_text(render(result))
            if args.command == "demo":
                (destination / "rehearsal.json").write_text(json.dumps(rehearsal_demo(), indent=2, sort_keys=True) + "\n")
            print(f"Created {destination.resolve()}/assessment.md and assessment.json")
        else:
            print(json.dumps(result, indent=2, sort_keys=True) if args.format == "json" else render(result))
    except (ContractError, OSError, ValueError) as error:
        print(f"CoreLift: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
