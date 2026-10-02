// Shared deterministic simulation. No HTTP client, credential handling or SAP transport.
export const SCENARIOS = ['success', 'partial', 'auth-failed', 'auth-interrupted', 'unreachable', 'identity-mismatch', 'least-privilege'];
export const DISCOVERY_SCOPE = ['system-metadata', 'capability-catalog', 'application-candidates'];
export const MESSAGES = {
  idle: 'Choose a connection. CoreLift will discover the technical details.',
  'scope-review': 'Review the three metadata reads, then simulate secure sign-in.',
  authenticating: 'Simulated sign-in is in progress. No credentials are requested.',
  discovering: 'Discovering metadata and candidate applications in the fictional development system.',
  ready: 'Simulated discovery complete. Choose one application to scope the next assessment.',
  scoped: 'Application scope selected in simulation. No new assessment or system action has run.',
  cancelled: 'Connection cancelled. Discovered details and selection were cleared.',
  'provider-unavailable': 'Connection provider unavailable. Your locator was accepted locally; no address was contacted. An approved SAP development adapter must be configured before secure sign-in.',
  'saved-unavailable': 'No saved connection is configured in this local catalog. Use a system address, or have the supported SAP adapter supply an existing connection.',
  'auth-failed': 'Simulated sign-in was refused. Retry through the sign-in flow; no details were retained.',
  'auth-interrupted': 'Simulated sign-in was interrupted. Retry when ready.',
  unreachable: 'The simulated system could not be reached. Confirm the selected connection and network access before retrying.',
  'identity-mismatch': 'Server identity did not match the selected system/client in simulation. Discovery stopped; no fallback endpoint was tried.',
  'least-privilege': 'The simulated account lacks metadata-read permission. Ask the system owner for display-only access to the requested metadata; no broader role is assumed.',
};
const CANDIDATES = [
  { id: 'Z_REQUEST_NOTES', name: 'Request notes', reason: 'Small fictional sidecar candidate with extension-owned notes; useful first scope.', status: 'simulated' },
  { id: 'Z_PR_WORKBENCH', name: 'Purchasing workbench', reason: 'Fictional Dynpro application with transactional coupling; useful for testing an on-stack decision.', status: 'simulated' },
];
function copy(value) { return JSON.parse(JSON.stringify(value)); }
export function validateLocator(locator) {
  if (!locator || Object.keys(locator).sort().join(',') !== 'kind,value' || typeof locator.value !== 'string' || locator.value.length > 512) throw new Error('Invalid connection locator.');
  if (locator.kind === 'saved-connection') {
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(locator.value)) throw new Error('Invalid saved connection identifier.');
    return { kind: locator.kind, value: locator.value };
  }
  // Origin only: no path expansion, query, credentials, encoded host, local bridge or IP literals.
  if (locator.kind !== 'system-url' || !/^https:\/\/[A-Za-z0-9.-]+(?::[0-9]{1,5})?\/?$/.test(locator.value)) throw new Error('Use an HTTPS system origin without credentials, path, query or fragment.');
  let url;
  try { url = new URL(locator.value); } catch { throw new Error('Invalid HTTPS system origin.'); }
  const host = url.hostname.toLowerCase();
  if (!host.includes('.') || host.endsWith('.') || host.split('.').some(p => !/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(p)) || /^[0-9.]+$/.test(host) || /(^|\.)(localhost|local)$/.test(host) || host === 'metadata.google.internal') throw new Error('This locator is not supported. Local bridges and IP addresses require a separately approved adapter.');
  return { kind: locator.kind, value: url.origin };
}

// A simulator observation is bound to one selected identity and three named reads.
// This is not a real TLS/DNS/authentication implementation or SAP operation mapping.
export function validateSimulatedObservation(observation) {
  const expected = { origin: 'https://synthetic-dev.invalid', system: 'DEV', client: '100' };
  if (!observation || Object.keys(expected).some(k => observation.identity?.[k] !== expected[k])) return 'identity-mismatch';
  if (!Array.isArray(observation.grants) || observation.grants.length !== DISCOVERY_SCOPE.length || DISCOVERY_SCOPE.some(k => !observation.grants.includes(k))) return 'least-privilege';
  return null;
}

export class DiscoverySession {
  #schedule; #generation = 0; #scenario = 'success'; #locator = null; #state;
  constructor({ schedule = fn => setTimeout(fn, 250) } = {}) {
    this.#schedule = schedule;
    this.#state = { discovery_version: '1.0.0', read_only: true, environment: 'development', environment_verification: 'user-declared', mode: 'unconfigured', phase: 'idle', revision: 0, attempt: 0, notice: MESSAGES.idle, facts: [], capabilities: [], applications: [], selected_application: null, permitted_scope: [...DISCOVERY_SCOPE] };
  }
  snapshot() { return copy(this.#state); }
  #clear() { this.#state.facts = []; this.#state.capabilities = []; this.#state.applications = []; this.#state.selected_application = null; }
  #phase(phase) { this.#state.phase = phase; this.#state.notice = MESSAGES[phase]; this.#state.revision++; }
  #begin() {
    this.#clear(); const generation = ++this.#generation; this.#state.attempt++; this.#phase('authenticating');
    this.#schedule(() => {
      if (generation !== this.#generation) return;
      if (['auth-failed', 'auth-interrupted', 'unreachable'].includes(this.#scenario)) { this.#phase(this.#scenario); return; }
      this.#phase('discovering');
      this.#schedule(() => {
        if (generation !== this.#generation) return;
        // Fixed provider observations only; browser events cannot submit identity/facts/success.
        const failure = validateSimulatedObservation({ identity: { origin: 'https://synthetic-dev.invalid', system: this.#scenario === 'identity-mismatch' ? 'OTHER' : 'DEV', client: '100' }, grants: this.#scenario === 'least-privilege' ? ['system-metadata'] : [...DISCOVERY_SCOPE] });
        if (failure) { this.#clear(); this.#phase(failure); return; }
        const partial = this.#scenario === 'partial';
        this.#state.facts = [
          { key: 'server-identity', value: 'Fictional DEV / client 100', status: 'simulated-observed' },
          { key: 'product', value: 'S/4HANA on-premise', status: 'simulated-observed' },
          { key: 'release', value: '2023', status: 'simulated-observed' },
          { key: 'fps', value: partial ? null : 'FPS02', status: partial ? 'unknown' : 'simulated-observed' },
          { key: 'abap-platform', value: '758', status: 'simulated-observed' },
        ];
        this.#state.capabilities = DISCOVERY_SCOPE.map(id => ({ id, status: 'simulated-available', reason: 'Fixed simulator metadata only; no SAP operation mapping is enabled.' }));
        this.#state.capabilities.push({ id: 'existing-atc-findings', status: 'unknown', reason: 'Existing ATC findings are unavailable in this simulation. Provide an existing result only if needed; no new run is started.' });
        this.#state.applications = copy(CANDIDATES); this.#phase('ready');
      });
    });
  }
  dispatch(event) {
    // Strict server schema additionally checks the envelope; this guard also protects browser simulation.
    if (!event || typeof event !== 'object' || Array.isArray(event)) throw new Error('Invalid discovery event.');
    const fields = { status: ['action'], prepare: ['action','revision','scenario'], locate: ['action','revision','locator'], start: ['action','revision'], retry: ['action','revision'], cancel: ['action','revision'], disconnect: ['action','revision'], select: ['action','revision','application_id'] }[event.action];
    if (!fields || Object.keys(event).length !== fields.length || fields.some(k => !(k in event))) throw new Error('Unsupported discovery event.');
    if (event.action === 'status') return this.snapshot();
    if (event.revision !== this.#state.revision) throw new Error('Discovery state changed. Reload before continuing.');
    if (event.action === 'prepare') {
      if (!SCENARIOS.includes(event.scenario)) throw new Error('Unknown simulation scenario.');
      this.#generation++; this.#clear(); this.#locator = null; this.#scenario = event.scenario; this.#state.mode = 'simulation'; this.#phase('scope-review');
    } else if (event.action === 'locate') {
      const locator = validateLocator(event.locator);
      this.#generation++; this.#clear(); this.#locator = locator; this.#state.mode = 'unconfigured';
      this.#phase(locator.kind === 'saved-connection' ? 'saved-unavailable' : 'provider-unavailable');
    } else if (event.action === 'start' || event.action === 'retry') {
      const phases = event.action === 'start' ? ['scope-review'] : ['auth-failed','auth-interrupted','unreachable','identity-mismatch','least-privilege','cancelled'];
      if (this.#state.mode !== 'simulation' || !phases.includes(this.#state.phase)) throw new Error('Sign-in is unavailable in this state.');
      this.#begin();
    } else if (event.action === 'cancel' || event.action === 'disconnect') {
      this.#generation++; this.#clear(); this.#locator = null;
      if (event.action === 'disconnect') { this.#state.mode = 'unconfigured'; this.#phase('idle'); }
      else this.#phase('cancelled');
    } else if (event.action === 'select') {
      if (!['ready','scoped'].includes(this.#state.phase) || !this.#state.applications.some(a => a.id === event.application_id)) throw new Error('Select an application returned by this discovery.');
      this.#state.selected_application = event.application_id; this.#phase('scoped');
    }
    return this.snapshot();
  }
  dispose() { this.#generation++; this.#clear(); this.#locator = null; }
}
