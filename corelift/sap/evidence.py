"""API evidence from SAP's public Cloudification Repository, pinned to a commit.

https://github.com/SAP/abap-atc-cr-cv-s4hc publishes which SAP objects are
released (objectReleaseInfo*) and which are classic APIs (objectClassifications_SAP).
CoreLift reads those files at one immutable commit and maps them to its
evidence contract. The files say nothing about remote (C2) contracts or
endorsed remote pathways, so both stay unknown and the engine never derives a
BTP sidecar from this evidence alone.
"""
import hashlib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from ..contracts import ContractError

REPO = "SAP/abap-atc-cr-cv-s4hc"
MAX_FILE = 80_000_000
RELEASE_STATE = {"released": "released", "deprecated": "classic",
                 "notToBeReleased": "internal", "notToBeReleasedStable": "internal"}
CLASSIC_STATE = {"classicAPI": "classic", "noAPI": "not-recommended"}
TABLE_TYPES = {"TABL", "VIEW", "DDLS", "STOB"}
RELEASED, UNLISTED = "released", "unlisted"  # successor states recorded in evidence notes


def files_for(target):
    """Candidate file names per needed file; the first one published wins.

    SAP publishes private-edition files per feature pack stack, e.g.
    objectReleaseInfo_PCE2025_1.json for 2025 FPS01 (2022 has no suffix).
    """
    if target["edition"] == "public":
        return [["src/objectReleaseInfoLatest.json"]]
    fps = re.search(r"\d+", target["fps"])
    release = [f"src/objectReleaseInfo_PCE{target['release']}_{int(fps[0])}.json"] if fps else []
    return [release + [f"src/objectReleaseInfo_PCE{target['release']}.json"], ["src/objectClassifications_SAP.json"]]


def _get(url, accept="*/*", limit=MAX_FILE):
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "git/2 CoreLift"})
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ContractError(f"{url}: exceeds size limit")
    return data


def resolve_commit(ref="main"):
    # Git smart-HTTP ref advertisement: no API token or rate limit needed.
    refs = _get(f"https://github.com/{REPO}.git/info/refs?service=git-upload-pack", limit=5_000_000).decode("latin-1")
    match = re.search(rf"([0-9a-f]{{40}}) refs/heads/{re.escape(ref)}\b", refs)
    if not match:
        raise ContractError("could not resolve an immutable Cloudification Repository commit")
    return match[1]


def fetch(target, destination, commit=None):
    """Download the target's files at one commit. Network: public GitHub only."""
    commit = commit or resolve_commit()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ContractError("commit must be a 40-character SHA")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    paths = []
    for candidates in files_for(target):
        for name in candidates:
            try:
                data = _get(f"https://raw.githubusercontent.com/{REPO}/{commit}/{name}")
                break
            except urllib.error.HTTPError as error:
                if error.code != 404:
                    raise
        else:
            raise ContractError(f"SAP publishes no Cloudification file for {target['edition']} {target['release']} {target['fps']} "
                                f"at {commit[:12]} (tried {', '.join(candidates)}); pick a published feature pack stack, e.g. 2025 FPS01")
        path = destination / Path(name).name
        path.write_bytes(data)
        paths.append(path)
    return commit, paths


def _records(path):
    data = path.read_bytes()
    if len(data) > MAX_FILE:
        raise ContractError(f"{path.name}: exceeds size limit")
    doc = json.loads(data)
    items = doc.get("objectReleaseInfo") or doc.get("objectClassifications") or []
    return items, hashlib.sha256(data).hexdigest()


def _release_record(released, name):
    """The first record for name in the target's release file with a state CoreLift maps, or None."""
    return next((item for item in released.get(str(name).upper(), []) if item.get("state") in RELEASE_STATE), None)


def _target_state(released, name):
    """SAP's state for a successor in the target's release file, so drafts need no second lookup."""
    record = _release_record(released, name)
    return record["state"] if record else UNLISTED


def build(inventory, files, commit):
    """Map inventory dependencies onto pinned repository records."""
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ContractError("commit must be a 40-character SHA")
    released, classic, hashes = {}, {}, {}
    for path in map(Path, files):
        items, hashes[path.name] = _records(path)
        table = released if "objectReleaseInfo" in path.name else classic
        for item in items:
            key = (item.get("objectKey") or item.get("tadirObjName") or "").upper()
            if key:
                table.setdefault(key, []).append(item)
    owned = {a["id"] for a in inventory["applications"]} | {d["id"] for d in inventory["datasets"]}
    wanted = {}
    for app in inventory["applications"]:
        for dep in app["dependencies"]:
            if dep["object"] not in owned and dep["kind"] != "custom":
                wanted.setdefault(dep["object"], set()).add(dep["kind"])
    objects, notes = [], {}
    for name in sorted(wanted):
        match = _release_record(released, name)
        state = RELEASE_STATE[match["state"]] if match else None
        if not match:
            for item in classic.get(name, []):
                if item.get("state") in CLASSIC_STATE:
                    match, state = item, CLASSIC_STATE[item["state"]]
                    break
        if not match:
            notes[name] = {"found": False, "note": "Not in the pinned Cloudification Repository files: unclassified (treat as internal until SAP or an architect says otherwise)"}
            continue
        successors = [s.get("objectKey") or s.get("tadirObjName") for s in match.get("successors", [])]
        is_data = match.get("objectType", match.get("tadirObject", "")) in TABLE_TYPES
        ops = ["read"] if is_data else ["call"]
        objects.append({"object": name, "state": state, "contract": "unknown", "remote_pathway": "unknown",
                        "source_id": "sap-cloudification", "verification": "cloudification-pinned",
                        "supported_operations": ops, "endorsed_operations": []})
        notes[name] = {"found": True, "sap_state": match.get("state"), "object_type": match.get("objectType"),
                       "application_component": match.get("applicationComponent", ""),
                       "successors": successors, "successor_states": {s: _target_state(released, s) for s in successors},
                       "successor_concept": match.get("successorConceptName", "")}
    evidence = {"schema_version": "1.0.0", "synthetic": False, "target": inventory["target"],
                "snapshot_revision": commit, "objects": objects}
    return evidence, {"repository": f"https://github.com/{REPO}", "commit": commit, "file_sha256": hashes, "objects": notes}
