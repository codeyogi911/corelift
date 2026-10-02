# CoreLift local assessment workspace

The optional workspace reads the same validated assessment as the CLI. It provides Connections, Applications, Clean-core findings, Migration plan and Verification. Source and future-target versions, synthetic/imported provenance and unapproved status remain visible. It has no execute, approve, upload, credential or connector controls.

## Run locally

From the source project, with Node 22+ and Python 3.11+:

```sh
npm ci
npm run build:ui
npm run preview
```

Open `http://127.0.0.1:4173/`. Stop with Ctrl-C. This is a loopback browser preview, not Codex sidebar acceptance. All UI code/styles are bundled locally; no CDN, analytics, external fonts or automatic source fetches are used. The install step downloads pinned development dependencies from npm; assessment and UI operation use local data only.

To inspect an explicitly selected local assessment already produced by the CLI:

```sh
npm run preview -- --assessment /absolute/path/assessment.json
```

The server freezes one validated snapshot at startup. Reload reads that same snapshot; restart to select another file. Malformed, oversized or unsupported inputs produce an error and never silently fall back to demo. An imported report is always labeled as imported assertions—even if its JSON says `synthetic: true`. The two-note mock rehearsal appears only in bundled demo mode. No independent verification is claimed for imported run records.

## Optional Codex package

```sh
npm run build:ui
python3 scripts/build_packages.py --with-ui --output dist-workspace
```

Choose a fresh output directory. `dist-workspace/codex` contains portable root `plugin.json`, real root `mcp.json`, bundled `ui/generated/server.mjs` and a self-contained MCP App HTML resource. This built package needs Node 22+ and Python 3.11+, without an npm install. The Cursor and Claude packages keep the skills/CLI workflow and contain no MCP UI configuration. The default builder without `--with-ui` still produces skills/CLI packages for all three hosts.

The stdio server exposes one read-only tool, `open_corelift_workspace`, which accepts `{}`. Its tool definition declares `_meta.ui.resourceUri` and `_meta["openai/ui"].entrypoints: [{"type":"global"}]`. The registered `ui://corelift/workspace-v0.2.0` resource has MIME type `text/html;profile=mcp-app`, the official MCP Apps bridge and restrictive CSP metadata. These declarations are protocol-tested. They are not a runtime acceptance claim. No host/global settings, credentials or marketplace entries are changed by the build.

For a separately authorized host smoke test, use that host's current supported local plugin-loading workflow and select the built Codex package. Confirm entrypoint discovery, primary sidebar placement, initial rendering, theme/size/context updates and reopening; retain text/structured output as fallback. Actual Codex sidebar loading remains unverified. Do not treat local preview success as satisfying this test.

Direct protocol command for a compatible local MCP client:

```sh
node ui/generated/server.mjs
# Or select a single report at process startup:
node ui/generated/server.mjs --assessment /absolute/path/assessment.json
```

Stdout is reserved for MCP JSON-RPC; this command waits for an MCP client. `CORELIFT_PYTHON` may select a trusted local Python executable if `python3` is not on PATH. The tool/UI cannot supply executable names, file paths or subprocess arguments.

## Verification

```sh
npm run build:ui
npm run test:ui
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
.venv/bin/python scripts/check_schemas.py
```

The Python-only assessment tests remain usable without Node; the optional UI packaging test skips when UI artifacts have not been built. Protocol tests run actual SDK clients against source, bundled and relocated package servers. Preview tests bind ephemeral loopback ports. See [recorded checks](validation.md) and [boundary decisions](workspace-design.md).
