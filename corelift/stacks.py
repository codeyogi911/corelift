"""Target stacks: where side-by-side code goes, chosen with the user.

A stack is a Markdown profile, not engine code. CoreLift ships profiles under
skills/choose-target-stack/stacks/; a customer adds their own by dropping a
profile into the workspace's stacks/ folder. The engine only validates the
shape and copies the chosen profile into the workspace, where every brief and
reviewer reads it. Dispositions stay evidence-based whatever stack is chosen.
"""
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .contracts import ROOT, ContractError

SHIPPED = ROOT / "skills" / "choose-target-stack" / "stacks"
SECTIONS = ("When it fits", "Building blocks", "Calling SAP", "Tests", "Done when")
PLACEMENTS = ("side-by-side", "on-stack")
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
CHOICE = "target-stack.json"


def parse(path):
    text = path.read_text()
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise ContractError(f"{path.name}: stack profile needs front matter between --- lines")
    meta = dict(line.split(":", 1) for line in match[1].splitlines() if ":" in line)
    meta = {key.strip(): value.strip() for key, value in meta.items()}
    if not ID.fullmatch(meta.get("id", "")) or meta["id"] != path.stem:
        raise ContractError(f"{path.name}: id must be a short lowercase slug equal to the file name")
    if not meta.get("name"):
        raise ContractError(f"{path.name}: name missing")
    if meta.get("placement") not in PLACEMENTS:
        raise ContractError(f"{path.name}: placement must be one of {', '.join(PLACEMENTS)}")
    headings = re.findall(r"^## (.+?)\s*$", text, re.M)
    missing = [s for s in SECTIONS if s not in headings]
    if missing:
        raise ContractError(f"{path.name}: missing section(s) {', '.join(missing)}")
    return {"id": meta["id"], "name": meta["name"], "placement": meta["placement"],
            "default": meta.get("default") == "true", "path": path}


def profiles(workspace=None):
    """Shipped profiles plus the workspace's own stacks/*.md, by id."""
    found = {}
    folders = [SHIPPED] + ([Path(workspace) / "stacks"] if workspace else [])
    for folder in folders:
        for path in sorted(folder.glob("*.md")) if folder.is_dir() else []:
            profile = parse(path)
            if profile["id"] in found:
                raise ContractError(f"{path.name}: stack id {profile['id']} already exists; pick another id")
            found[profile["id"]] = profile
    return found


def default():
    return next(p for p in profiles().values() if p["default"])


def choose(workspace, stack_id):
    """Record the user's stack and copy its profile to <workspace>/target-stack.md."""
    from .sap.pipeline import open_workspace  # the pipeline imports this module
    ws = open_workspace(workspace)
    known = profiles(ws)
    if stack_id not in known:
        raise ContractError(f"unknown stack {stack_id!r}; known: {', '.join(sorted(known))}. "
                            "Add a profile to the workspace's stacks/ folder for a new one.")
    profile = known[stack_id]
    shutil.copyfile(profile["path"], ws / "target-stack.md")
    value = {"id": profile["id"], "name": profile["name"], "placement": profile["placement"],
             "chosen_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (ws / CHOICE).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return value


def chosen(workspace):
    """The recorded choice, or the default stack before the user has chosen."""
    path = Path(workspace) / CHOICE
    if path.is_file():
        return json.loads(path.read_text())
    profile = default()
    return {"id": profile["id"], "name": profile["name"], "placement": profile["placement"], "chosen_at": None}
