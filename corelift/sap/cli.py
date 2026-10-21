"""Terminal commands for the SAP connection and lift pipeline."""
import getpass
import json
import os
import sys

from ..capabilities import CapabilityDenied, require_capability
from ..contracts import ContractError
from . import pipeline, profile
from .adt import ADTClient, ADTError


def _ask(label, default=""):
    value = input(f"{label}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def connect(args):
    if args.demo:
        path = profile.save(profile.DEMO, "DEMO", "demo")
        print(f"Connected to the fictional demo system. Saved {path}.")
        return 0
    saved = profile.load() or {}
    url = args.url or _ask("SAP system URL (https://host:port)", saved.get("url", ""))
    client = args.client if args.client is not None else _ask("SAP client (blank for default)", saved.get("client", ""))
    user = args.user or _ask("SAP user", saved.get("user", ""))
    password = os.environ.get("CORELIFT_SAP_PASSWORD") or getpass.getpass("SAP password (hidden): ")
    verify = not args.insecure_skip_tls_verify
    print("Checking the connection (read-only)...")
    connection = ADTClient(url, user, password, client, verify, args.ca_file or None)
    connection.ping()
    components = connection.components()
    path = profile.save(url, user, password, client, verify, args.ca_file)
    print(f"Connected to {url} as {user}. Components: {', '.join(f'{k} {v}' for k, v in sorted(components.items()))}")
    print(f"Saved to {path} (owner-only). Your coding agent can now lift your apps; it never sees the password.")
    return 0


def run(args):
    try:
        if args.command == "mcp":
            from ..mcp_server import serve
            serve()
            return 0
        if args.command == "connect":
            return connect(args)
        if args.command == "disconnect":
            print("Forgot the saved SAP connection." if profile.forget() else "No saved SAP connection.")
            return 0
        require_capability("sap-read")
        settings = profile.load()
        if args.command == "status":
            info = profile.public(settings)
            if settings:
                info["components"] = profile.client_for(settings).components()
            print(json.dumps(info, indent=2))
            return 0 if settings else 1
        require_capability("network-evidence")
        target = {"family": "S4HANA", "edition": args.target_edition, "release": args.target_release, "fps": args.target_fps}
        result = pipeline.lift(args.workspace, profile.client_for(settings), args.package, args.query, target, args.commit,
                               progress=lambda m: print(m, file=sys.stderr))
        print(json.dumps(result, indent=2))
        return 0
    except (ADTError, ContractError, CapabilityDenied, LookupError, PermissionError, OSError, ValueError) as error:
        print(f"CoreLift: {error}", file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.", file=sys.stderr)
        return 130
