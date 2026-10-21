---
id: sap-btp-cap
name: SAP BTP with CAP
placement: side-by-side
default: true
---

## When it fits

The usual clean-core target. Pick it when the app owns its own data or UI, reads or updates ERP only through released remote APIs, and the customer runs (or plans) SAP BTP.

## Building blocks

- A CAP project (Node.js by default; Java if the customer standardizes on it): `package.json`, `db/` for the extension-owned entities, `srv/` for services, `app/` for a Fiori elements UI when the original had screens.
- SAP HANA Cloud or the CAP default database for extension data; ERP stays the system of record for ERP data.
- XSUAA or SAP Cloud Identity Services roles that mirror the original authorization checks.

## Calling SAP

Import the released remote API named in the brief as a CAP remote service (`cds import`) and call it through a BTP destination. Use only APIs whose remote (C2) release the brief or SAP's API documentation confirms; anything else stays an open question in `REVIEW.md`.

## Tests

`npm test` with CAP's test helpers (`cds.test`), mocking the remote ERP service. One test per business rule found in the original source; a screen's validations and messages become service-level tests.

## Done when

- `cds compile srv` succeeds and `npm test` passes locally
- every ERP call goes through an imported remote service, never a direct table or RFC
- the Fiori UI (if any) shows every field, action and message of the reference screenshots
