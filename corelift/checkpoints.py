"""Checkpoint loop for shifting one application, with evidence gates.

An agent shifts an application in small checkpoints. Each checkpoint passes
its gates in order: behavior (tests), screen review against the reference
screenshots (only for checkpoints that touch screens), two independent
reviews, then approval by the user or a delegation the user gave. Every gate
records a fingerprint of the application's target/ code and of the plan, so
a later change makes earlier evidence stale. A gate that a missing tool
blocks stays visible: the checkpoint closes as unverified, never as passed.

This ledger is local bookkeeping in the workspace that keeps agents honest
about their own evidence. It is not tamper-proof and it runs nothing.
"""
import hashlib
import json
import re
from datetime import datetime, timezone

from .contracts import ContractError
from .sap.pipeline import open_workspace, slug

GATES = ("behavior", "screen-review", "review-a", "review-b", "approval")
VERDICTS = ("pass", "fail", "blocked")
# Gates a missing tool may block; reviews and approval always need a pass.
BLOCKABLE = {"behavior", "screen-review"}
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
LOOP = "LOOP.json"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _app_folder(ws, application):
    apps = {a["id"] for a in json.loads((ws / "inventory.json").read_text())["applications"]} if (ws / "inventory.json").is_file() else set()
    if application not in apps:
        raise ContractError(f"{application} is not an application in this workspace")
    return ws / "migration" / slug(application)


def _load(ws, application):
    path = _app_folder(ws, application) / LOOP
    if not path.is_file():
        raise ContractError(f"{application} has no checkpoint plan; call corelift_checkpoint_plan first")
    return json.loads(path.read_text())


def _save(ws, application, loop):
    folder = _app_folder(ws, application)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / LOOP).write_text(json.dumps(loop, indent=2, sort_keys=True) + "\n")


def fingerprint(ws, application, checkpoint):
    """SHA-256 over the checkpoint's goal and every file under target/."""
    digest = hashlib.sha256(json.dumps([checkpoint["id"], checkpoint["goal"], checkpoint["screens"]]).encode())
    target = _app_folder(ws, application) / "target"
    for path in sorted(p for p in target.rglob("*") if p.is_file()) if target.is_dir() else []:
        digest.update(path.relative_to(target).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def plan(workspace, application, checkpoints, builder="builder"):
    """Write or revise the ordered checkpoints; closed checkpoints stay as they were."""
    ws = open_workspace(workspace)
    folder = _app_folder(ws, application)
    old = json.loads((folder / LOOP).read_text()) if (folder / LOOP).is_file() else {"checkpoints": []}
    closed = {c["id"]: c for c in old["checkpoints"] if c["status"] != "open"}
    revised = []
    for item in checkpoints:
        cid, goal = str(item.get("id", "")), str(item.get("goal", "")).strip()
        if not ID.fullmatch(cid) or not goal:
            raise ContractError("each checkpoint needs a short lowercase id and a goal of a few words")
        if cid in closed:
            revised.append(closed.pop(cid))
            continue
        revised.append({"id": cid, "goal": goal[:200], "screens": bool(item.get("screens")), "status": "open", "gates": {}})
    if closed:
        raise ContractError(f"closed checkpoints cannot be dropped: {', '.join(closed)}")
    if len({c["id"] for c in revised}) != len(revised):
        raise ContractError("checkpoint ids must be unique")
    loop = {"application": application, "builder": builder, "checkpoints": revised}
    _save(ws, application, loop)
    return loop


def _required(checkpoint):
    return [g for g in GATES if g != "screen-review" or checkpoint["screens"]]


def _current(ws, application, checkpoint):
    """Gates recorded on the code as it is now, by name."""
    now = fingerprint(ws, application, checkpoint)
    return {name: g for name, g in checkpoint["gates"].items() if g["fingerprint"] == now}


def _delegated(ws, application):
    path = ws / "delegation.json"
    return path.is_file() and application in json.loads(path.read_text())["applications"]


def gate(workspace, application, checkpoint_id, name, verdict, by, evidence):
    """Record one gate verdict for an open checkpoint."""
    ws = open_workspace(workspace)
    loop = _load(ws, application)
    checkpoint = next((c for c in loop["checkpoints"] if c["id"] == checkpoint_id), None)
    if checkpoint is None or checkpoint["status"] != "open":
        raise ContractError(f"{checkpoint_id} is not an open checkpoint of {application}")
    required = _required(checkpoint)
    if name not in required or verdict not in VERDICTS:
        raise ContractError(f"gate must be one of {', '.join(required)} and verdict one of {', '.join(VERDICTS)}")
    by, evidence = str(by).strip(), str(evidence).strip()
    if not by or not evidence:
        raise ContractError("a gate needs who decided (by) and the evidence")
    if verdict == "blocked" and name not in BLOCKABLE:
        raise ContractError(f"{name} cannot be blocked; it needs a pass or a fail")
    current = _current(ws, application, checkpoint)
    earlier = required[:required.index(name)]
    waiting = [g for g in earlier if g not in current or current[g]["verdict"] == "fail"]
    if waiting:
        raise ContractError(f"{name} comes after {', '.join(waiting)}; pass those on the current code first")
    if name.startswith("review-"):
        other = current.get("review-b" if name == "review-a" else "review-a")
        if by == loop["builder"] or (other and other["by"] == by):
            raise ContractError("reviews need two reviewers other than the builder, each in a fresh context")
    if name == "approval" and not (by == "user" or (by == "delegated" and _delegated(ws, application))):
        raise ContractError("approval is by the user, or 'delegated' after the user delegated this application")
    checkpoint["gates"][name] = {"verdict": verdict, "by": by, "evidence": evidence[:2000],
                                 "fingerprint": fingerprint(ws, application, checkpoint), "at": _now()}
    # A new verdict on an earlier gate invalidates every later one.
    for later in required[required.index(name) + 1:]:
        checkpoint["gates"].pop(later, None)
    _save(ws, application, loop)
    return {"checkpoint": checkpoint_id, "gate": name, "verdict": verdict}


def close(workspace, application, checkpoint_id):
    """Close a checkpoint whose gates all hold on the current code."""
    ws = open_workspace(workspace)
    loop = _load(ws, application)
    checkpoint = next((c for c in loop["checkpoints"] if c["id"] == checkpoint_id and c["status"] == "open"), None)
    if checkpoint is None:
        raise ContractError(f"{checkpoint_id} is not an open checkpoint of {application}")
    current = _current(ws, application, checkpoint)
    stale = [g for g in checkpoint["gates"] if g not in current]
    missing = [g for g in _required(checkpoint) if g not in current or current[g]["verdict"] == "fail"]
    if stale or missing:
        raise ContractError("cannot close " + checkpoint_id + ": "
                            + "; ".join(filter(None, [f"stale after a code change: {', '.join(stale)}" if stale else "",
                                                      f"needs a pass: {', '.join(missing)}" if missing else ""])))
    blocked = [g for g in _required(checkpoint) if current[g]["verdict"] == "blocked"]
    checkpoint.update(status="closed-unverified" if blocked else "closed", closed_at=_now(),
                      fingerprint=fingerprint(ws, application, checkpoint))
    _save(ws, application, loop)
    following = next((c["id"] for c in loop["checkpoints"] if c["status"] == "open"), None)
    return {"checkpoint": checkpoint_id, "status": checkpoint["status"], "blocked": blocked, "next": following}


def delegate(workspace, applications, statement):
    """Record the user's words handing approval of these applications to the agents."""
    ws = open_workspace(workspace)
    for application in applications:
        _app_folder(ws, application)
    if not str(statement).strip():
        raise ContractError("record the user's own words for a delegation")
    value = {"applications": sorted(set(applications)), "statement": str(statement)[:1000], "recorded_at": _now()}
    (ws / "delegation.json").write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return value


def lesson(workspace, text, application=None):
    """Append an accepted lesson that later checkpoints and apps read first."""
    ws = open_workspace(workspace)
    if application is not None:
        _app_folder(ws, application)
    text = " ".join(str(text).split())[:500]
    if not text:
        raise ContractError("a lesson needs text")
    path = ws / "LESSONS.md"
    if not path.is_file():
        path.write_text("# Lessons\n\nAccepted corrections from earlier checkpoints. Apply them before building.\n\n")
    with path.open("a") as handle:
        handle.write(f"- {text}" + (f" ({application})" if application else "") + "\n")
    return {"lessons": str(path)}


def status(workspace):
    """Every planned checkpoint by application, for the hand-off summary."""
    ws = open_workspace(workspace)
    found = {}
    for path in sorted((ws / "migration").glob(f"*/{LOOP}")):
        loop = json.loads(path.read_text())
        found[loop["application"]] = [{"id": c["id"], "goal": c["goal"], "status": c["status"],
                                       "gates": {g: v["verdict"] for g, v in c["gates"].items()}} for c in loop["checkpoints"]]
    return found
