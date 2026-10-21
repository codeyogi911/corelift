# CoreLift

SAP clean-core migration assistant. **Early prototype**, released under Apache-2.0.

This local foundation assesses normalized ECC/S4HANA ABAP exports and produces an evidence-backed, unapproved migration plan. It includes a working synthetic assessment and a two-note in-memory rehearsal. It has no live SAP connector, migration executor or deployment provider.

## Run the first slice

Python 3.11+; no dependency install, credentials or network required:

```sh
git clone https://github.com/codeyogi911/corelift.git
cd corelift
python3 -m corelift demo
python3 -m corelift demo --output reports-demo
python3 -m corelift rehearse-demo
```

`reports-demo` must be a new folder. It contains `assessment.md`, `assessment.json`, and `rehearsal.json`. Use a different folder for each run. JSON includes deterministic input hashes and source revisions.
Generated reports are local and excluded from Git.

The fictional purchasing portfolio exercises eight applications: ERP purchasing stays in ERP, request notes are a BTP sidecar candidate, a Dynpro workbench stays transaction-coupled, a wrapper retains internal-object risk, a dependent application inherits that risk, a not-recommended dependency needs rebuilding, incomplete evidence triggers investigation, and an unused report is a retirement candidate. All `SYN_*` APIs are fake; their availability is not a claim about SAP. The rehearsal verifies two fake extension-owned notes, idempotent replay, semantic reconciliation and checkpoint rollback in memory.

For your own explicitly supplied local exports:

```sh
python3 -m corelift assess --inventory inventory.json --evidence api-evidence.json --sources sources.json
```

See [input contracts](docs/input-contracts.md), [SAP decisions](docs/sap-decisions.md) and [architecture](docs/architecture.md). Do not commit customer exports or credentials. Customer assessment requires normalized local metadata and target-pinned API evidence; it is not live application discovery. A report candidate is not SAP certification. ERP core remains ERP; BTP extends it.

## Open the local workspace

Node 22+ and Python 3.11+:

```sh
npm ci
npm run build:ui
npm run preview
```

Open `http://127.0.0.1:4173/` for the synthetic assessment. The read-only workspace shows connections, applications, clean-core findings, migration stages and verification. Stop with Ctrl-C. Use `npm run preview -- --assessment /absolute/path/assessment.json` to inspect an explicitly selected local report. Imported assertions stay distinct from actual demo checks.

See [workspace setup and Codex package](docs/workspace.md). The actual global-entrypoint tool and MCP App resource are protocol-tested; Codex sidebar acceptance remains unverified.

## Host packages

```sh
python3 scripts/build_packages.py --output dist
python3 dist/codex/scripts/corelift.py demo
python3 dist/cursor/scripts/corelift.py demo
python3 dist/claude/scripts/corelift.py demo
```

Each package contains the same engine, schema, evidence, synthetic fixtures and shared `assess-sap-clean-core` skill. Codex uses a portable root `plugin.json`; Cursor and Claude use their native manifest directories. The default packages remain skills/CLI-only. The optional `--with-ui` build adds a tested read-only MCP assessment workspace to Codex. No host settings or marketplace are modified by building packages.
A rebuild requires a fresh output folder, for example `--output dist-next`; the builder refuses to overwrite packages.

For a separately authorized local host test, Claude supports `claude --plugin-dir ./dist/claude`; load the skill and ask for the synthetic demo. Codex/Cursor package loading depends on their available local authoring surfaces. Host installation and invocation have not been verified in this foundation. `claude plugin validate ./dist/claude` is a structural check, not a runtime compatibility guarantee.

Current contracts were checked against [OpenAI packaging docs](https://developers.openai.com/plugins/build/plugins), [Claude manifest docs](https://code.claude.com/docs/en/plugins-reference), and [Cursor plugin docs](https://cursor.com/docs/reference/plugins) on 2026-10-02. OpenAI's portable schema is vendored with a SHA-256 checksum for repeatable validation. Cursor's native adapter is skills-only; advanced host-specific components will need their own validation. Hooks are optional and are never a safety boundary.

## Verify

```sh
python3 scripts/verify.py
```

This runs the same gate as CI: agent docs, Python tests, UI build and tests, JSON Schema checks, package build and release checks. See [contributing](CONTRIBUTING.md) for setup and [AGENTS.md](AGENTS.md) for the build loop.

Tests verify decisions, graph propagation, target mismatch and missing evidence, C1-versus-C2, malformed exports, comment injection, offline side effects, mock atomicity/idempotency/rollback/concurrency, package containment and engine parity. The demo and unit tests have zero network calls. Package credential scanning is a limited guard, not a promise that arbitrary customer exports are sanitized.

## Next implementation boundary

Prove one scoped SAP read pathway and full ATC/usage/screen export coverage in an authorized test landscape. Add verified functional replacement and per-operation API evidence before expanding placement decisions. Build/deployment/data migration remain blocked until scoped approval, provider enforcement, checkpoint, rollback and recorded verification exist. No customer connection, upload, credentials/grants, BTP resources, spend, global installation or external publication is authorized by running this prototype.

## License and project direction

CoreLift's shared assessment engine, host packages, synthetic examples and tests are open source under [Apache-2.0](LICENSE). See [third-party notices](THIRD_PARTY.md). This is an independent project, not an SAP, OpenAI, Anthropic or Anysphere product; no affiliation, endorsement or certification is claimed. Product names belong to their respective owners.

The open-source foundation is usable on its own for local assessment and review. Optional managed services, hosted collaboration or enterprise support may be explored later; none is implemented or required by this release. CoreLift is a working name.

See [contributing](CONTRIBUTING.md) for development checks and [security reporting](SECURITY.md). Never put credentials, customer exports or proprietary SAP materials in issues or pull requests.
