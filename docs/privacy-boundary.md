# Local evidence and host disclosure

CoreLift 0.3.0 separates a full local workspace from its MCP response. This is an output boundary for CoreLift's server, not a sandbox around the AI host or the user's computer. Local stdio transport does not make information sent to an AI host local-only.

## What each action sends

| Selected action | Read locally | Returned to the MCP host |
| --- | --- | --- |
| Open bundled demo | Public fictional fixtures and synthetic rehearsal | Full fictional assessment, sources, demo checks and workspace metadata |
| Open an imported report, default | One explicitly selected normalized local report; validated and frozen in server memory | Fixed format/version, imported, read-only and withheld status; no report contents or counts |
| Open imported report with separate `--share-summary` startup consent | Same local report | Exactly three numbers: applications, applications with unknowns, blocked stages; plus fixed disclosure/version metadata and explanatory text |
| Read the UI resource or tool/resource listings | Bundled public UI and schemas | Static UI, public schemas, capabilities and descriptions; no report values |
| Invalid report | Bounded attempted local read | Fixed error text; no file contents, filename or path echoed by the server |
| Run standalone CLI or loopback preview | Selected local exports/report | Nothing through CoreLift MCP; the full report is visible in the local terminal/files/browser |

The three counts are assertions derived from imported decisions and stages, not proof of SAP coverage or successful verification. Counts may themselves be sensitive. Default import responses do not even disclose the number of applications. No imported source, object identifiers, filename, hash, release, screen behavior, ownership, detailed evidence or recommendations are placed in MCP text, `structuredContent`, `_meta`, resource content or server diagnostics. Raw ABAP is never part of this projection.

## Review locally first

Use your own local terminal and browser for detailed private review. Keep original exports and generated reports outside the public checkout and package roots, in a directory with agreed ownership, retention and access. The normalized report retains detailed evidence; this change does not redact or delete local files. The preview serves the full report on `127.0.0.1`, with no authentication; local processes or browser extensions with access may read it. Close the preview when finished.

An AI assistant's shell tool output, file read, attachment, screenshot or browser inspection can send private information to that assistant. Do not ask the assistant to inspect private files or capture the full local preview unless that separate disclosure is authorized. The CLI is intentionally detailed and its errors may include local paths or input context. The MCP projection does not protect a direct CLI invocation by another host tool. Host launch configuration and process arguments also contain the selected report path; choose a non-sensitive alias where possible. CoreLift cannot govern the host's independent filesystem permissions, logging, retention or model processing.

For normalized exports, the user can run `assess --output <new-local-folder>` in their own terminal to write the full JSON and Markdown reports locally. See the CLI quick start and input contracts. This prototype does not yet parse arbitrary SAP export formats.

## Separate disclosure choice

For an MCP client, the default imported-report startup is:

```sh
node ui/generated/server.mjs --assessment /absolute/path/assessment.json
```

Its sidebar explains what is withheld and directs the user to the local CLI/preview. The normal bundled demo remains fully navigable. There is no tool argument or sidebar control to enable sharing.

Only after explicit authorization to send the three counts to the chosen host, configure:

```sh
node ui/generated/server.mjs --assessment /absolute/path/assessment.json --share-summary
```

This flag cannot be used without a selected report. It never permits detailed evidence or source transmission. Permission to connect to SAP, possession of credentials, an approval field inside an import or the presence of a local file does not authorize disclosure. Do not add this flag on the user's behalf based on connection consent. The shipped MCP configuration uses only the bundled demo and contains no sharing flag or report path.

The report and disclosure mode are fixed for that process. Reload repeats the same result. Restart without `--share-summary` to stop future count disclosure. Previously transmitted information cannot be recalled from the host by restarting CoreLift. Local file deletion and host retention are separate responsibilities.

## Scope and verification

Synthetic planted-marker tests cover source, generated and relocated-package stdio servers, text/structured results, metadata, resources, startup errors and server stderr. Strict output schemas reject full imported workspaces and unexpected summary fields. DOM-level tests cover full demo rendering, switching to disclosure status without stale details, rejection of full imported host payloads and full local preview behavior. These are not pixel or actual host lifecycle tests.

No live SAP connector, credentials, new ATC run, monitor activation, customer upload, BTP resource or deployment is introduced. Before a real pilot, confirm the installed version includes this boundary; a prepared source/package update does not replace an already installed older plugin.
