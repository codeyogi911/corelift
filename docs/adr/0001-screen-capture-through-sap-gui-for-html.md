# Reference screenshots through SAP GUI for HTML

Status: accepted, 2026-10-21

## Context

Shashwat asked for agents to "go deep" on screen (Dynpro) programs and take screenshots of them, so the target UI can be reviewed against the original, as Shopify's Helix does with reference screenshots. ADT exposes program source but not Dynpro layouts or flow logic, so the read-only ADT client cannot produce a picture of a screen.

## Decision

Add one capability, `sap-screen-capture`, outside the ADT allowlist. With an approval the agent records as the user's (system, named transactions, the user's words), `corelift/sap/screens.py` hands out SAP GUI for HTML links (`/sap/bc/gui/sap/its/webgui?~transaction=…`) only for approved transactions of the lifted scope on the connected system. The agent opens them with the host's browser tool in the user's own signed-in session, takes a screenshot of the first screen and goes back. The user signs in there; the password never reaches the agent.

## Consequences

- SAP access is no longer purely read-only by construction. Opening a transaction runs its start-up (PBO) logic, and nothing in CoreLift can stop a browser from pressing Save or Execute. Display-only is policy in the plan's rules and the skill, not enforcement. CoreLift limits only which links it hands out.
- Discovery judges each screen program's start-up code (LOAD-OF-PROGRAM, INITIALIZATION, AT SELECTION-SCREEN OUTPUT, PBO modules, the FORMs they call, and START-OF-SELECTION for a report without a selection screen) as display-only, unclear or changes-data. The scan errs towards not display-only: includes, dynamic calls, other programs' FORMs, object creation and method or function calls make it unclear. The agent captures only screens whose layout the source leaves unclear. `corelift/sap/screens.py` refuses a link unless the transaction is mapped to a judged screen program, refuses changes-data always, and opens unclear ones only when the approval lists them as accepted. The transaction-to-program match is the agent's, and a transaction that skips its first screen or starts with a variant runs more than the scan sees.
- Shashwat in the project thread, 2026-10-23: "its okay, agents should be able to read screen code and decide if they need to screenshot".
- The skill asks for the approval once, names the transactions, and recommends a development or QA system. Users who refuse lose only the screenshots; the lift, assessment and loop work without them.
- The ledger and approval are local bookkeeping: CoreLift cannot prove the statement came from the user.
- Rejected: reading Dynpro layouts over RFC (`RPY_DYNPRO_READ`) needs an open RFC pathway CoreLift does not use; rendering screens from source alone would guess at layouts; a CoreLift-owned headless browser would need a new dependency and still run the same start-up logic.
- Revisit when a released, read-only screen metadata API exists, or when the goscrub connector offers one.
