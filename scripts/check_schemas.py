"""Development-only standards/schema verification; pip install -r requirements-dev.txt."""
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from corelift.contracts import validate
from corelift.engine import assess
from corelift.workspace import snapshot


def load(p):
    return json.loads(p.read_text())


def main():
    inputs = {"inventory": load(ROOT / "examples/synthetic-ecc/inventory.json"),
              "api-evidence": load(ROOT / "examples/synthetic-ecc/api-evidence.json"),
              "sources": load(ROOT / "evidence/sources.json")}
    inputs["assessment"] = assess(inputs["inventory"], inputs["api-evidence"], inputs["sources"])
    inputs["workspace"] = snapshot()
    inputs["host-summary"] = {"host_summary_version": "1.0.0", "mode": "imported", "read_only": True, "disclosure": "withheld", "counts": None}
    for name, value in inputs.items():
        schema = load(ROOT / "schemas" / f"{name}.schema.json")
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
        validate(value, schema)
    for name in ("discovery-event", "discovery-state"):
        Draft202012Validator.check_schema(load(ROOT / "schemas" / f"{name}.schema.json"))
    Draft202012Validator(load(ROOT / "schemas/discovery-event.schema.json")).validate({"action": "create"})
    official = ROOT / "evidence/agent-plugins-1.0.0.schema.json"
    expected = (ROOT / "evidence/agent-plugins-1.0.0.sha256").read_text().strip()
    assert hashlib.sha256(official.read_bytes()).hexdigest() == expected, "official schema checksum changed"
    Draft202012Validator.check_schema(load(official))
    Draft202012Validator(load(official)).validate(load(ROOT / "plugin.json"))
    official_mcp = ROOT / "evidence/agent-plugins-1.0.0-mcp.schema.json"
    assert hashlib.sha256(official_mcp.read_bytes()).hexdigest() == official_mcp.with_suffix(".sha256").read_text().strip()
    Draft202012Validator.check_schema(load(official_mcp))
    Draft202012Validator(load(official_mcp)).validate(load(ROOT / "ui/codex-mcp.json"))
    print("PASS: six data contracts plus two discovery schemas, portable manifest and optional MCP config match JSON Schema 2020-12; official schema checksums verified")


if __name__ == "__main__":
    main()
