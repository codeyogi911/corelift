---
id: aws
name: AWS
placement: side-by-side
default: false
---

## When it fits

The customer standardizes on AWS and the app can live beside ERP: it owns its own data or UI and reaches ERP only through released remote APIs. Clean core is about how the extension touches SAP, not where it runs.

## Building blocks

- AWS Lambda or containers on Amazon ECS/EKS, with Amazon DynamoDB or Amazon RDS for extension data and Amazon API Gateway in front.
- TypeScript on Node.js by default, infrastructure as code in the customer's tool of choice (the brief's tests must not need a cloud account).
- Roles from Amazon Cognito or the customer's identity provider that mirror the original authorization checks.

## Calling SAP

Call only the released remote APIs (OData or SOAP with a remote C2 release) the brief lists, over HTTPS through the customer's approved network path and a technical user with least privilege. No RFC to unreleased function modules, no direct database access, no generic proxy. Unconfirmed remote release stays an open question in `REVIEW.md`.

## Tests

Unit tests with the runtime's standard test runner, with the SAP API mocked from its published metadata. One test per business rule found in the original source.

## Done when

- the tests pass locally without a cloud account or SAP connection
- every SAP call goes through one client module per released API
- the UI (if any) shows every field, action and message of the reference screenshots
