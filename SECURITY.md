# Security

CoreLift is an early local prototype. It has no supported production/customer connector, deployment executor or production security assurance. The current maintained version is the latest main branch.

Do not place credentials, customer exports or exploitable sensitive details in public issues. Use GitHub's private vulnerability reporting on this repository when available. If private reporting is unavailable, open a minimal issue requesting a private reporting channel without the sensitive details. Reports are handled on a best-effort basis; no response-time commitment is made.

Keep the local preview bound to loopback. Plugin installation runs local Node/Python code under the host's permissions; read-only MCP annotations are not an OS sandbox. Review code and host permissions before loading any plugin. A future connector requires explicit scope, enforced capabilities, input/output minimization and evidence of the supported SAP pathway.
