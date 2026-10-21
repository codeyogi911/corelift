# CoreLift

CoreLift assesses a customer's custom SAP applications and plans how each one leaves, stays on or retires from the ERP core, with every decision traced to evidence a reviewer can check.

## Systems

**Source system**:
The customer's current SAP system (ECC or S/4HANA) that holds the custom applications.
_Avoid_: legacy system, old SAP

**Target**:
The SAP release the plan is assessed against, identified by family, edition, release and FPS.
_Avoid_: destination, new system

**ERP core**:
The standard SAP transactions and authoritative business data, which stay in ERP.
_Avoid_: backend, the SAP side

**Extension**:
Customer-built logic or data that adds to the ERP core, on-stack or on BTP.
_Avoid_: customization, Z-code (as a general term)

**Sidecar**:
An extension that runs on BTP beside the ERP core and reaches it only through endorsed remote pathways.
_Avoid_: microservice, cloud app

**Connection**:
A customer-authorized link from CoreLift to one source system, scoped to named operations. Today: read-only ADT reads, made by the user with `corelift connect` or the host's plugin settings.
_Avoid_: login, integration, credentials

## Evidence

**Inventory**:
A normalized export describing the source system's custom applications, their code, usage, screens, datasets and dependencies.
_Avoid_: dump, extract, scan

**Application**:
One unit of custom functionality in the inventory that receives its own disposition.
_Avoid_: program, object, report (unless it is literally a report)

**API evidence**:
Target-pinned records of each SAP API's classification, release contract and endorsed operations.
_Avoid_: API list, API catalog

**Source record**:
A cited policy or document with its URL, check date, revision and scope.
_Avoid_: reference, link

**Extensibility level**:
SAP's A to D rating of a dependency: released, nominated classic, internal, not recommended. The weakest dependency governs the application.
_Avoid_: tier (the legacy model)

**Release contract**:
The use a released API permits: C0 extension, C1 local, C2 remote.
_Avoid_: API version, visibility

**Wrapper**:
Custom code that hides a weaker dependency behind its own interface while keeping that dependency's level.
_Avoid_: adapter, facade

## Outcomes

**Assessment**:
The evidence-backed result for an inventory: dispositions, dependencies, unknowns, draft plan and run record.
_Avoid_: report (the rendered file is a report; the content is the assessment), analysis

**Disposition**:
The candidate outcome for one application, such as retain-core, btp-sidecar-candidate, retain-on-stack-candidate, rebuild-candidate, retire-candidate or investigate.
_Avoid_: recommendation, verdict, placement

**Unknown**:
A missing fact that blocks a disposition until someone investigates it. An unknown is never evidence of impossibility.
_Avoid_: gap, warning

**Migration plan**:
The draft, unapproved sequence of stages from discovery through cutover, verification and rollback.
_Avoid_: roadmap, runbook

**Rehearsal**:
A run of plan steps against a mock target to prove atomicity, replay, reconciliation and rollback before any real target exists.
_Avoid_: dry run, simulation, test migration

## Execution boundary

**Capability**:
A named operation CoreLift may perform, such as offline assessment. Offline assessment and public evidence download are open, SAP reads need a system binding from the user's connection, screen capture needs the user's approval of named transactions, and everything else is denied until a provider implements it.
_Avoid_: permission, feature

**Provider**:
The component that performs a capability against a real system and enforces its approval, checkpoint, rollback and verification.
_Avoid_: connector (for the enforcing part), driver

**Approval**:
A recorded human decision bound to one target, system, operation and artifact.
_Avoid_: consent, sign-off, OK

**Host package**:
CoreLift built for one agent host (Codex, Claude Code, Cursor) with identical engine, schemas and skills.
_Avoid_: plugin build, distribution

**Workspace**:
The read-only view of an assessment shown inside a host or local preview.
_Avoid_: dashboard, UI app

## Lift and shift

**Lift**:
The read-only pipeline over one connection: discover custom code, pin API evidence, assess, write migration briefs.
_Avoid_: scan, import, migration (nothing moves during a lift)

**Lift workspace**:
The local folder a lift writes (inventory, source, evidence, assessment, briefs, drafted targets). Holds customer source; never committed. Distinct from the read-only assessment Workspace.
_Avoid_: project, output folder

**Migration brief**:
The per-application hand-off (`migration/<APP>/BRIEF.md`) telling an agent the disposition, target pattern, dependencies with SAP successors, unknowns and done criteria.
_Avoid_: ticket, task, prompt

**Reference screenshot**:
A screenshot of one transaction of the source system, taken in display mode with the user's approval, that a target UI is reviewed against.
_Avoid_: screen capture (the step), mockup

**Target stack**:
Where an application's side-by-side code is drafted, described by a stack profile: SAP BTP with CAP by default, ABAP Cloud, AWS, Google Cloud, Azure or a customer's own. It never changes a disposition.
_Avoid_: platform, cloud, target (the SAP release)

**Stack profile**:
The Markdown file describing one target stack in fixed sections (When it fits, Building blocks, Calling SAP, Tests, Done when).
_Avoid_: template, preset

**Checkpoint**:
One small, reviewable step of a shift, named in a few words and closed only when its gates hold on the current code.
_Avoid_: milestone, task, stage (stages belong to the migration plan)

**Gate**:
One verdict a checkpoint needs: behavior, screen review, two independent reviews and approval. A code change makes it stale; a missing tool leaves it blocked, never passed.
_Avoid_: check, step

**Delegation**:
The user's recorded words letting agents approve checkpoints of named applications.
_Avoid_: autopilot, auto-approve

**Lesson**:
An accepted correction from a checkpoint, kept in the workspace's `LESSONS.md` for later checkpoints and apps.
_Avoid_: memory, note

**Shift**:
An agent drafting one application's target code from its migration brief on the chosen target stack, checkpoint by checkpoint, inside the lift workspace for human review. Never deployed or written to SAP.
_Avoid_: migrate, deploy, convert
