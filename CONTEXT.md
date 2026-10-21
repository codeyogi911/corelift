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
A customer-authorized link from CoreLift to one source system, scoped to named operations. Planned; no connection provider exists yet.
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
A named operation CoreLift may perform, such as offline assessment. Every capability other than offline assessment is denied until a provider implements it.
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
