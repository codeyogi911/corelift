# CoreLift local assessment workspace

The standalone local preview and bundled public demo read the same validated assessment as the CLI. They provide Connections, Applications, Clean-core findings, Migration plan and Verification. Source and future-target versions, synthetic/imported provenance and unapproved status remain visible. Imported MCP reports instead show disclosure status by default, with a separate opt-in for three aggregate counts. See [the exact data boundary](privacy-boundary.md). There are no execute, approve, upload, credential or connector controls.

## Run locally

From the source project, with Node 22+ and Python 3.11+:

```sh
npm ci
npm run build:ui
npm run preview
```

Open `http://127.0.0.1:4173/`. Stop with Ctrl-C. This is a loopback browser preview, not Codex sidebar acceptance. All UI code/styles are bundled locally; no CDN, analytics, external fonts or automatic source fetches are used. The install step downloads pinned development dependencies from npm; the local preview makes no automatic external requests. Data returned to an MCP host may be processed remotely by that host.

To inspect an explicitly selected local assessment already produced by the CLI:

```sh
npm run preview -- --assessment /absolute/path/assessment.json
```

The server freezes one validated snapshot at startup. Reload reads that same snapshot; restart to select another file. Malformed, oversized or unsupported inputs produce an error and never silently fall back to demo. An imported report is always labeled as imported assertions—even if its JSON says `synthetic: true`. The two-note mock rehearsal appears only in bundled demo mode. No independent verification is claimed for imported run records.

## Guided connection discovery

Open Connections → Try guided demo → Simulate sign-in. The agent flow discovers fictional system metadata and suggested applications automatically; select one for a local scope. Failure/cancellation/retry states are testable. The standalone preview accepts only a locator for a future real connection and explains when the provider is unavailable. No credentials or SAP connection are involved. See [the implemented flow and protocol](guided-discovery.md).

## Optional Codex package

```sh
npm run build:ui
python3 scripts/build_packages.py --with-ui --output dist-workspace
```

Choose a fresh output directory. `dist-workspace/codex` contains portable root `plugin.json`, real root `mcp.json`, bundled `ui/generated/server.mjs`, separate `ui/generated/preview.mjs`, and a self-contained MCP App HTML resource. This built package needs Node 22+ and Python 3.11+, without an npm install. The Cursor and Claude packages keep the skills/CLI workflow and contain no MCP UI configuration. The default builder without `--with-ui` still produces skills/CLI packages for all three hosts.

The stdio server exposes one read-only tool, `open_corelift_workspace`, which accepts `{}`. Its tool definition declares `_meta.ui.resourceUri` and `_meta["openai/ui"].entrypoints: [{"type":"global"}]`. The registered `ui://corelift/workspace-v0.4.0` resource has MIME type `text/html;profile=mcp-app`, the official MCP Apps bridge and restrictive CSP metadata. These declarations are protocol-tested. They are not a runtime acceptance claim. No host/global settings, credentials or marketplace entries are changed by the build.

For a separately authorized host smoke test, use that host's current supported local plugin-loading workflow and select the built Codex package. Confirm entrypoint discovery, primary sidebar placement, initial rendering, theme/size/context updates and reopening; retain text/structured output as fallback. Actual Codex sidebar loading remains unverified. Do not treat local preview success as satisfying this test.

Direct protocol command for a compatible local MCP client:

```sh
node ui/generated/server.mjs
# Or select a single report, withholding all contents and counts from the host:
node ui/generated/server.mjs --assessment /absolute/path/assessment.json
```

Add `--share-summary` only after separate explicit permission to send the three counts; connection consent is insufficient. Detailed imported evidence is available only in the local CLI/preview. The report path is visible in local launch configuration; this server boundary does not restrict other host tools.

Stdout is reserved for MCP JSON-RPC; this command waits for an MCP client. `CORELIFT_PYTHON` may select a trusted local Python executable if `python3` is not on PATH. The tool/UI cannot supply executable names, file paths or subprocess arguments.

## Verification

```sh
npm run build:ui
npm run test:ui
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
.venv/bin/python scripts/check_schemas.py
```

The Python-only assessment tests remain usable without Node; the optional UI packaging test skips when UI artifacts have not been built. Protocol tests run actual SDK clients against source, bundled and relocated package servers. Preview tests bind ephemeral loopback ports. See [recorded checks](validation.md) and [boundary decisions](workspace-design.md).
