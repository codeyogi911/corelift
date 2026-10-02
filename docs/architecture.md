# Foundation and next boundary

`corelift/engine.py` is pure, deterministic shared logic. Versioned schemas cover inventory, API evidence, sources and assessment (including migration plan and run record). `__main__.py` handles explicit local reads and optional new-folder reports. `rehearsal.py` is a synthetic in-memory target for two extension-owned notes, with atomic load, replay, reference validation, rollback and locking. Neither module is a SAP connector.

Host packages contain identical engine/schema/evidence/fixture bytes and one shared skill. Codex uses the portable Agent Plugins root manifest; Cursor has a native skills-only adapter; Claude uses its own manifest. Packages are self-contained and have no global settings, marketplace entry, remote MCP declaration or hooks. The skill resolves its own package root, so installations need not share an absolute path. Codex local installation and installed-server protocol were verified; the user subsequently reported sidebar discovery. Resource/data/navigation behavior in the host remains a separate pending check. Claude/Cursor runtime invocation remains unverified.

`capabilities.py` allows offline assessment only. All other capabilities fail closed even when passed an approval object, because no external provider exists. Future reads need a capability allowlist, target/system identity, scoped authorization and local evidence handling. Future writes must use operation/artifact/system-bound approval, checkpoint, independent verification and rollback reconciliation inside the provider. Approval UI or optional hooks cannot enforce this by themselves. Approval states in the report are descriptive and cannot unlock execution.

Future connectors should ingest official ATC/custom-code/usage/interface exports first, then add narrowly supported system reads only after authorization. Next development should prove one genuine SAP API pathway in a test landscape, not general RFC/OData exploration. Before implementation, add version-aware functional capability evidence, standard replacement catalog, full screen/ABAP behavior extraction, and per-operation SAP pathway verification. Customer exports can contain secrets; no automated detector guarantees their absence. Keep them local, minimized and excluded from Git.

Plans cover discovery, assessment, design, build, data migration, deployment, checkpoint, cutover, verification and rollback. Later stages are visibly blocked because providers are absent. CoreLift creates no BTP resources and makes no live SAP, compilation or compliance claims.

## Guided connection discovery

The [guided discovery flow](guided-discovery.md) keeps preview sessions separate from assessment evidence. A strict event contract drives a deterministic simulator; only the provider creates observations. The host retains the imported-report disclosure boundary and exposes no connection/authentication mutation tool. A real SAP adapter is not yet implemented.
