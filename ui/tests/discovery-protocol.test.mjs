import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { startPreview } from '../preview.mjs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { ROOT, TOOL_NAME, RESOURCE_URI } from '../shared.mjs';
import path from 'node:path';

async function post(url, body, headers = {}) {
  return fetch(url + '/api/discovery', { method: 'POST', headers: { Origin: url, 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(body) });
}

test('loopback discovery protocol requires present exact Origin, Host, JSON, and bounded bodies', async () => {
  const preview = await startPreview({ port: 0 });
  try {
    const url = preview.url;
    assert.equal((await fetch(url + '/api/discovery', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status, 403);
    assert.equal((await post(url, {}, { Origin: 'null' })).status, 403);
    assert.equal((await post(url, {}, { Origin: 'https://evil.example' })).status, 403);
    const badHost = await new Promise((resolve, reject) => {
      const req = http.request(url + '/api/discovery', { method: 'POST', headers: { Host: 'evil.example', Origin: url, 'Content-Type': 'application/json' } }, res => { res.resume(); res.on('end', () => resolve(res.statusCode)); });
      req.on('error', reject); req.end('{}');
    });
    assert.equal(badHost, 403);
    assert.equal((await post(url, {}, { 'Content-Type': 'text/plain' })).status, 415);
    assert.equal((await post(url, { secret: 'x'.repeat(10000) })).status, 413);
    assert.equal((await fetch(url + '/api/discovery')).status, 404);
    assert.equal((await post(url + '/wrong', {})).status, 403);
    const chunked = await new Promise((resolve, reject) => {
      const req = http.request(url + '/api/discovery', { method: 'POST', headers: { Origin: url, 'Content-Type': 'application/json', 'Transfer-Encoding': 'chunked' } }, res => { res.resume(); res.on('end', () => resolve(res.statusCode)); });
      req.on('error', reject); req.write('x'.repeat(5000)); req.end('x'.repeat(5000));
    });
    assert.equal(chunked, 413);
    const slow = await new Promise((resolve, reject) => {
      const req = http.request(url + '/api/discovery', { method: 'POST', headers: { Origin: url, 'Content-Type': 'application/json', 'Transfer-Encoding': 'chunked' } }, res => { res.resume(); res.on('end', () => { req.destroy(); resolve(res.statusCode); }); });
      req.on('error', reject); req.write('{');
    });
    assert.equal(slow, 408);
  } finally { preview.close(); }
});

test('loopback sessions execute guided simulation and keep planted locator out of all MCP surfaces', async () => {
  const preview = await startPreview({ port: 0 });
  const client = new Client({ name: 'discovery-privacy-check', version: '1.0.0' });
  try {
    const created = await (await post(preview.url, { event: { action: 'create' } })).json();
    const id = created.session_id; let state = created.state;
    const send = async (action, more = {}) => {
      const response = await post(preview.url, { session_id: id, event: { action, ...(action === 'status' ? {} : { revision: state.revision }), ...more } });
      const body = await response.json(); if (response.ok) state = body.state; return { response, body };
    };
    const marker = 'PRIVATE_LOCATOR_MARKER_84726';
    const located = await send('locate', { locator: { kind: 'system-url', value: `https://${marker.replaceAll('_','-')}.example.invalid` } });
    assert.equal(located.response.status, 200); assert.equal(state.phase, 'provider-unavailable');
    assert.doesNotMatch(JSON.stringify(located.body), /PRIVATE-LOCATOR/);
    assert.equal((await send('start')).response.status, 409);
    assert.equal((await send('authenticated', { token: marker })).response.status, 400);
    await send('prepare', { scenario: 'partial' }); await send('start');
    for (let n = 0; n < 15 && state.phase !== 'ready'; n++) { await new Promise(r => setTimeout(r, 80)); await send('status'); }
    assert.equal(state.phase, 'ready'); assert.equal(state.facts.find(f => f.key === 'fps').status, 'unknown');
    await send('select', { application_id: state.applications[0].id }); assert.equal(state.phase, 'scoped');
    await client.connect(new StdioClientTransport({ command: process.execPath, args: [path.join(ROOT, 'ui/generated/server.mjs')], stderr: 'pipe' }));
    const outputs = [await client.callTool({ name: TOOL_NAME, arguments: {} }), await client.listTools(), await client.listResources(), await client.readResource({ uri: RESOURCE_URI })];
    for (const value of outputs) assert.doesNotMatch(JSON.stringify(value), /PRIVATE-LOCATOR|PRIVATE_LOCATOR|84726/);
    assert.equal(outputs[0].structuredContent.mode, 'demo');
    assert.equal(outputs[1].tools.length, 1, 'no discovery or authentication mutation tools exposed to MCP');
    await send('disconnect'); assert.equal(state.phase, 'idle'); assert.deepEqual(state.facts, []);
  } finally { await client.close(); preview.close(); }
});

test('loopback relocated package includes a working standalone guided-discovery preview', async () => {
  const { mkdtemp, rm } = await import('node:fs/promises');
  const { execFile, spawn } = await import('node:child_process');
  const { promisify } = await import('node:util');
  const { tmpdir } = await import('node:os');
  const directory = await mkdtemp(path.join(tmpdir(), 'corelift-discovery-package-')); let child;
  try {
    await promisify(execFile)(process.env.CORELIFT_PYTHON || 'python3', [path.join(ROOT, 'scripts/build_packages.py'), '--with-ui', '--output', path.join(directory, 'packages')]);
    child = spawn(process.execPath, [path.join(directory, 'packages/codex/ui/generated/preview.mjs'), '--port', '0'], { cwd: directory, stdio: ['ignore','pipe','pipe'] });
    const url = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Preview startup deadline exceeded.')), 5000);
      child.stdout.on('data', chunk => { const match = String(chunk).match(/http:\/\/127\.0\.0\.1:\d+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
      child.once('exit', code => { clearTimeout(timer); reject(new Error(`Preview exited early: ${code}`)); });
    });
    const html = await (await fetch(url)).text(); assert.match(html, /Try guided demo/);
    const created = await (await post(url, { event: { action: 'create' } })).json();
    const prepared = await (await post(url, { session_id: created.session_id, event: { action: 'prepare', revision: 0, scenario: 'success' } })).json();
    assert.equal(prepared.state.phase, 'scope-review');
    const result = await (await fetch(url + '/api/workspace')).json(); assert.equal(result.structuredContent.mode, 'demo');
  } finally {
    if (child && child.exitCode === null) { const exited = new Promise(resolve => child.once('exit', resolve)); child.kill('SIGTERM'); await exited; }
    await rm(directory, { recursive: true, force: true });
  }
});
