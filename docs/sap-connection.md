# Connecting SAP and lifting apps

Connecting the SAP system is the only step a user does by hand. The agent does the rest through the `corelift-sap` MCP server and the `lift-and-shift-sap` skill.

## Install

Claude Code:

```sh
/plugin marketplace add codeyogi911/corelift
/plugin install corelift@corelift
```

Claude Code then prompts for the SAP URL, client, user and password (the password goes to the OS credential store). Leave them empty to connect later from a terminal, or enter `demo` as the URL.

Codex:

```sh
codex plugin marketplace add codeyogi911/corelift
codex plugin add corelift@corelift
```

Its onboarding skill walks the user through connecting. To pick up a newer `main`, run `codex plugin marketplace upgrade corelift`, then `codex plugin add corelift@corelift` again. `codex plugin list | grep corelift` should show one enabled CoreLift; with a second copy (for example a local marketplace pointing at a clone) Codex silently serves the tools from whichever copy registered `corelift-sap` first, even if you disable the other with `-c`. `codex mcp get corelift-sap` shows which copy that is; remove the one you are not testing with `codex plugin remove`.

## Try it on the demo system

In an empty project folder, start `codex` (or Claude Code) and ask: "lift and shift my SAP custom code using the demo system". The agent switches the session to the fictional demo system, lifts package `ZDEMO_PURCHASING` into `corelift-workspace/`, shows a table of four applications and drafts target code with a `REVIEW.md` per application. `codex exec` runs the same prompt non-interactively.

## Connect

`sap_connection_status` returns `connect_command`, the exact command with the installed plugin path; agents hand it to the user. This deliberately shows the host the plugin's install folder (which the host chose and already loads skills from); it never contains the password or connection file contents. `<plugin-root>` below is that path's folder.

```sh
python3 <plugin-root>/scripts/corelift.py connect        # prompts; password is hidden
python3 <plugin-root>/scripts/corelift.py connect --demo # fictional system, no SAP needed
python3 <plugin-root>/scripts/corelift.py status
```

`connect` tests the system read-only, then saves `~/.corelift/connection.json` with owner-only permissions (`CORELIFT_HOME` moves it). `CORELIFT_SAP_URL`, `CORELIFT_SAP_CLIENT`, `CORELIFT_SAP_USER`, `CORELIFT_SAP_PASSWORD` and `CORELIFT_SAP_VERIFY_TLS` override the file. Agents see the URL, client and user, never the password.

The SAP user needs ADT display rights (`S_ADT_RES`, `S_DEVELOP` activity 03) and the `/sap/bc/adt` ICF service active. HTTPS is required except for loopback test systems; `--ca-file` accepts a company CA bundle.

## What a lift does

| Step | Tool | Reads | Writes (workspace only) |
| --- | --- | --- | --- |
| discover | `corelift_discover` | SAP via ADT: components, package tree or name search, ABAP source | `inventory.json`, `source/`, `discovery.json` |
| evidence | `corelift_fetch_evidence` | SAP's public [Cloudification Repository](https://github.com/SAP/abap-atc-cr-cv-s4hc) at one commit | `evidence/`, `api-evidence.json`, `evidence-notes.json` (with each successor's state in the target's release file) |
| assess | `corelift_assess` | the two files above | `assessment.json`, `assessment.md` |
| plan | `corelift_plan` | the assessment | `migration/<APP>/BRIEF.md`, `migration/INDEX.json` |

`corelift_lift` runs all four. A workspace carries its own `.gitignore` because it holds customer source and screenshots.

## After the lift: screens, stack, shift

| Step | Tool | Asks the user | Writes (workspace only) |
| --- | --- | --- | --- |
| screens | `corelift_screen_plan`, `corelift_record_screen` | approval to open the listed transactions in display mode | `screens/PLAN.json`, `screens/<TCODE>/*.png`, `screens/INDEX.json` |
| stack | `corelift_list_stacks`, `corelift_choose_stack` | which target stack (SAP BTP with CAP by default) | `target-stack.json`, `target-stack.md`, rewritten briefs |
| shift | `corelift_checkpoint_plan`, `corelift_gate`, `corelift_checkpoint_close` | approval per checkpoint, or one delegation (`corelift_delegate`) | `migration/<APP>/target/`, `LOOP.json`, `REVIEW.md`, `LESSONS.md` |

**Screens.** Discovery reads each screen program's modules, authorization objects, messages and locks from its source and lists the transactions in scope. Layouts are not readable over ADT, so with the user's approval the agent opens each transaction in SAP GUI for HTML (`/sap/bc/gui/sap/its/webgui`, which must be active) in the user's own signed-in browser and files a screenshot. CoreLift hands out links only for approved transactions of the lifted scope on the connected system; the browser itself is the host's tool, outside CoreLift's enforcement. Opening a transaction runs its start-up logic, so the skill recommends a development or QA system.

**Stack.** Target stacks are Markdown profiles in `skills/choose-target-stack/stacks/` (SAP BTP with CAP, ABAP Cloud on S/4HANA, AWS, Google Cloud, Azure). A customer adds their own as `<workspace>/stacks/<id>.md` with the same sections. Every profile reaches SAP only through released APIs. The stack never changes a disposition; choosing ABAP Cloud drafts side-by-side candidates on-stack.

**Shift.** Inspired by [Shopify's Helix](https://shopify.engineering/helix): each app is drafted in small checkpoints, and each checkpoint passes behavior (tests), screen review against the reference screenshots (screen checkpoints only), two independent reviews and approval, all on the current code. A code change makes earlier evidence stale; a stack whose tests need SAP (ABAP Unit) closes the checkpoint as `closed-unverified`; accepted corrections go to `LESSONS.md` for later checkpoints. In Claude Code the `sap-migration-engineer` subagent builds and `sap-migration-reviewer` subagents review in fresh contexts. The ledger keeps agents honest about their own evidence; it is local bookkeeping, not tamper-proof.

## Boundaries

- The ADT client (`corelift/sap/adt.py`) refuses any request outside its read-only allowlist before a socket opens. One allowlisted call is a POST that reads the package tree. Paths with `.`/`..` segments and redirects are refused, so untrusted URIs cannot widen the allowlist and credentials never follow to another host.
- Nothing is written, locked, activated, transported or deployed in SAP or BTP. `sap-read` is granted only bound to the one system the user connected (`corelift/capabilities.py`); `offline-assess` and `network-evidence` are open; everything else fails closed.
- Pinned Cloudification evidence (`verification: cloudification-pinned`) classifies objects as released, classic, internal or not-recommended. It carries no remote (C2) contract or endorsed pathway, so a BTP sidecar is never derived from it alone. Objects absent from SAP's files stay unknown.
- `sap-screen-capture` is granted only with a statement the agent records as the user's, naming the transactions (`corelift/sap/screens.py` binds it to the connected system and the lifted scope). It is the one SAP access outside the read-only ADT allowlist: display-only is policy, not enforcement ([ADR 0001](adr/0001-screen-capture-through-sap-gui-for-html.md)). The demo system has no screens to capture.
- Discovery reads source only: no usage statistics (SCMON/SUSG), ATC results, screen layouts, flow logic or DDIC details yet. Screen behavior and dependencies are lexical hints. Treat every disposition as a candidate for an architect.
- This Python connector is a stopgap. The goscrub Go ADT backend is the planned single connector; it should emit the same `inventory.json` contract so the rest of the pipeline is unchanged.
- Verified against the synthetic ADT endpoint in `corelift/sap/mock.py` and SAP's published repository files. Not yet exercised against a real SAP system.
