"""Validate the deliberately small subset used by CoreLift's versioned schemas.

This is not a general JSON Schema implementation. The development check also
validates all contracts using the reference jsonschema library.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ContractError(ValueError):
    pass


def validate(value, schema, path="$", definitions=None):
    definitions = definitions or schema.get("$defs", {})
    if "anyOf" in schema:
        for choice in schema["anyOf"]:
            try:
                validate(value, choice, path, definitions)
                return
            except ContractError:
                pass
        raise ContractError(f"{path}: no supported shape matched")
    if "$ref" in schema:
        return validate(value, definitions[schema["$ref"].split("/")[-1]], path, definitions)
    types = {"object": dict, "array": list, "string": str, "boolean": bool,
             "integer": int, "null": type(None)}
    expected = schema.get("type")
    if expected and (not isinstance(value, types[expected]) or
                     (expected == "integer" and isinstance(value, bool))):
        raise ContractError(f"{path}: expected {expected}")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path}: unsupported value {value!r}")
    if "const" in schema and (value != schema["const"] or
                              (isinstance(schema["const"], bool) and type(value) is not bool)):
        raise ContractError(f"{path}: expected {schema['const']!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0) or len(value) > schema.get("maxLength", 1000000):
            raise ContractError(f"{path}: invalid string length")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            raise ContractError(f"{path}: invalid format")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", 100000):
            raise ContractError(f"{path}: invalid item count")
        if schema.get("uniqueItems") and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            raise ContractError(f"{path}: duplicate items")
        for i, item in enumerate(value):
            validate(item, schema.get("items", {}), f"{path}[{i}]", definitions)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                raise ContractError(f"{path}: missing {key}")
        if schema.get("additionalProperties") is False:
            extra = value.keys() - props.keys()
            if extra:
                raise ContractError(f"{path}: unexpected fields {sorted(extra)}")
        for key, item in value.items():
            if key in props:
                validate(item, props[key], f"{path}.{key}", definitions)


def contract(name, value):
    schema = json.loads((ROOT / "schemas" / f"{name}.schema.json").read_text())
    validate(value, schema)


def unique(records, label):
    ids = [x["id"] for x in records]
    if len(ids) != len(set(ids)):
        raise ContractError(f"duplicate {label} IDs")
