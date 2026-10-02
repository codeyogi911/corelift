# First S/4HANA on-premise intake

Design status: proposed next slice, not a live connector. On 2026-10-02 the user reported CoreLift visible in the Codex sidebar. That establishes user-observed discovery only. Opening the resource, correct data rendering, navigation and reopening are still separate checks.

## Smallest useful pilot

Assess one representative custom application in an agreed development or QA system, starting with already available metadata/ATC exports. Confirm the source release and the intended modernization target separately. If only production is available, use owner-provided existing exports first; do not start monitoring, scans or remote discovery as an implicit substitute. The first outcome is an inventory with explicit coverage gaps and a reviewable disposition, not a migration or a successful-connection badge.

Information needed now (no credentials):

1. Development, QA, sandbox or production; who can authorize metadata reads for the selected system/client.
2. S/4HANA release, FPS/SPS and SAP_BASIS/ABAP platform version. Unknown is an acceptable intake answer; it blocks release-specific conclusions.
3. Which access already works: ADT in Eclipse/VS Code, SAP GUI, VPN, existing ATC/Custom Code Migration app results, or existing Cloud Connector. Availability is not permission to use every operation.
4. One custom app: transaction/app identifier or an approved package/object scope, UI technology and a short business purpose. Start without business rows or customer source code in chat.
5. Objective: clean-core review at the current release, a separately planned S/4 upgrade, or evaluation of one side-by-side extension. Do not silently turn BTP into the ERP target.
6. Local retention location/owner and what, if anything, may be shown to the AI host. No customer code upload is part of this pilot.

## Supported evidence routes

Prefer exports or existing findings from the customer's established SAP tools. SAP's [2025 Custom Code Migration Guide](https://help.sap.com/doc/9dcbc5e47ba54a5cbb509afaa49dd5a1/2025.000/en-US/CustomCodeMigration_EndtoEnd.pdf) distinguishes migration, BTP ABAP readiness and arbitrary ATC analysis project types. Since this source is already S/4HANA, do not default to ECC conversion checks. Select an available clean-core/cloud-readiness check variant appropriate to the agreed objective. Read existing results; creating analysis projects, scheduling ATC, activating SCMON/SUSG, configuring destinations or installing Notes are separate system changes. The guide also describes display-only access to findings; its full setup-role examples are not a least-privilege recipe for CoreLift.

Use [SAP's Cloudification Repository](https://github.com/SAP/abap-atc-cr-cv-s4hc) for the relevant private/on-premise release file, pinned to an immutable commit and matched to the target. Record FPS/SPS mapping explicitly: upstream states that its files track feature-package releases, not every support-package update. `Latest`, a public-cloud file or a matching object name does not establish applicability. Readiness classification, release contract, allowed operation and agentic access pathway remain separate evidence.

SAP documents an [ADT MCP setup](https://help.sap.com/docs/abap-cloud/abap-development-tools-for-visual-studio-code/enabling-adt-mcp-server) and a [Custom Code Migration Agent](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/custom-code-migration-agent-1). Evaluate those only after confirming the installed ADT/backend versions, availability, licensing and exact exposed tools. Their existence does not imply an unrestricted read-only API for arbitrary on-premise systems. Do not invent endpoints, reuse undocumented ADT internals or enable the full tool set. The migration agent's ECC-to-S/4 remit is not proof of general S/4-to-BTP migration.

Cloud Connector is not needed for a local export intake. SAP's BTP-based analysis architecture uses it, but that is a distinct existing-landscape option, not an instruction to provision BTP or a tunnel. On-stack ABAP Cloud availability begins with S/4HANA 2022 SP00, per [SAP's ABAP Cloud overview](https://help.sap.com/doc/112b8531132e43398ed50b2ad38ab14b/latest/en-US/ffa919727c624f25a95bd2f9443244f4.pdf); source and future-target availability must not be conflated.

For any future live pathway, verify documented use against the [SAP API Policy](https://help.sap.com/doc/sap-api-policy/latest/en-US/API_Policy_latest.pdf), including its requirements for agentic sequencing. The [CAP runtime MCP adapter](https://cap.cloud.sap/docs/guides/ai/cap-mcp#sap-api-policy) expressly excludes proxying SAP Application APIs. CoreLift must not expose arbitrary RFC function names, SQL/table readers, URL fetches or generic OData calls as an agent bridge.

## What the project currently lacks

| Existing code | Missing next boundary |
| --- | --- |
| `ui/app.mjs` Connections view is a static status display | A guided intake draft with explicit unknowns, scope summary and reasons a path is unavailable. No Connect button before a provider exists. |
| Inventory has source/target product versions | Separate environment class, local system/client alias, SAP_BASIS version, owner, scope and independently observed identity. |
| `corelift/capabilities.py` permits offline assessment only | Typed named read capabilities, provider/version support, endpoint identity binding, time/object/output limits and backend authorization checks. Approval text must not unlock a missing provider. |
| CLI accepts manually normalized JSON | A bounded local importer for one real supported export format, preserving original-file hashes, extractor/tool/version, check variant, result timestamp, usage window and missing coverage. Choose the format from an actual approved export. |
| Customer API evidence stays `exported-unverified` | A separate verified-evidence adapter with target mapping, artifact provenance and per-operation/pathway evidence. Until then, keep conclusions unknown. |
| MCP returns the whole assessment as structured content | An explicit disclosure policy and minimized host-visible projection before customer use. Local transport is not proof of local-only data. |
| Demo UI always labels SAP/BTP not connected | Distinct declared-access, preflight, observed-connection and imported-evidence states, each backed by an event/result, never inferred from a checkbox. |

## Proposed local intake contract

Keep an intake manifest separate from assessment schema 1.0.0. The manifest records a schema version; source system alias, environment, release/FPS/SPS, SAP_BASIS and client alias; independently selected target; one application/package scope; claimed existing access; intended capability; evidence artifacts and hashes; retention owner; and disclosure choice. It contains no password, token, cookie, endpoint-with-credentials or arbitrary executable/URL/tool argument. Unknown values remain explicit. A claim of access is not verified authentication.

First implementation scope: validate this manifest and import one supported local export into the existing normalized inventory. Return `scope-needed`, `ready-for-local-import` or `live-provider-unavailable`, never `connected`. A future named live read can proceed only after system identity, approved endpoint/pathway, user authority, object allowlist, result limits and required capabilities are known. Missing access or a TLS/authorization failure ends that attempt; do not fall back to another endpoint or a broader tool.

## Evidence for one application

Collect object/package identifiers and types, transaction/Fiori entrypoints, known dependencies and called interfaces, relevant existing ATC findings with check/version/run context, and existing usage coverage. Include screen behavior (validation, authorization, locks, value help and errors), dataset ownership/classification and ERP transaction coupling as locally reviewed metadata. Record missing evidence instead of manufacturing complete coverage. No business table rows, source dump, monitor activation or scan scheduling is needed for the initial inventory.

Hash original local artifacts as well as normalized JSON. Keep scope, exporter version and timestamps in the run record; hashes establish byte identity, not SAP correctness. Compare a small sample of dependencies/findings against the established SAP tool with the application owner before expanding to another app.

## Data boundary

Raw exports and code remain in an explicitly selected local customer-data directory outside the public checkout and package roots. Do not attach them to chat, publish them, send them to a model, or include them in telemetry. Derived identifiers, screen behavior and findings can also be confidential.

Today `ui/shared.mjs` returns the full normalized assessment to its MCP host, so the current imported-report mode is not a local-only confidentiality guarantee. Until a minimized disclosure projection is implemented and approved, evaluate customer material through the local CLI without returning its contents to the assistant or MCP host. Any host-visible summary must be explicitly scoped and reviewed; raw code is excluded. Local retention and deletion requirements must be agreed before intake. No claim of encryption, credential isolation or automatic sanitization is made by the current prototype.

## Deterministic checks before a live connector

The companion regression tests verify that an S/4 source does not become a connection; source and target versions stay distinct; unverified customer-shaped evidence remains unknown; imported reports never receive synthetic rehearsal; and absent live providers stay denied despite approval-shaped metadata. All fixtures remain synthetic. Later connector tests must additionally cover identity mismatch, out-of-scope objects, denied methods, byte/time bounds, cancellation, TLS/authorization errors, safe output projection, unsupported export versions and zero SAP writes. Those tests do not substitute for a scoped real-landscape read.
