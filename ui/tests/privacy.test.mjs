import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm, readFile } from 'node:fs/promises';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import os from 'node:os';
import path from 'node:path';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { ROOT, TOOL_NAME, RESOURCE_URI, loadSnapshot, hostResultFor, validateHostOutput, parseArgs } from '../shared.mjs';
import validateHostSummary from '../generated/validate-host-summary.mjs';
import { startPreview } from '../preview.mjs';

const marker = 'PRIVATE_SYNTHETIC_MARKER_642985'; // Fictional planted data, never customer data.
const withheld = { host_summary_version: '1.0.0', mode: 'imported', read_only: true, disclosure: 'withheld', counts: null };
async function fixture() {
  const directory = await mkdtemp(path.join(os.tmpdir(), 'corelift-privacy-'));
  const file = path.join(directory, `${marker}.json`);
  const demo = JSON.parse(await loadSnapshot());
  const report = JSON.parse(JSON.stringify(demo.assessment).replaceAll('Z_PR_WORKBENCH', marker));
  report.decisions[0].reason = marker;
  report.decisions[0].risks.push(marker);
  report.sources[0].title = marker;
  report.run_record.limitations.push(marker);
  await writeFile(file, JSON.stringify(report));
  return { directory, file, report, clean: () => rm(directory, { recursive: true, force: true }) };
}
async function connect(entry, args) {
  const client = new Client({ name: 'privacy-boundary-check', version: '1.0.0' });
  const transport = new StdioClientTransport({ command: process.execPath, args: [entry, ...args], stderr: 'pipe' });
  let stderr = '';
  transport.stderr?.on('data', data => { stderr += data; });
  await client.connect(transport);
  return { client, stderr: () => stderr, close: () => client.close() };
}
function aggregate(report) {
  return { ...withheld, disclosure: 'aggregate-counts', counts: {
    applications: report.decisions.length,
    applications_with_unknowns: report.decisions.filter(d => d.unknowns.length).length,
    blocked_stages: report.migration_plan.stages.filter(s => s.status.startsWith('blocked')).length,
  } };
}

test('local imported snapshot retains details; host projection is fixed unless separately opted in', async () => {
  const f = await fixture();
  try {
    const snapshot = await loadSnapshot(f.file);
    assert.match(snapshot, new RegExp(marker));
    assert.equal(JSON.parse(snapshot).mode, 'imported'); // report.synthetic cannot bypass policy.
    assert.deepEqual(hostResultFor(snapshot).structuredContent, withheld);
    assert.deepEqual(hostResultFor(snapshot, { shareSummary: true }).structuredContent, aggregate(f.report));
    const changed = JSON.parse(snapshot);
    changed.assessment.decisions = changed.assessment.decisions.slice(0, 1);
    assert.deepEqual(hostResultFor(JSON.stringify(changed)), hostResultFor(snapshot));
    assert.equal(validateHostOutput(JSON.parse(snapshot)), false, 'full imported output forbidden by declared tool schema');
    assert.equal(validateHostOutput(JSON.parse(await loadSnapshot())), true, 'bundled demo still usable');
  } finally { await f.clean(); }
});

for (const bundled of [false, true]) for (const share of [false, true]) {
  test(`${bundled ? 'bundled' : 'source'} MCP imported output exposes ${share ? 'only explicit aggregate counts' : 'fixed metadata only'} across every response surface`, async () => {
    const f = await fixture();
    const { client, close, stderr } = await connect(path.join(ROOT, bundled ? 'ui/generated/server.mjs' : 'ui/server.mjs'), ['--assessment', f.file, ...(share ? ['--share-summary'] : [])]);
    try {
      const result = await client.callTool({ name: TOOL_NAME, arguments: {} });
      assert.deepEqual(result.structuredContent, share ? aggregate(f.report) : withheld);
      assert.equal(result._meta, undefined);
      assert.equal(validateHostOutput(result.structuredContent), true);
      const surfaces = [result, await client.listTools(), await client.listResources(), await client.readResource({ uri: RESOURCE_URI }), client.getInstructions()];
      for (const surface of surfaces) {
        const serialized = JSON.stringify(surface);
        for (const privateValue of [marker, f.file, f.directory, JSON.parse(await loadSnapshot(f.file)).snapshot_hash]) assert.ok(!serialized.includes(privateValue), 'private value absent from host surfaces');
      }
      for (const args of [{ shareSummary: true }, { approval: 'connect and disclose' }, { assessment: f.file }]) await assert.rejects(client.callTool({ name: TOOL_NAME, arguments: args }));
      await writeFile(f.file, '{}');
      assert.deepEqual(await client.callTool({ name: TOOL_NAME, arguments: {} }), result, 'session disclosure and report stay fixed');
      assert.doesNotMatch(stderr(), new RegExp(marker));
    } finally { await close(); await f.clean(); }
  });
}

test('summary schema rejects extra data, mismatched disclosure, noninteger and negative counts', () => {
  const good = { ...withheld, disclosure: 'aggregate-counts', counts: { applications: 3, applications_with_unknowns: 1, blocked_stages: 2 } };
  for (const value of [withheld, good]) assert.equal(validateHostSummary(value), true);
  for (const value of [{ ...withheld, assessment: marker }, { ...withheld, counts: good.counts }, { ...good, counts: { ...good.counts, owner: marker } }, { ...good, counts: { ...good.counts, applications: -1 } }, { ...good, counts: { ...good.counts, applications: 1.5 } }, { ...withheld, disclosure: 'full' }, { ...withheld, host_summary_version: '99' }]) {
    assert.equal(validateHostSummary(value), false); assert.equal(validateHostOutput(value), false);
  }
});

test('disclosure requires explicit local import startup option; connection-shaped options never grant it', () => {
  assert.throws(() => parseArgs(['--share-summary']));
  assert.throws(() => parseArgs(['--assessment', 'a.json', '--share-summary'], true));
  assert.throws(() => parseArgs(['--assessment', 'a.json', '--connected']));
  assert.throws(() => parseArgs(['--assessment', 'a.json', '--share-summary', '--share-summary']));
  assert.equal(parseArgs(['--assessment', 'a.json']).shareSummary, false);
  assert.equal(parseArgs(['--assessment', 'a.json', '--share-summary']).shareSummary, true);
});

test('invalid imported report with summary consent has fixed non-echoing error', async () => {
  const f = await fixture();
  await writeFile(f.file, JSON.stringify({ private: marker }));
  const { client, close, stderr } = await connect(path.join(ROOT, 'ui/generated/server.mjs'), ['--assessment', f.file, '--share-summary']);
  try {
    const result = await client.callTool({ name: TOOL_NAME, arguments: {} });
    assert.equal(result.isError, true); assert.equal(result.structuredContent, undefined);
    assert.doesNotMatch(JSON.stringify(result) + stderr(), new RegExp(marker));
  } finally { await close(); await f.clean(); }
});

test('separate loopback preview intentionally retains complete imported report', async () => {
  const f = await fixture();
  const preview = await startPreview({ port: 0, assessment: f.file });
  try {
    const result = await (await fetch(preview.url + '/api/workspace')).json();
    assert.equal(result.structuredContent.mode, 'imported');
    assert.deepEqual(result.structuredContent.assessment, f.report);
    assert.match(JSON.stringify(result), new RegExp(marker));
  } finally { preview.close(); await f.clean(); }
});

test('relocated install package preserves the import disclosure boundary and safe default config', async () => {
  const f = await fixture();
  let connection;
  try {
    const destination = path.join(f.directory, 'packages');
    await promisify(execFile)(process.env.CORELIFT_PYTHON || 'python3', [path.join(ROOT, 'scripts/build_packages.py'), '--with-ui', '--output', destination]);
    const root = path.join(destination, 'codex');
    const config = JSON.parse(await readFile(path.join(root, 'mcp.json'), 'utf8'));
    assert.ok(!JSON.stringify(config).includes('--share-summary'));
    const definition = config.mcpServers['corelift-workspace'];
    const entry = definition.args[0].replace('${PLUGIN_ROOT}', root);
    connection = await connect(entry, ['--assessment', f.file]);
    const result = await connection.client.callTool({ name: TOOL_NAME, arguments: {} });
    assert.deepEqual(result.structuredContent, withheld);
    assert.doesNotMatch(JSON.stringify(result), new RegExp(marker));
  } finally { await connection?.close(); await f.clean(); }
});
