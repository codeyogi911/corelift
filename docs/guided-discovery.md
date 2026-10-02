# Connect once, then discover

Workspace 0.4.0 implements a guided local simulation of the desired development-system flow. It does not implement a live SAP adapter or secure sign-in. The only initial input for a future real connection is the system address or an existing saved connection. Release, FPS/SPS and ABAP platform are discovery outputs, not a technical questionnaire.

## Try the implemented flow

Run `npm run preview`, open Connections, choose **Try guided demo**, review the three metadata reads, and choose **Simulate sign-in**. CoreLift establishes fictional system/version facts, shows available versus unknown capabilities, and suggests two representative applications. Choose one to create the local scope for a later assessment. This does not replace or verify the existing synthetic assessment. Failure scenarios are available under the expandable demo control; cancel, retry and clear-session actions are functional.

The same fictional flow is available in the MCP workspace without changing the existing empty-input tool. Private imported reports still show only withheld status or the separately authorized three-count summary. Opening the fictional Connections view does not grant permission to transmit imports.

For a built optional Codex package, run `node ui/generated/preview.mjs` from that package to use its separate local preview. No npm install is required. All optional UI bundles include the preview entrypoint. The existing full synthetic assessment is still available.

The local preview alone accepts a real HTTPS origin or saved-connection name. It validates the locator and returns **Connection provider unavailable** or **No saved connection configured**. It never contacts that address or claims authentication. No real saved-connection catalog is imported, no files are searched and no credentials are requested. The disabled sign-in control explains the missing adapter. The entered locator is cleared from the form and retained only in transient local session memory until cleared, expired or the preview stops. No browser storage is used.

## Connection and observation contract

Development is currently user-declared; it does not authorize writes or independently prove server identity. The planned real flow is: select locator → review the bounded read scope → sign in in a trusted provider-owned UI → bind the authenticated server identity → discover supported metadata operations → list bounded application metadata → let the user choose a scope.

The local Node state machine is authoritative for preview sessions. `POST /api/discovery` accepts only `create`, `status`, `prepare` (fixed simulation scenario), `locate`, `start`, `retry`, `cancel`, `disconnect` and `select` events. Mutations require the current revision. Opaque in-memory session IDs isolate tabs; at most four sessions exist per preview and expire after ten minutes. No auth token or password is accepted in this protocol. Session IDs are local bearer handles, not SAP credentials; local processes can operate the preview, which is not an OS isolation boundary.

Authentication success, identity observations and candidate results originate inside the fixed simulator, never from browser events. Delayed callbacks are bound to an attempt generation; cancel, retry, replacement, disconnect and expiry prevent stale results from repopulating facts. Failed attempts clear results and selection. Discovery candidates and assessment evidence are separate stores.

The shared browser state machine inside an MCP host is a separate fictional simulation, not an authenticated Node session. Private locators are unavailable there. Its simulation never calls an MCP mutation tool or writes to an assessment.

POST requires exact Host and a present matching Origin, exact JSON content type, at most 8 KiB streamed data and a 1.5-second body deadline. Missing origins, forged completion events, stale revisions and unexpected fields fail closed. No cross-origin permissions are added. The result schema allows only simulated observations and unknown facts; there is no real connected/verified state. Errors never reflect a locator or incoming body.

## Supported SAP route and current evidence

Checked 2026-10-02. SAP's [official ADT MCP tutorial](https://developers.sap.com/tutorials/abap-dev-adt-mcp-server-tools/) describes an experimental local HTTP server inside ADT for VS Code, dependent on an active destination and virtual-workspace compatibility. Its advertised tools include mutation as well as inspection. Therefore this prototype does not equate a running ADT MCP server with a safe discovery provider, or claim direct Codex compatibility from MCP support alone.

SAP's [ABAP AI roadmap](https://help.sap.com/docs/abap-cross-product/roadmap-info/genai) documents object-search capability. The [ADT object-search guide](https://help.sap.com/docs/abap-cloud/abap-development-tools-user-guide/abap-object-search) describes finding development objects. These support evaluating metadata discovery through supported development tooling; they do not establish exact tool names, response schemas or release availability for the user's system. The live adapter remains unmapped pending the selected supported client/backend and its actual capability catalog. No invented system-information endpoint is used.

Consult SAP's [ADT MCP tool catalog](https://help.sap.com/docs/abap-cloud/abap-development-tools-for-visual-studio-code/mcp-tools) and [security guidance](https://help.sap.com/docs/abap-cloud/abap-development-tools-for-visual-studio-code/security-recommendations-and-considerations) when binding the adapter. Those dynamic Help pages were discoverable but their full current body was not extractable in this research run; this implementation does not infer a detailed authentication or tool contract from them. Official tutorial/roadmap evidence is a design constraint, not verification of the user's landscape.

## Gate before a real adapter

Only after the user supplies a locator and approves actual sign-in/read scope, verify the installed SAP client/backend and supported tool contracts. Bind the approved origin, system/client and authenticated identity; retain secrets only in the supported provider/OS mechanism, never this UI or model context. Do not guess a login URL, mint credentials, install tools or enable broad SAP roles.

The adapter must independently enforce an allowlist of named metadata reads and bounded candidates; tool names, annotations and possession of a developer account are insufficient. Do not run code search/source reads, ATC scans, unit tests, monitor setup, generators, activation, transports, business-row queries or uploads under this discovery grant. Existing ATC findings require an explicitly supported read mapping and scope. The three current internal operation IDs are prototype intent names, not SAP APIs.

This change performs **no DNS lookup, HTTP fetch, redirect or SAP invocation** for locators. Rejecting URL credentials, paths, query/fragment, local/metadata targets and ambiguous IP forms reduces misuse of the draft, but is not a complete network SSRF defense. A future adapter must enforce exact allowlisted origins/paths, validate all resolved IPs against approved network scope at connection time (including rebinding), reject unapproved redirects, validate TLS/peer identity, control proxy behavior and separately bind any intentionally local ADT bridge. These transport controls cannot be delegated to browser validation or host hooks.

If a supported read is unavailable, retain the specific fact as unknown and request only the missing fact or an existing result. Do not reintroduce a general release/access questionnaire or silently substitute a new scan. Connection permission never enables host disclosure. The [privacy boundary](privacy-boundary.md) still applies to reports and to independent host file, CLI or browser access.
