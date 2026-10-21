---
name: shift-sap-app
description: Draft one lifted SAP app on its target stack through CoreLift's checkpoint loop with behavior, screen, review and approval gates. Use for each app being shifted in a CoreLift workspace.
---

You orchestrate one application, `migration/<APP>/`. The builder drafts, reviewers judge in fresh contexts, and you record every verdict with `corelift_gate`. A failed gate sends the work back to the builder; you never record a pass you did not see.

## Steps

1. **Plan checkpoints.** Read `BRIEF.md`, `../../target-stack.md` and `../../LESSONS.md`. Propose 2 to 6 checkpoints of a few words each, smallest first (a skeleton, then each business rule or screen), and mark `screens: true` on checkpoints that add UI. Call `corelift_checkpoint_plan`. Done when the plan is saved; show it to the user only when they review checkpoints themselves.
2. **Build one checkpoint.** In Claude Code dispatch the `sap-migration-engineer` subagent with the brief path and the checkpoint; elsewhere do it yourself. Done when the builder reports the checkpoint's tests and their result.
3. **Behavior gate.** Record `behavior` by `builder`: `pass` with the passing test command and count, `fail` with the failures, or `blocked` when the stack's tests need a system you do not have (ABAP Unit). A fail goes back to step 2.
4. **Screen gate** (checkpoints with `screens: true`). Dispatch the `sap-migration-reviewer` subagent in screen mode with the reference screenshots from the brief. Record `screen-review` with its verdict and every difference it lists. Differences that code can fix are fails.
5. **Reviews.** Dispatch two `sap-migration-reviewer` subagents separately, `reviewer-1` against the brief and stack profile, `reviewer-2` against the original ABAP behavior. Record `review-a` and `review-b`. Any finding is a fail: back to step 2, then every gate again on the new code.
6. **Approval.** When the user reviews checkpoints, show the diff summary and record `approval` by `user` with their words. When the user delegated this app, record it by `delegated`. Turn each correction the user makes into a lesson with `corelift_record_lesson`.
7. **Close.** Call `corelift_checkpoint_close`. Done when it returns `closed` or `closed-unverified`; continue with `next` until it is null.

Without subagents (other hosts), run each reviewer as a separate pass that rereads the files from disk and ignores your earlier reasoning, and name the reviewers `reviewer-1` and `reviewer-2`.
