import test from 'node:test';
import assert from 'node:assert/strict';
import { DiscoverySession, SCENARIOS, DISCOVERY_SCOPE, validateLocator, validateSimulatedObservation } from '../discovery.mjs';
import { createDiscoveryService } from '../discovery-service.mjs';
import { createDiscoveryController } from '../discovery-view.mjs';
import validateState from '../generated/validate-discovery-state.mjs';

function fixture(scenario = 'success') {
  const tasks = []; const session = new DiscoverySession({ schedule: fn => tasks.push(fn) });
  const send = (action, more = {}) => session.dispatch({ action, revision: session.snapshot().revision, ...more });
  send('prepare', { scenario });
  return { session, send, tasks, drain: () => { while (tasks.length) tasks.shift()(); } };
}

test('guided simulation discovers facts and candidates without manual technical questions', () => {
  const f = fixture();
  assert.equal(f.send('start').phase, 'authenticating');
  f.tasks.shift()(); assert.equal(f.session.snapshot().phase, 'discovering');
  f.drain(); const state = f.session.snapshot();
  assert.equal(state.phase, 'ready'); assert.equal(validateState(state), true);
  assert.equal(state.mode, 'simulation'); assert.equal(state.environment_verification, 'user-declared');
  assert.equal(state.facts.find(f => f.key === 'release').value, '2023');
  assert.ok(state.facts.every(f => f.status === 'simulated-observed'));
  assert.equal(f.send('select', { application_id: state.applications[0].id }).phase, 'scoped');
  assert.throws(() => f.send('select', { application_id: 'PRIVATE_UNDISCOVERED_APP' }));
  assert.equal(f.send('disconnect').facts.length, 0);
});

test('partial discovery keeps only missing facts unknown and offers an existing-evidence fallback', () => {
  const f = fixture('partial'); f.send('start'); f.drain();
  const state = f.session.snapshot();
  assert.deepEqual(state.facts.find(f => f.key === 'fps'), { key: 'fps', value: null, status: 'unknown' });
  assert.equal(state.capabilities.find(c => c.id === 'existing-atc-findings').status, 'unknown');
  assert.equal(state.applications.length, 2);
});

for (const scenario of SCENARIOS.filter(s => !['success','partial'].includes(s))) test(`failed ${scenario} attempt retains no facts, selection or credentials and can retry`, () => {
  const f = fixture(scenario); f.send('start'); f.drain();
  const state = f.session.snapshot();
  assert.equal(state.phase, scenario); assert.deepEqual(state.facts, []); assert.deepEqual(state.applications, []);
  assert.equal(state.selected_application, null); assert.equal(validateState(state), true);
  assert.equal(f.send('retry').attempt, 2); f.drain(); assert.equal(f.session.snapshot().phase, scenario);
});

test('cancel, retry, disconnect and replacement ignore delayed completions and clear stale selections', () => {
  const f = fixture(); f.send('start'); const old = f.tasks.shift();
  f.send('cancel'); f.send('retry'); old(); assert.equal(f.session.snapshot().phase, 'authenticating');
  f.drain(); f.send('select', { application_id: 'Z_REQUEST_NOTES' });
  f.send('prepare', { scenario: 'success' }); f.send('start'); f.tasks.shift()();
  f.send('disconnect'); f.drain(); assert.equal(f.session.snapshot().phase, 'idle'); assert.deepEqual(f.session.snapshot().facts, []);
  f.send('prepare', { scenario: 'success' }); f.send('start');
  f.send('locate', { locator: { kind: 'system-url', value: 'https://private-dev.example.invalid' } });
  f.drain(); assert.equal(f.session.snapshot().phase, 'provider-unavailable'); assert.deepEqual(f.session.snapshot().applications, []);
});

test('replayed starts and forged authentication/identity/fact/capability events cannot authorize discovery', () => {
  const f = fixture(); const revision = f.session.snapshot().revision;
  f.session.dispatch({ action: 'start', revision });
  assert.throws(() => f.session.dispatch({ action: 'start', revision }));
  for (const action of ['authenticated','discovered','connected','run-atc','read-source','deploy']) assert.throws(() => f.send(action));
  for (const field of ['identity','facts','token','approval','provider','url','executable','permissions']) assert.throws(() => f.send('start', { [field]: 'forged' }));
});

test('simulated server identity and named least-privilege grants are bound independently of tool annotations', () => {
  const observation = { identity: { origin: 'https://synthetic-dev.invalid', system: 'DEV', client: '100' }, grants: [...DISCOVERY_SCOPE] };
  assert.equal(validateSimulatedObservation(observation), null);
  for (const key of ['origin','system','client']) assert.equal(validateSimulatedObservation({ ...observation, identity: { ...observation.identity, [key]: 'OTHER' } }), 'identity-mismatch');
  for (const grants of [[], ['system-metadata'], [...DISCOVERY_SCOPE,'write'], ['system-metadata','system-metadata','system-metadata']]) assert.equal(validateSimulatedObservation({ ...observation, grants, readOnlyHint: true, approval: 'allow-all' }), 'least-privilege');
});

test('URL parsing rejects SSRF-shaped locators; accepted origins never select a live transport', () => {
  for (const value of ['http://dev.example','file:///etc/passwd','https://user:secret@dev.example','https://dev.example/path','https://dev.example?token=secret','https://dev.example#secret','https://127.0.0.1','https://2130706433','https://0x7f000001','https://169.254.169.254','https://[::1]','https://localhost','https://x.localhost','https://metadata.google.internal','https://dev.example/../','https://dev.example\\@evil.example','https://dev.example\n','https://dev.example:65536','https://dev.example.','https://%31%32%37.0.0.1']) assert.throws(() => validateLocator({ kind: 'system-url', value }), value);
  const f = fixture();
  const before = globalThis.fetch; globalThis.fetch = () => { throw new Error('Network forbidden in simulation'); };
  try {
    const result = f.send('locate', { locator: { kind: 'system-url', value: 'https://PRIVATE-MARKER.example.internal:8443' } });
    assert.equal(result.phase, 'provider-unavailable'); assert.equal(result.mode, 'unconfigured');
    assert.doesNotMatch(JSON.stringify(result), /PRIVATE-MARKER/); assert.throws(() => f.send('start'));
    assert.equal(f.send('locate', { locator: { kind: 'saved-connection', value: 'LOCAL_DEV_ALIAS' } }).phase, 'saved-unavailable');
    assert.throws(() => f.send('start'));
  } finally { globalThis.fetch = before; }
});

test('Node service isolates opaque sessions, limits lifetime/count and rejects forged completions', () => {
  let time = 0; const tasks = []; const service = createDiscoveryService({ now: () => time, ttlMs: 100, maxSessions: 2, schedule: fn => tasks.push(fn) });
  const a = service.execute({ event: { action: 'create' } }), b = service.execute({ event: { action: 'create' } });
  assert.notEqual(a.session_id, b.session_id); assert.throws(() => service.execute({ event: { action: 'create' } }), /limit/);
  const prepared = service.execute({ session_id: a.session_id, event: { action: 'prepare', revision: 0, scenario: 'success' } });
  service.execute({ session_id: a.session_id, event: { action: 'start', revision: prepared.state.revision } });
  assert.equal(service.execute({ session_id: b.session_id, event: { action: 'status' } }).state.phase, 'idle');
  assert.throws(() => service.execute({ session_id: 'unknown', event: { action: 'status' } }));
  assert.throws(() => service.execute({ session_id: a.session_id, event: { action: 'authenticated', revision: 2, facts: [] } }));
  assert.throws(() => service.execute({ session_id: a.session_id, event: { action: 'start', revision: 2, approval: true } }));
  time = 100; assert.throws(() => service.execute({ session_id: a.session_id, event: { action: 'status' } }), /unavailable/);
  while (tasks.length) tasks.shift()();
  const fresh = service.execute({ event: { action: 'create' } }); assert.equal(fresh.state.phase, 'idle');
  service.close(); assert.throws(() => service.execute({ session_id: fresh.session_id, event: { action: 'status' } }));
});


test('idle sessions expire without another request and pending callbacks cannot restore facts', async () => {
  const tasks = []; const service = createDiscoveryService({ ttlMs: 20, maxSessions: 1, schedule: fn => tasks.push(fn) });
  try {
    const a = service.execute({ event: { action: 'create' } });
    service.execute({ session_id: a.session_id, event: { action: 'prepare', revision: 0, scenario: 'success' } });
    service.execute({ session_id: a.session_id, event: { action: 'start', revision: 1 } });
    await new Promise(resolve => setTimeout(resolve, 45));
    assert.equal(tasks.length, 1);
    tasks.shift()();
    assert.equal(tasks.length, 0, 'idle expiry invalidated completion before another service request');
    const fresh = service.execute({ event: { action: 'create' } });
    assert.equal(fresh.state.phase, 'idle'); assert.deepEqual(fresh.state.facts, []);
    assert.throws(() => service.execute({ session_id: a.session_id, event: { action: 'status' } }));
  } finally { service.close(); }
});

test('preview controller clears expired or failed observations and recovers without reloading page', async () => {
  let time = 0, offline = false;
  const service = createDiscoveryService({ now: () => time, ttlMs: 10000, schedule: fn => fn() });
  const request = async (_url, options) => {
    if (offline) throw new Error('PRIVATE_REQUEST_FAILURE');
    try { const result = service.execute(JSON.parse(options.body)); return { ok: true, status: 200, json: async () => result }; }
    catch (error) { return { ok: false, status: error.status, json: async () => ({ error: error.message }) }; }
  };
  const controller = createDiscoveryController({ preview: true, onChange() {}, request });
  try {
    await controller.send({ action: 'prepare', scenario: 'success' }); await controller.send({ action: 'start' });
    assert.equal(controller.state.phase, 'ready'); assert.equal(controller.state.facts.length, 5);
    time = 10000; await controller.send({ action: 'status' });
    assert.equal(controller.state.phase, 'idle'); assert.deepEqual(controller.state.facts, []); assert.match(controller.error, /expired/);
    await controller.send({ action: 'prepare', scenario: 'success' }); await controller.send({ action: 'start' });
    assert.equal(controller.state.phase, 'ready');
    offline = true; await controller.send({ action: 'status' }); assert.deepEqual(controller.state.facts, []); assert.doesNotMatch(controller.error, /PRIVATE_REQUEST_FAILURE/);
    offline = false; await controller.send({ action: 'status' }); assert.equal(controller.state.phase, 'ready');
    await controller.send({ action: 'disconnect' }); assert.deepEqual(controller.state.applications, []);
  } finally { controller.close(); service.close(); }
});


test('cancel and disconnect refresh a callback-raced revision without trapping the controller', async () => {
  const tasks = []; const service = createDiscoveryService({ schedule: fn => tasks.push(fn) });
  const request = async (_url, options) => {
    try { const body = service.execute(JSON.parse(options.body)); return { ok: true, status: 200, json: async () => body }; }
    catch (error) { return { ok: false, status: error.status, json: async () => ({}) }; }
  };
  const controller = createDiscoveryController({ preview: true, onChange() {}, request });
  try {
    for (const action of ['cancel','disconnect']) {
      await controller.send({ action: 'prepare', scenario: 'success' }); await controller.send({ action: 'start' });
      tasks.shift()(); // Server moves to discovering before UI polls its new revision.
      await controller.send({ action });
      assert.equal(controller.error, '');
      assert.equal(controller.state.phase, action === 'cancel' ? 'cancelled' : 'idle');
      while (tasks.length) tasks.shift()();
      assert.deepEqual(controller.state.facts, []);
    }
  } finally { controller.close(); service.close(); }
});


test('out-of-order initial session responses cannot replace the newest connection', async () => {
  const service = createDiscoveryService(); let releaseFirst, created = 0;
  const request = async (_url, options) => {
    const body = JSON.parse(options.body); const result = service.execute(body);
    if (body.event.action === 'create' && ++created === 1) await new Promise(resolve => { releaseFirst = resolve; });
    return { ok: true, status: 200, json: async () => result };
  };
  const controller = createDiscoveryController({ preview: true, onChange() {}, request });
  try {
    const first = controller.send({ action: 'prepare', scenario: 'success' });
    await controller.send({ action: 'locate', locator: { kind: 'system-url', value: 'https://dev.example.invalid' } });
    assert.equal(controller.state.phase, 'provider-unavailable');
    releaseFirst(); await first; await controller.send({ action: 'status' });
    assert.equal(controller.state.phase, 'provider-unavailable');
  } finally { controller.close(); service.close(); }
});
