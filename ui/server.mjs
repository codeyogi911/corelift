import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema, ListResourcesRequestSchema, ReadResourceRequestSchema, ErrorCode, McpError } from '@modelcontextprotocol/sdk/types.js';
import { RESOURCE_MIME_TYPE } from '@modelcontextprotocol/ext-apps/server';
import { loadSnapshot, parseArgs, resourceHTML, resultFor, schema, RESOURCE_URI, TOOL_NAME } from './shared.mjs';

const shutdown = new AbortController();
let server;
for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => { shutdown.abort(); void server?.close(); });
try {
  const { assessment } = parseArgs(process.argv.slice(2));
  let snapshotJSON, loadError;
  try { snapshotJSON = await loadSnapshot(assessment, shutdown.signal); } catch (error) { loadError = error.message; }
  if (shutdown.signal.aborted) throw new Error("cancelled");
  const html = await resourceHTML();
  if (shutdown.signal.aborted) throw new Error("cancelled");
  server = new Server({ name: 'corelift-local-workspace', version: '0.2.0' }, {
    capabilities: { tools: {}, resources: {} },
    instructions: 'CoreLift inspects one frozen local assessment. Imported report assertions are unverified. No SAP/BTP connection, write, approval or deployment tools exist. Use structured/text results if this host cannot render MCP Apps.',
  });
  server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: [{
    name: TOOL_NAME, title: 'CoreLift', description: 'Open the read-only CoreLift assessment workspace for the configured local report or synthetic demo.',
    inputSchema: { type: 'object', properties: {}, additionalProperties: false },
    outputSchema: schema,
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false },
    _meta: { ui: { resourceUri: RESOURCE_URI, visibility: ['model', 'app'] }, 'openai/ui': { entrypoints: [{ type: 'global' }] } },
  }] }));
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    if (request.params.name !== TOOL_NAME) throw new McpError(ErrorCode.InvalidParams, 'Unknown read-only tool.');
    const args = request.params.arguments ?? {};
    if (Object.keys(args).length) throw new McpError(ErrorCode.InvalidParams, 'This entrypoint accepts empty arguments only.');
    if (loadError) return { isError: true, content: [{ type: 'text', text: loadError }] };
    return resultFor(snapshotJSON);
  });
  server.setRequestHandler(ListResourcesRequestSchema, async () => ({ resources: [{ uri: RESOURCE_URI, name: 'CoreLift assessment workspace', mimeType: RESOURCE_MIME_TYPE }] }));
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    if (request.params.uri !== RESOURCE_URI) throw new McpError(ErrorCode.InvalidParams, 'Unknown workspace resource.');
    return { contents: [{ uri: RESOURCE_URI, mimeType: RESOURCE_MIME_TYPE, text: html,
      _meta: { ui: { prefersBorder: false, csp: { connectDomains: [], resourceDomains: [], frameDomains: [] } },
        'openai/ui': { preferredDisplayMode: 'fullscreen', availableDisplayModes: ['inline', 'fullscreen'] } } }] };
  });
  await server.connect(new StdioServerTransport());
} catch {
  if (!shutdown.signal.aborted) process.stderr.write('CoreLift MCP could not start. Build the UI and check local startup arguments.\n');
  process.exitCode = shutdown.signal.aborted ? 0 : 1;
}
