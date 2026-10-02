"""Build contained, self-contained packages. No installation or publication."""
import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDED = ("corelift", "schemas", "evidence", "examples", "skills", "docs", "scripts")


def package_files(root):
    files = [root / "README.md", root / "requirements-dev.txt", root / "LICENSE", root / "NOTICE", root / "THIRD_PARTY.md"]
    for name in INCLUDED:
        base = root / name
        if base.is_symlink():
            raise ValueError(f"symlink package root: {name}")
        for p in base.rglob("*"):
            if p.is_symlink():
                raise ValueError(f"symlink refused: {p.relative_to(root)}")
            if not p.resolve().is_relative_to(root.resolve()):
                raise ValueError("package path escapes root")
            if p.is_file() and "__pycache__" not in p.parts:
                if p.suffix not in {".py", ".json", ".md", ".sha256"}:
                    raise ValueError(f"unexpected package file: {p.name}")
                if re.search(r"(?:BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{32,})", p.read_text()):
                    raise ValueError(f"possible credential in package: {p.name}")
                files.append(p)
    for p in files:
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):
            raise ValueError("package file escapes root")
        if re.search(r"(?:BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{32,})", p.read_text()):
            raise ValueError(f"possible credential in package: {p.name}")
    return sorted(files)


def build(destination, root=ROOT, with_ui=False):
    files = package_files(root)
    if (root / "plugin.json").is_symlink():
        raise ValueError("symlink manifest refused")
    ui_files = [root / "ui/generated/server.mjs", root / "ui/generated/preview.mjs", root / "ui/generated/workspace.html", root / "ui/codex-mcp.json", root / "ui/generated/THIRD_PARTY_NOTICES.txt", root / "ui/generated/bundle-licenses.json"] if with_ui else []
    for p in ui_files:
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root.resolve()):
            raise ValueError("build the contained UI artifacts before --with-ui")
    manifest = json.loads((root / "plugin.json").read_text())
    destination = Path(destination)
    if any(destination.resolve().is_relative_to((root / name).resolve()) for name in INCLUDED):
        raise ValueError("destination overlaps source")
    destination.mkdir(exist_ok=False)
    for host in ("codex", "cursor", "claude"):
        package = destination / host
        package.mkdir()
        for p in files:
            target = package / p.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
        if host == "codex":
            path, meta = package / "plugin.json", manifest
        else:
            path = package / f".{host}-plugin" / "plugin.json"
            meta = {key: manifest[key] for key in ("name", "version", "description", "author", "license", "homepage") if key in manifest}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, indent=2) + "\n")
        if host == "codex" and with_ui:
            for source in ui_files:
                target = package / ("mcp.json" if source.name == "codex-mcp.json" else source.relative_to(root))
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        (package / "README.md").write_text(
            f"# CoreLift — {host} local package\n\n"
            "Python 3.11+, offline only. From this package folder run:\n\n"
            "```sh\npython3 scripts/corelift.py demo\npython3 scripts/corelift.py rehearse-demo\n```\n\n"
            "Load `skills/assess-sap-clean-core/SKILL.md` through your host's supported local plugin workflow. "
            "No installation, hooks or marketplace entry is performed by this package. "
            "Host runtime loading has not been verified. Every decision is a draft; no SAP connection or BTP deployment exists.\n\n"
            "See `docs/input-contracts.md`, `docs/sap-decisions.md` and `docs/architecture.md` for scope and evidence. "
            "The source repository README provides the full development/test workflow. See LICENSE, NOTICE and THIRD_PARTY.md for licensing.\n")
        if host == "codex" and with_ui:
            with (package / "README.md").open("a") as readme:
                readme.write("\nThis optional package includes a real read-only stdio MCP workspace and root `mcp.json`. Requires Node 22+ and Python 3.11+. No npm install is needed in this built package. The server accepts empty input and serves a bundled UI resource. The public synthetic demo remains complete and includes guided fictional connection discovery. Run node ui/generated/preview.mjs for the separate local preview; real sign-in remains unavailable until a supported provider is bound. Imported reports withhold contents and counts unless separate startup consent enables exactly three aggregate counts; full details stay in the local CLI/preview. See docs/privacy-boundary.md. Codex global sidebar acceptance is unverified. See `docs/workspace.md` for scope and fallback.\n")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dist", help="NEW output folder")
    parser.add_argument("--with-ui", action="store_true", help="Include the built read-only MCP workspace in the Codex package only")
    args = parser.parse_args()
    try:
        print(f"Built local packages in {build(args.output, with_ui=args.with_ui).resolve()}")
    except (OSError, ValueError) as error:
        parser.exit(2, f"CoreLift packaging: {error}\n")
