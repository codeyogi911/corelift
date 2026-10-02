# Local assessment workspace: boundary review

Scope: one read-only application workspace, using the existing deterministic assessment. Navigation covers Connections, Applications, Findings, Migration plan and Verification. Connections show offline source provenance and unavailable live providers; they do not collect credentials. A persistent banner distinguishes synthetic demo from imported report assertions. All approvals stay unapproved and execution stages blocked.

The Python exporter validates a selected local assessment or computes the bundled synthetic assessment. The file path is selected only at process startup, never supplied by a tool/UI request. Its output is bounded and frozen for the local server lifetime. Errors remain errors and never silently switch to demo. A canonical snapshot hash identifies exactly what the workspace is showing. Imported run records are claims from that report, not verification performed by the workspace. Synthetic mock rehearsal is displayed only with the actual bundled demo, never as proof for an imported file.

An actual stdio MCP server uses the official SDK and exposes one empty-input read-only tool, `open_corelift_workspace`. Its tools/list metadata points to `ui://corelift/workspace-v0.4.0` and declares the OpenAI global entrypoint. A registered resource returns a self-contained MCP App document. Text and structured results are usable without UI. For imported reports, these contain fixed disclosure status by default or exactly three aggregate counts with explicit local startup consent. Detailed imported evidence stays in the local CLI/preview. The static resource contains no assessment data. See [the privacy boundary](privacy-boundary.md). No placeholder HTTP MCP endpoint is declared.

The UI uses the official MCP Apps SDK, registers the result listener before initialization, and renders the initial result without a duplicate call. Host capability detection controls optional refresh/link behavior. Host theme/context are applied when supported. A separate loopback preview runs the same UI through a fixed same-origin read endpoint. It is not evidence of Codex acceptance.

Untrusted assessment strings render with DOM text APIs. Only user-selected HTTPS sources on explicit SAP/OpenAI/MCP documentation hosts can open; no sources are fetched automatically. Resource CSP denies network/assets by default. Preview exposes exact routes, allows only GET, validates Host/Origin, disables caching, and serves no arbitrary files. Python calls use fixed executable/arguments without a shell, with timeout/output bound; no source text is executed.

Independent Astra High design review approved this boundary with requirements for fail-closed imports, bounded exporter lifecycle, visible provenance and restrictive preview/resource handling. Those requirements guide implementation and tests. Actual local host connection, resource rendering, entrypoint discovery and sidebar acceptance remain a separately authorized host smoke test; no marketplace/global configuration is changed here.

Contract references checked 2026-10-02:

- [OpenAI global entrypoint](https://github.com/openai/mcp-extensions/blob/main/docs/spec.md#global-entrypoint)
- [MCP App resource and CSP](https://developers.openai.com/plugins/build/chatgpt-ui)
- [OpenAI MCP extension SDK](https://github.com/openai/mcp-extensions/blob/main/typescript/README.md)
- [MCP Apps lifecycle](https://apps.extensions.modelcontextprotocol.io/api/classes/app.App.html)
