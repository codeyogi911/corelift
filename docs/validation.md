# Local foundation verification

Verified 2026-10-02 using Python 3.14.4. Runtime target: Python 3.11+. No SAP connection, BTP resource, customer upload, host installation or public repository was used.

| Check | Result |
| --- | --- |
| Unit/integration checks | 34 passed |
| JSON Schema 2020-12 | Inventory, API evidence, sources and assessment validated by jsonschema 4.26.0 |
| Portable manifest | Validated against vendored official Agent Plugins 1.0.0 schema; SHA-256 checked |
| Skill frontmatter | Skill Creator quick validator passed |
| Claude manifest | `claude plugin validate` passed; optional author information warning |
| Host package parity | Codex/Cursor/Claude packaged CLIs produce identical assessment JSON |
| Synthetic rehearsal | Two fake notes: atomic load, idempotent replay, semantic comparison, rollback, rejection/failure/concurrency checks |
| External effects | Pure assessment/rehearsal tested with network, subprocess and report-write guards; absent providers deny execution even with approval metadata |

Independent code and experience reviews found and prompted corrections for access kind/operation, transitive transaction coupling, dynamic-call uncertainty, unverified customer evidence, bounded input reads, screen behavior reconstruction, source/target evidence provenance and data ownership. Regression tests exercise those corrections. A final architecture review additionally checked table-read eligibility, multiline dynamic calls, INSERT variants and Markdown endorsement claims; these were corrected and regression-tested.
The independent final reviewer reran all 34 tests and the exact reproductions, confirmed the corrections, and reported no remaining material blocker within the local offline prototype scope.

The fictional request-notes application is a future-target sidecar design candidate. The Dynpro workbench remains on-stack/transaction-coupled; its behavior would need reconstruction for BTP. The internal wrapper and its consumer retain C-level dependency risk. Mock rehearsal demonstrates Python behavior only, with no SAP extraction, compilation, authorization, delta transfer or deployment verification.

Remaining limitations: lexical ABAP hints do not prove dependency coverage; normalized exporters and verified customer evidence ingestion are not implemented. Every customer API claim stays unresolved in this prototype. Host runtime installation/invocation remains untested. No published Cursor-native JSON schema or full Codex runtime validator is claimed; their packages receive manifest shape, containment and shared-CLI parity checks.

## Read-only workspace slice, 0.2.0

Verified locally on 2026-10-02 with Node 23.6.0, Python 3.14.4, official MCP SDK 1.31.0 and MCP Apps SDK 2.0.3. Runtime targets remain Node 22+ and Python 3.11+. Older minimum runtimes were not separately exercised.

- 37 Python tests passed, including workspace import provenance and optional package separation.
- Nine Node integration tests passed: real MCP tools/resources discovery, empty-input global-entrypoint metadata, parseable bundled HTML, standalone bundled server, frozen imported snapshot, fail-closed invalid input, exact read-only loopback routes with Host/Origin protection, constrained links/routes, invalid-schema rejection, startup cancellation and relocated package parity. Related assertions are grouped into nine test cases.
- Five JSON contracts and the portable manifest/optional MCP config passed reference JSON Schema 2020-12 validation. Both official Agent Plugins schema checksums were verified.
- A bounded owned-tab browser check inspected real pixels and accessibility state: desktop application detail; small-screen stacked layout with no document horizontal overflow; keyboard application and navigation selection; search empty state; unknown dependency evidence; unavailable SAP/BTP connections; unapproved plan stages; synthetic-only verification; invalid-input error without demo fallback. Desktop/mobile/error screenshots are saved locally under ignored `reports-ui/`. Temporary viewport override was reset, owned tab closed and loopback process stopped. No shared tabs were changed.
- Independent Astra High boundary and code reviews checked schema parity, import trust separation, bounded exporter lifecycle, MCP metadata, CSP/source links, UI states and optional package containment. Code review caught a startup cancellation race; it was fixed and deterministically regression-tested for both preview and MCP startup. Reviewer independently reran seven non-network tests and reported no remaining material blocker in the reviewed slice.

The initial HTML has a loading status and no-script fallback; runtime errors render an accessible error with retry. Browser preview is not a host integration test. Codex global sidebar acceptance, host theme/context negotiation and live MCP iframe lifecycle have **not** been exercised in the actual host. The portable metadata and resource contract are implemented and protocol-tested; this distinction is maintained in the UI and package documentation. Customer connectors, SAP behavior, BTP deployment and migration execution remain outside this slice.

## Initial public release preparation

The release includes the official Apache-2.0 license, original-work attribution and full license/notice texts for the 15 npm dependencies in the UI/server bundle dependency graph. Agent Plugins schemas remain unchanged and attributed under their upstream Apache-2.0 license. Public source/package checks reject personal absolute paths, secret-like values and missing distribution notices. Gitleaks 8.30.1, downloaded from its official release and checksum-verified, found no secrets in the initial local history or generated release packages. These checks reduce risk; they are not a guarantee that arbitrary future customer input is safe to publish.

A local Codex CLI 0.159.3 installation succeeded for CoreLift 0.2.0 after explicit local marketplace registration. Cached manifest, MCP configuration, server, UI and notices matched the built package by SHA-256. Repository auto-discovery did not work in that CLI environment, even with a command-scoped project-trust override. Actual Codex sidebar discovery/navigation remains unverified: the sanctioned computer-use tool refused access to the Codex application, and no bypass or desktop restart was attempted. Installation and protocol success must not be presented as host UI acceptance.
