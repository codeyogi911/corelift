# Third-party material

CoreLift's original code, synthetic examples and documentation are Apache-2.0; see LICENSE and NOTICE. Third-party material retains its original license.

## Vendored schemas

The two unmodified Agent Plugins 1.0.0 JSON Schemas in `evidence/` come from the [official schema site](https://agent-plugins.org/schemas). Their SHA-256 files pin the exact bytes. Upstream's [license policy](https://github.com/agentplugins/agent-plugins-spec/blob/main/LICENSE.md) assigns Apache-2.0 to schemas and software. The repository LICENSE supplies the license text; NOTICE records attribution. No upstream specification prose or artwork is copied.

## JavaScript dependencies

`package-lock.json` pins npm dependencies. The source repository does not vendor their source. `npm run build:ui` records every npm package that actually contributes code to either bundle using esbuild's dependency graph, then copies its license/notice text into `ui/generated/THIRD_PARTY_NOTICES.txt` and writes a machine-readable `bundle-licenses.json`. Optional Codex packages include both files. Build tooling and packages omitted by tree shaking are not redistributed in those bundles. Direct dependencies include the MCP TypeScript SDK, MCP Apps SDK and Ajv. The inventory records npm package license metadata; the full upstream license texts govern. MCP license files also contain Apache-2.0 transition notices alongside retained MIT terms, and those texts are copied intact. Transitive components retain their own terms.

Generated bundles must be distributed with their notices. Do not remove notices merely because minification preserves some inline comments. The Python runtime uses the standard library; `jsonschema` is an optional development dependency, not bundled.

## SAP references and visual assets

SAP guidance is linked to its public original sources. CoreLift does not bundle gated SAP documentation, SAP customer code, proprietary API catalogs or SAP artwork. Every `SYN_*` fixture and ABAP example is fictional. The interface uses original text/CSS and system fonts, with no copied brand images or externally hosted assets. The plugin icon in `assets/` is original artwork: `logo.svg` is its source and the PNGs are rendered from it.
