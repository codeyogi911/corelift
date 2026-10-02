import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import http from 'node:http';
import { transform } from 'esbuild';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { RESOURCE_URI, TOOL_NAME, ROOT, loadSnapshot, validateWorkspace } from '../shared.mjs';
import { startPreview } from '../preview.mjs';
import { safeSourceURL, routeFromContext, matchesApplication } from '../presentation.mjs';

async function connect(args = [], bundled = false) {
  const client = new Client({ name: 'corelift-protocol-check', version: '1.0.0' });
  const transport = new StdioClientTransport({ command: process.execPath, args: [path.join(ROOT, bundled ? 'ui/generated/server.mjs' : 'ui/server.mjs'), ...args], stderr: 'pipe' });
  await client.connect(transport);
  return { client, close: () => client.close() };
}

test('real SDK client discovers global entrypoint, empty-input tool and registered UI resource', async () => {
  const { client, close } = await connect();
  try {
    const { tools } = await client.listTools();
    assert.equal(tools.length, 1);
    const tool = tools[0];
    assert.equal(tool.name, TOOL_NAME);
    assert.equal(tool._meta.ui.resourceUri, RESOURCE_URI);
    assert.deepEqual(tool._meta['openai/ui'].entrypoints, [{ type: 'global' }]);
    assert.equal(tool.annotations.readOnlyHint, true);
    assert.equal(tool.annotations.openWorldHint, false);
    assert.equal(tool.inputSchema.additionalProperties, false);
    const result = await client.callTool({ name: TOOL_NAME, arguments: {} });
    assert.equal(result.isError, undefined);
    assert.equal(validateWorkspace(result.structuredContent), true);
    assert.deepEqual(result.structuredContent, JSON.parse(await loadSnapshot()));
    assert.match(result.content[0].text, /structured result/);
    assert.equal((await client.listResources()).resources[0].uri, RESOURCE_URI);
    const resource = (await client.readResource({ uri: RESOURCE_URI })).contents[0];
    assert.equal(resource.mimeType, 'text/html;profile=mcp-app');
    assert.deepEqual(resource._meta.ui.csp.connectDomains, []);
    assert.match(resource.text, /data-preview="false"/);
    assert.doesNotMatch(resource.text, /<script[^>]+src=/);
    const script = resource.text.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
    await transform(script, { loader: 'js' });
    await assert.rejects(client.callTool({ name: TOOL_NAME, arguments: { path: '/etc/hosts' } }));
    await assert.rejects(client.callTool({ name: 'deploy', arguments: {} }));
    await assert.rejects(client.readResource({ uri: 'file:///etc/hosts' }));
  } finally { await close(); }
});

test('bundled standalone server has equivalent protocol behavior', async () => {
  const { client, close } = await connect([], true);
  try { assert.deepEqual((await client.callTool({ name: TOOL_NAME, arguments: {} })).structuredContent, JSON.parse(await loadSnapshot())); }
  finally { await close(); }
});

test('imported synthetic report remains imported and snapshot is frozen', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'corelift-ui-import-'));
  const file = path.join(directory, 'assessment.json');
  const demo = JSON.parse(await loadSnapshot());
  await writeFile(file, JSON.stringify(demo.assessment));
  const { client, close } = await connect(['--assessment', file]);
  try {
    const first = (await client.callTool({ name: TOOL_NAME, arguments: {} })).structuredContent;
    assert.equal(first.mode, 'imported');
    assert.equal(first.rehearsal, null);
    assert.match(first.provenance_notice, /assertions/);
    await writeFile(file, '{}');
    assert.deepEqual((await client.callTool({ name: TOOL_NAME, arguments: {} })).structuredContent, first);
  } finally { await close(); await rm(directory, { recursive: true, force: true }); }
});

test('invalid selected import returns useful tool error and never demo fallback', async () => {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'corelift-ui-invalid-'));
  const file = path.join(directory, 'bad.json');
  await writeFile(file, '{"secret":"not-for-output"}');
  const { client, close } = await connect(['--assessment', file]);
  try {
    const result = await client.callTool({ name: TOOL_NAME, arguments: {} });
    assert.equal(result.isError, true); assert.equal(result.structuredContent, undefined);
    assert.match(result.content[0].text, /No demo substitution/);
    assert.doesNotMatch(JSON.stringify(result), /not-for-output/);
  } finally { await close(); await rm(directory, { recursive: true, force: true }); }
});

test('loopback preview only serves exact read routes and rejects unexpected origins', async () => {
  const preview = await startPreview({ port: 0 });
  try {
    const page = await fetch(preview.url + '/');
    assert.equal(page.status, 200);
    assert.equal(page.headers.get('cache-control'), 'no-store');
    assert.match(page.headers.get('content-security-policy'), /frame-ancestors 'none'/);
    assert.match(await page.text(), /data-preview="true"/);
    assert.equal((await fetch(preview.url + '/api/workspace')).status, 200);
    assert.equal((await fetch(preview.url + '/api/workspace?path=/etc/hosts')).status, 404);
    assert.equal((await fetch(preview.url + '/api/workspace', { method: 'POST' })).status, 405);
    assert.equal((await fetch(preview.url + '/api/workspace', { headers: { Origin: 'https://untrusted.example' } })).status, 403);
    const rejectedHost = await new Promise((resolve, reject) => {
      const request = http.get(preview.url + '/api/workspace', { headers: { Host: 'untrusted.example' } }, response => { response.resume(); resolve(response.statusCode); });
      request.on('error', reject);
    });
    assert.equal(rejectedHost, 403);
    assert.equal((await fetch(preview.url + '/scripts/corelift.py')).status, 404);
  } finally { preview.close(); }
});

test('source URLs and host routes are constrained independently of source strings', () => {
  for (const value of ['javascript:alert(1)', 'https://help.sap.com.evil.example/', 'https://user:pass@help.sap.com/', 'https://github.com/attacker/payload', 'http://help.sap.com/']) assert.equal(safeSourceURL(value), null);
  assert.equal(safeSourceURL('https://help.sap.com/docs/test'), 'https://help.sap.com/docs/test');
  assert.equal(routeFromContext({ 'openai/deepLink': { url: '//evil.example' } }), null);
  assert.equal(routeFromContext({ 'openai/deepLink': { url: '/plan' } }), 'plan');
  assert.equal(matchesApplication({ application_id: 'Z_PR_WORKBENCH', disposition: 'retain-on-stack-candidate' }, 'workbench'), true);
});

test('unsupported schema/version and malformed rehearsal fail browser/server schema', async () => {
  const value = JSON.parse(await loadSnapshot());
  value.workspace_version = '99.0.0'; assert.equal(validateWorkspace(value), false);
  value.workspace_version = '1.0.0'; value.read_only = 1; assert.equal(validateWorkspace(value), false);
  value.read_only = true; value.rehearsal = { passed: true }; assert.equal(validateWorkspace(value), false);
});

test('startup cancellation terminates exporter and does not connect or listen afterward', async () => {
  const { spawn } = await import('node:child_process');
  const { chmod } = await import('node:fs/promises');
  const directory = await mkdtemp(path.join(os.tmpdir(), 'corelift-ui-cancel-'));
  const fakePython = path.join(directory, 'slow-python');
  await writeFile(fakePython, `#!${process.execPath}\nrequire('node:fs').writeFileSync(process.env.CORELIFT_TEST_READY, String(process.pid)); setTimeout(() => {}, 60000);\n`);
  await chmod(fakePython, 0o700);
  try {
    for (const entry of ['server.mjs', 'preview.mjs']) {
      const ready = path.join(directory, entry + '.ready');
      const child = spawn(process.execPath, [path.join(ROOT, 'ui', entry)], { env: { ...process.env, CORELIFT_PYTHON: fakePython, CORELIFT_TEST_READY: ready }, stdio: ['pipe', 'pipe', 'pipe'] });
      let output = ''; child.stdout.on('data', data => { output += data; });
      const exited = new Promise(resolve => child.once('exit', (code, signal) => resolve({ code, signal })));
      let exporterPID;
      try {
        for (let count = 0; count < 150; count++) {
          try { exporterPID = Number(await readFile(ready, 'utf8')); break; } catch { await new Promise(resolve => setTimeout(resolve, 20)); }
        }
        assert.ok(exporterPID, 'exporter started before cancellation');
        child.kill('SIGTERM');
        const outcome = await Promise.race([exited, new Promise(resolve => setTimeout(() => resolve(null), 2000))]);
        assert.ok(outcome, 'startup must terminate after cancellation');
        assert.equal(outcome.code, 0);
        assert.equal(output, '');
        assert.throws(() => process.kill(exporterPID, 0), /ESRCH/);
      } finally { child.kill('SIGKILL'); child.stdin.destroy(); }
    }
  } finally { await rm(directory, { recursive: true, force: true }); }
});

test('optional relocated Codex package runs without source checkout or node_modules', async () => {
  const { execFile } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const run = promisify(execFile);
  const directory = await mkdtemp(path.join(os.tmpdir(), 'corelift-ui-package-'));
  const destination = path.join(directory, 'packages');
  let client;
  try {
    await run(process.env.CORELIFT_PYTHON || 'python3', [path.join(ROOT, 'scripts/build_packages.py'), '--with-ui', '--output', destination], { cwd: directory });
    const pluginRoot = path.join(destination, 'codex');
    const config = JSON.parse(await readFile(path.join(pluginRoot, 'mcp.json'), 'utf8'));
    const definition = config.mcpServers['corelift-workspace'];
    assert.equal(definition.type, 'stdio');
    assert.equal(definition.command, 'node');
    client = new Client({ name: 'relocated-package-check', version: '1.0.0' });
    await client.connect(new StdioClientTransport({ command: process.execPath,
      args: definition.args.map(value => value.replace('${PLUGIN_ROOT}', pluginRoot)),
      cwd: definition.cwd.replace('${PLUGIN_ROOT}', pluginRoot), stderr: 'pipe' }));
    assert.deepEqual((await client.callTool({ name: TOOL_NAME, arguments: {} })).structuredContent, JSON.parse(await loadSnapshot()));
    assert.match((await client.readResource({ uri: RESOURCE_URI })).contents[0].text, /CoreLift assessment workspace/);
  } finally { await client?.close(); await rm(directory, { recursive: true, force: true }); }
});
