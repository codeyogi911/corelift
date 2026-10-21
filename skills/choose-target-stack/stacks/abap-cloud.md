---
id: abap-cloud
name: ABAP Cloud on S/4HANA
placement: on-stack
default: false
---

## When it fits

The app needs tight, transactional access to ERP data and the target is S/4HANA 2022 or later (private cloud or on-premise) or S/4HANA Cloud Public Edition. For an ECC source this lands after the S/4HANA conversion.

## Building blocks

- Classes, CDS view entities, behavior definitions (RAP) and service bindings in abapGit layout under `target/src/`, language version ABAP for Cloud Development.
- A Fiori elements UI from the RAP service when the original had screens.
- Custom tables only for extension-owned data.

## Calling SAP

Released local (C1) APIs only: released CDS views, RAP business objects, released classes. Replace direct table access with the released CDS successors the brief lists.

## Tests

ABAP Unit test classes (`*.clas.testclasses.abap`) with test doubles for released APIs. They cannot run outside SAP, so the behavior gate stays blocked until a human runs them; say so instead of claiming a pass.

## Done when

- every object declares ABAP for Cloud Development and uses only APIs the brief lists as released
- ABAP Unit tests exist for each business rule of the original
- `REVIEW.md` names the ATC clean-core check variant to run before transport
