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

Its onboarding skill walks the user through connecting. To pick up a newer `main`, run `codex plugin marketplace upgrade corelift`, then `codex plugin add corelift@corelift` again. `codex plugin list | grep corelift` should show one enabled CoreLift; a second copy (for example a local marketplace pointing at a clone) starts a second `corelift-sap` server, so remove or disable the one you are not testing.

## Try it on the demo system

In an empty project folder, start `codex` (or Claude Code) and ask: "lift and shift my SAP custom code using the demo system". The agent switches the session to the fictional demo system, lifts package `ZDEMO_PURCHASING` into `corelift-workspace/`, shows a table of four applications and drafts target code with a `REVIEW.md` per application. `codex exec` runs the same prompt non-interactively.

## Connect

`sap_connection_status` returns `connect_command`, the exact command with the installed plugin path; agents hand it to the user. `<plugin-root>` below is that path's folder.

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

`corelift_lift` runs all four. In Claude Code the skill then dispatches one `sap-migration-engineer` subagent per app to draft target code in `migration/<APP>/target/` with a `REVIEW.md`. A workspace carries its own `.gitignore` because it holds customer source.

## Boundaries

- The ADT client (`corelift/sap/adt.py`) refuses any request outside its read-only allowlist before a socket opens. One allowlisted call is a POST that reads the package tree. Paths with `.`/`..` segments and redirects are refused, so untrusted URIs cannot widen the allowlist and credentials never follow to another host.
- Nothing is written, locked, activated, transported or deployed in SAP or BTP. `sap-read` is granted only bound to the one system the user connected (`corelift/capabilities.py`); `offline-assess` and `network-evidence` are open; everything else fails closed.
- Pinned Cloudification evidence (`verification: cloudification-pinned`) classifies objects as released, classic, internal or not-recommended. It carries no remote (C2) contract or endorsed pathway, so a BTP sidecar is never derived from it alone. Objects absent from SAP's files stay unknown.
- Discovery reads source only: no usage statistics (SCMON/SUSG), ATC results, screen behavior or DDIC details yet. Dependencies are lexical hints. Treat every disposition as a candidate for an architect.
- This Python connector is a stopgap. The goscrub Go ADT backend is the planned single connector; it should emit the same `inventory.json` contract so the rest of the pipeline is unchanged.
- Verified against the synthetic ADT endpoint in `corelift/sap/mock.py` and SAP's published repository files. Not yet exercised against a real SAP system.
