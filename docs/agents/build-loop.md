# Build loop reference

Detail for the loop in [AGENTS.md](../../AGENTS.md). Read the section the current step points to.

## Seams

Test at these public boundaries; a test that reaches past them breaks on refactors that keep behaviour.

| Seam | Entry point | Existing tests |
| --- | --- | --- |
| CLI | `python3 -m corelift demo / assess / rehearse-demo` (`corelift/__main__.py: main`) | `tests/test_corelift.py` BoundaryTests |
| Assessment engine | `corelift.engine.assess(inventory, evidence, sources)` | AssessmentTests |
| Input contracts | `corelift.contracts.validate` against `schemas/*.schema.json` | AssessmentTests, `scripts/check_schemas.py` |
| Capability boundary | `corelift.capabilities.require_capability(name, approval)` | BoundaryTests |
| Rehearsal target | `corelift.rehearsal.MockNotesTarget` | RehearsalTests |
| Workspace snapshot and MCP server | `corelift.workspace.snapshot`, `ui/server.mjs` tools and resources | `tests/test_workspace.py`, `ui/tests/` |
| Host packages | `scripts/build_packages.build`, packaged `scripts/corelift.py` | PackageTests, `scripts/check_release.py` |
| Agent docs | `scripts/check_agent_docs.problems` | `tests/test_agent_docs.py` |
| SAP read connector | `corelift.sap.adt.ADTClient`, `allowed(method, path)` against `corelift.sap.mock` | `tests/test_sap.py` ReadOnlyClientTests |
| Discovery and evidence | `corelift.sap.discover.discover`, `corelift.sap.evidence.build` | DiscoveryTests, EvidenceAndAssessmentTests |
| Lift pipeline | `corelift.sap.pipeline.lift` and its steps; `python3 -m corelift connect / status / lift` | PipelineTests, ProfileTests |
| SAP MCP server | `corelift.mcp_server.handle`, `python3 -m corelift mcp` (stdio) | MCPServerTests |
| Screen capture | `corelift.sap.screens.plan / record`, `corelift.sap.discover.program_screens` | `tests/test_flow.py` ScreenCaptureTests, `tests/test_sap.py` DiscoveryTests |
| Target stacks | `corelift.stacks.profiles / choose`, `corelift.sap.pipeline.plan` | TargetStackTests |
| Checkpoint loop | `corelift.checkpoints.plan / gate / close / delegate / lesson` | CheckpointLoopTests |
| Skills and subagents | `skills/*/SKILL.md`, `agents/*.md` against the MCP tool list | SkillTests, MCPFlowTests |
| Plugin manifests | `.claude-plugin/plugin.json`, root `plugin.json` + `mcp.json`, marketplaces | PackageTests, `scripts/check_schemas.py`, `claude plugin validate .` |

A new connector or plugin surface adds a row here in the same change. If the code you need to test has no seam, that is a design finding: say so in the PR and propose the seam rather than testing internals.

## Review

Run the two axes in separate contexts so one cannot mask the other. Pin the fixed point first (`git merge-base origin/main HEAD`) and confirm the diff is non-empty.

**Standards prompt.** Give the reviewer `git diff <base>...HEAD`, the commit list, AGENTS.md, CONTRIBUTING.md and this baseline. Ask it to report, per hunk, (a) each breach of a documented rule, citing file and rule, and (b) each smell it spots, quoting the hunk. Documented repo rules win over the baseline; smells are judgement calls. Under 400 words.

Smell baseline: Mysterious Name, Duplicated Code, Feature Envy, Data Clumps, Primitive Obsession, Repeated Switches, Shotgun Surgery, Divergent Change, Speculative Generality, Message Chains, Middle Man, Refused Bequest. CoreLift-specific checks: a boundary from AGENTS.md weakened, a claim stronger than its evidence, a fixture that looks like real customer data, a new dependency without license review.

**Spec prompt.** Give the reviewer the diff, the commit list and the spec text. Ask for (a) requirements missing or partial, (b) behaviour nobody asked for, (c) requirements that look implemented but wrong, each quoting the spec line. Under 400 words.

Report the two axes side by side under `## Standards` and `## Spec` in the PR body, with the worst finding of each. Keep them unranked against each other.

## Bugs

Work in this order and finish each phase before the next.

1. **Loop.** Build one command that drives the real code path and asserts the user's exact symptom, then run it and see it go red. It must be deterministic, take seconds and run unattended. Usual shapes here: a failing unittest, `python3 -m corelift assess` on a minimal synthetic fixture diffed against expected JSON, or an MCP call from `ui/tests/`. If no such loop can be built, stop and ask for a redacted artifact or access, listing what you tried.
2. **Reproduce and minimise.** Confirm the failure is the one reported. Cut fixture fields, applications and steps one at a time until every remaining part is load-bearing.
3. **Hypothesise.** Write 3 to 5 ranked, falsifiable hypotheses ("if X is the cause, changing Y makes it pass"). Share them before testing when the user is around.
4. **Instrument.** One variable per probe. Tag temporary logs `[DEBUG-<4 hex>]` so one grep removes them.
5. **Fix.** Turn the minimal repro into a failing test at the right seam, watch it fail, fix, watch it pass, rerun the original loop.
6. **Clean up.** No `[DEBUG-` tags left, throwaway harnesses deleted, and the confirmed hypothesis stated in the commit message.

Redact credentials, hostnames and customer identifiers from every command and output you show.
