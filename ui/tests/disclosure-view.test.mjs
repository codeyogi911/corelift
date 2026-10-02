import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import { loadSnapshot, hostResultFor, validateWorkspace } from '../shared.mjs';
import validateHostSummary from '../generated/validate-host-summary.mjs';
import * as presentation from '../presentation.mjs';

// Minimal DOM seam checks real rendering/state transitions, not visual appearance.
class Element {
  constructor(text = '') { this.text = text; this.children = []; this.attributes = {}; }
  setAttribute(k, v) { this.attributes[k] = v; }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; }
  addEventListener() {}
  get textContent() { return this.text + this.children.map(c => c.textContent).join(' '); }
}
async function harness(preview = false, localResult) {
  const root = new Element(); const timers = []; let bridge;
  class App {
    constructor() { bridge = this; }
    connect() { return Promise.resolve(); }
    getHostCapabilities() { return {}; }
    getHostContext() { return {}; }
    close() {}
  }
  const source = (await readFile(new URL('../app.mjs', import.meta.url), 'utf8')).replace(/^import .*;\n/gm, '');
  const context = { ...presentation, App, applyHostStyleVariables() {}, validateWorkspace, validateHostSummary,
    Node: Element, document: { querySelector: () => root, documentElement: { dataset: { preview: String(preview) } }, createElement: () => new Element(), createTextNode: text => new Element(text) },
    window: { parent: {}, addEventListener() {} }, matchMedia: () => ({ matches: false }),
    setTimeout: (...args) => { const id = setTimeout(...args); timers.push(id); return id; }, clearTimeout,
    AbortSignal, fetch: async () => ({ ok: true, json: async () => localResult }) };
  vm.runInNewContext(source, context);
  await new Promise(resolve => setImmediate(resolve));
  return { root, send: value => bridge.ontoolresult(value), close: () => timers.forEach(clearTimeout) };
}

test('host disclosure view clears demo details, supports both summary modes and refuses full imports', async () => {
  const h = await harness();
  try {
    const snapshot = JSON.parse(await loadSnapshot());
    h.send({ structuredContent: snapshot });
    assert.match(h.root.textContent, /ERP_PURCHASING/);
    snapshot.mode = 'imported'; snapshot.rehearsal = null;
    const withheld = hostResultFor(JSON.stringify(snapshot));
    h.send(withheld);
    assert.match(h.root.textContent, /Contents withheld/);
    assert.doesNotMatch(h.root.textContent, /ERP_PURCHASING/);
    h.send(hostResultFor(JSON.stringify(snapshot), { shareSummary: true }));
    assert.match(h.root.textContent, /Three counts shared/);
    snapshot.assessment.decisions[0].reason = 'SHOULD_NEVER_RENDER';
    assert.equal(validateWorkspace(snapshot), true, 'otherwise valid full import must still be refused by host UI');
    h.send({ structuredContent: snapshot });
    assert.match(h.root.textContent, /invalid or unsupported/);
    assert.doesNotMatch(h.root.textContent, /SHOULD_NEVER_RENDER|ERP_PURCHASING/);
    h.send(withheld);
    assert.doesNotMatch(h.root.textContent, /Three counts shared|invalid or unsupported/);
  } finally { h.close(); }
});

test('local preview retains imported details and clearly distinguishes host disclosure', async () => {
  const value = JSON.parse(await loadSnapshot()); value.mode = 'imported'; value.rehearsal = null;
  const h = await harness(true, { structuredContent: value });
  try {
    assert.match(h.root.textContent, /ERP_PURCHASING/);
    assert.match(h.root.textContent, /Full report visible in this local preview/);
  } finally { h.close(); }
});
