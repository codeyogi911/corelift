---
name: connect-sap
description: Connect CoreLift to the user's SAP system, check the connection, or switch to the demo system. Use at first run, when a CoreLift tool reports no SAP system, or when the user asks to connect, reconnect or disconnect SAP.
---

Connecting is the only step the user does by hand. Keep it to one action for them.

1. Call `sap_connection_status`. If `configured` is true and `reachable` is true, say which system is connected (URL, client, user, components) and hand over to the `lift-and-shift-sap` skill. Done.
2. Otherwise offer two paths in one short message:
   - **Your system**: the user runs this in their own terminal, which asks for URL, client, user and a hidden password, tests the connection read-only and saves it owner-only in `~/.corelift/`:
     `python3 "<plugin-root>/scripts/corelift.py" connect`
     The plugin root is the folder that contains `skills/`: from this SKILL.md go up two folders. In Claude Code the user can instead fill the plugin's SAP settings (`/plugin` → CoreLift → configure) and restart.
   - **Try it first**: call `sap_use_demo_system` for a fictional ECC system with package `ZDEMO_PURCHASING`.
3. Passwords travel only through the user's terminal or the host's secure settings prompt. If the user pastes a password into chat, tell them to change it and use the terminal command instead.
4. After the user says they connected, call `sap_connection_status` again. The step is done when it reports `reachable: true`.

Connection failures and their fix:
- 401/403: wrong user, password or client, or the user lacks ADT display authorization (`S_ADT_RES`, `S_DEVELOP` with activity 03).
- 404 on `/sap/bc/adt/discovery`: the ADT ICF services are not active (`SICF` → `/sap/bc/adt`).
- TLS errors: rerun `connect --ca-file <company-ca.pem>`; `--insecure-skip-tls-verify` only for a sandbox.

To disconnect: `python3 "<plugin-root>/scripts/corelift.py" disconnect`.
