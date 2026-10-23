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

## SAP connection and plugins slice, 0.3.0

Verified 2026-10-21 with Python 3.13 and Node 22; CI covers Python 3.11 and 3.14.

- 59 Python tests (22 for the SAP slice) and 9 Node tests passed. SAP tests run the real ADT client against the synthetic ADT endpoint in `corelift/sap/mock.py`: allowlist refusal before any socket, dot-segment and loopback-HTTP refusal, 401 handling without echoing the password, discovery into a contract-valid inventory, namespaced SAP objects treated as APIs, pinned-evidence mapping, collision-free workspace names and MCP stdio round trips.
- `corelift lift` ran against the synthetic endpoint with SAP's real Cloudification Repository files at commit `934db1ad2f5c` (2025 FPS01 private-edition file plus classic classifications): four applications, all four SAP dependencies classified.
- `claude plugin validate` passed on the repository root, the marketplace and the built Claude package. One `claude --plugin-dir` run on the demo system exercised the skill, `corelift_lift` and two migration subagents that drafted ABAP Cloud code and `REVIEW.md` files; it exposed parallel drafting of dependent apps, which the skill now orders.
- Not exercised: a real SAP system (endpoint shapes, release detection from `/sap/bc/adt/system/components`, authorizations, CSRF expiry) and compiling or testing any drafted target code.

### Codex new-user run, 2026-10-21

Codex CLI 0.159.3 installed CoreLift 0.3.0 from `main` with `codex plugin marketplace add codeyogi911/corelift` and `codex plugin add corelift@corelift`. In an empty folder, `codex exec "lift and shift my SAP custom code using the demo system"` loaded the `connect-sap` and `lift-and-shift-sap` skills, called `sap_connection_status`, `sap_use_demo_system` and `corelift_lift` (real Cloudification files at commit `934db1ad2f5c`), showed a four-application table and drafted target code, tests and `REVIEW.md` for all four in about seven minutes. Drafted ABAP was not compiled or run.

Friction found and fixed in the same change: the docs had no Codex install command ("install from the plugin directory"); the not-connected status pointed the user at a `<plugin-root>` placeholder in a hidden cache folder (status now returns `connect_command` with the real path); the skill offered a choice when the user had already asked for the demo; and briefs named successors without saying whether the target releases them, so the agent searched the web and the raw evidence files to check. A second, local `corelift` marketplace on the test machine would have started a duplicate MCP server; the install docs now say how to check (`-c` disabling did not stop the other copy's server).

The fixed build was then installed alone in Codex from a local marketplace and both flows re-run with `codex exec`. "Connect to my own SAP system" called `sap_connection_status` and handed back the exact `connect_command` without reading CoreLift's source. The demo lift produced briefs stating each successor's state in the 2025 FPS01 release file (three released, `BAPI_PO_GETDETAIL1` flagged as not listed) and drafts for all four applications; the agent still searched SAP Help for mail API method details. Interactive Codex (TUI), a real SAP connection and compiling drafted ABAP were not exercised.

## Agent-driven flow slice, 0.4.0

Verified 2026-10-21 with Python 3.13 and Node 22; CI covers Python 3.11 and 3.14.

- 101 Python tests passed. New ones drive discovery's screen behavior hints and transactions against the synthetic ADT endpoint, the screen-capture provider (denied without the user's statement, bound to the connected system and lifted scope, PNG/JPEG only, no path escape), stack profiles (shipped and workspace profiles, shape validation, briefs following the chosen stack), the checkpoint ledger (gate order, stale evidence after a code change, reviewer independence, blocked gates closing as unverified, delegation, lessons) and the new MCP tools. A test keeps every tool, skill and subagent named in `skills/` and `agents/` real.
- Not exercised: SAP GUI for HTML on a real system, capturing a screenshot through a host browser, a host running the new skills and subagents end to end, and running any drafted target code's tests. Shopify's Helix article and the MIT-licensed helix-skills repository informed the loop design; no code was copied. Nothing from goscrub was used.

## Screen start-up verdicts, 2026-10-23

Verified with Python 3.13; CI covers Python 3.11 and 3.14. 110 Python tests passed. New tests drive discovery against the synthetic ADT endpoint (a dialog whose PBO only sets a status is display-only; a report without a selection screen that updates and commits on open is changes-data; a report whose INITIALIZATION performs a FORM that calls a function module is unclear), 15 adversarial snippets (includes, chained statements, one-line modules, dynamic calls, object creation, quotes inside strings, EXPORT TO DATABASE, file output, NO-DISPLAY parameters, update tasks), and the capture plan's refusals (no judged program, changes-data, unclear without acceptance). Not exercised: real programs, code inside includes and called function modules, transactions that skip their first screen or start with a variant.

## Codex app engine run, 2026-10-23

The Codex desktop app could not be driven directly (macOS refused screen control without showing a dialog), so the app's own engine was driven instead: `codex app-server` from Codex CLI 0.159.3 with `plugin/list`, `skills/list` and two-turn conversations on the app's default model (`gpt-6-luna`, the default `model/list` reported), as the app does. Interactive app screens were not seen.

- The CoreLift card carried only a name, a one-line description and a category: no starter prompt, long description or icon. The manifest now sets three starter prompts (the demo prompt first), a long description, capabilities, links, a brand colour and a logo and composer icon, which packages ship from `assets/`. Whether the app renders each field was not checked.
- "Lift and shift my SAP custom code using the demo system" lifted four applications, then asked the user to reply with a long scripted phrase to choose stack, scope and review mode. After "go with what you recommend" the agent hand-edited two briefs, because on-stack briefs said "Target stack: SAP BTP with CAP" while their instruction said ABAP Cloud. Briefs now state that on-stack apps stay on S/4HANA whatever stack is chosen, `INDEX.json` marks `follows_stack`, and the skills ask stack, scope and review mode in one message where "go" accepts every default.
- Re-run on the fixed build: one "go" settled all three questions, no brief was edited by hand, and the first checkpoint came back for review as designed. Drafted code was not compiled or run.
