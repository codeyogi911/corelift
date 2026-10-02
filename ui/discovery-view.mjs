import { DiscoverySession, SCENARIOS } from './discovery.mjs';
import validateDiscoveryState from './generated/validate-discovery-state.mjs';

// In hosts this controller is a wholly fictional browser simulation. Preview
// events use an isolated authoritative Node session; neither path calls SAP.
export function createDiscoveryController({ preview, onChange, request = (...args) => fetch(...args) }) {
  const demo = new DiscoverySession();
  let current = demo.snapshot(), sessionID, timer, sequence = 0, closed = false, busy = false, error = '';
  async function send(event) {
    clearTimeout(timer); const requestSequence = ++sequence; busy = true; error = ''; onChange();
    try {
      let result;
      if (preview) {
        const call = async body => {
          const response = await request('/api/discovery', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.timeout(5000), cache: 'no-store' });
          const value = await response.json(); if (!response.ok) { const failure = new Error('Local discovery request failed. Reload its status before continuing.'); failure.status = response.status; throw failure; }
          return value;
        };
        if (!sessionID) {
          const created = await call({ event: { action: 'create' } });
          if (requestSequence !== sequence || closed) return;
          if (typeof created.session_id !== 'string' || !/^[a-f0-9-]{36}$/.test(created.session_id) || !validateDiscoveryState(created.state)) throw new Error('Invalid local session.');
          sessionID = created.session_id; current = created.state;
        }
        const outgoing = event.action === 'status' ? event : { ...event, revision: current.revision };
        try { result = (await call({ session_id: sessionID, event: outgoing })).state; }
        catch (failure) {
          if (failure.status !== 409 || !['cancel','disconnect'].includes(event.action)) throw failure;
          const fresh = (await call({ session_id: sessionID, event: { action: 'status' } })).state;
          if (requestSequence !== sequence || closed) return;
          if (!validateDiscoveryState(fresh) || fresh.attempt !== current.attempt || fresh.mode !== current.mode) throw failure;
          result = (await call({ session_id: sessionID, event: { ...event, revision: fresh.revision } })).state;
        }
      } else {
        if (event.action === 'locate') throw new Error('Private locators belong in the separate local preview.');
        result = demo.dispatch(event.action === 'status' ? event : { ...event, revision: current.revision });
      }
      if (!validateDiscoveryState(result)) throw new Error('Unsupported discovery response.');
      if (requestSequence !== sequence || closed) return;
      current = result;
    } catch (failure) {
      if (requestSequence === sequence && !closed) {
        current = { ...new DiscoverySession().snapshot(), revision: current.revision };
        if (preview && failure.status === 403) { sessionID = undefined; current.revision = 0; error = 'Local session expired or unavailable. Choose a connection or try the guided demo again.'; }
        else error = 'Discovery unavailable. Reload its status before continuing; previous details have been cleared.';
      }
    }
    finally {
      if (requestSequence === sequence && !closed) {
        busy = false; onChange();
        if (!error && ['authenticating','discovering'].includes(current.phase)) timer = setTimeout(() => void send({ action: 'status' }), 180);
      }
    }
  }
  return { get state() { return current; }, get busy() { return busy; }, get error() { return error; }, send,
    close() { closed = true; sequence++; clearTimeout(timer); demo.dispose(); } };
}

export function discoveryView({ el, button, tag, controller, preview }) {
  const state = controller.state;
  const eventButton = (label, action, extra = {}) => button(label, () => void controller.send({ action, ...extra }), { disabled: controller.busy ? true : undefined });
  const intro = el('section', { class: 'surface discovery', 'aria-labelledby': 'connect-title' },
    el('div', { class: 'row' }, el('h2', { id: 'connect-title' }, 'Connect your development system'), tag(state.mode === 'simulation' ? 'Simulation · no SAP connection' : 'Local setup · not connected', 'neutral')),
    el('p', { class: 'small-note' }, 'Choose a system or an existing connection, sign in securely, then let CoreLift discover the release, available metadata and candidate applications. You choose the first app.'),
    el('p', { class: 'small-note' }, 'Development environment is user-declared. Reads still require permission; no writes, new ATC run, monitoring, business rows or source upload are included.'));
  if (preview) {
    const locator = el('input', { id: 'connection-locator', type: 'text', autocomplete: 'off', spellcheck: 'false', placeholder: 'HTTPS system address or saved connection name', maxlength: '512' });
    intro.append(el('form', { class: 'connection-form', onsubmit: event => { event.preventDefault(); const value = locator.value.trim(); void controller.send({ action: 'locate', locator: { kind: value.startsWith('https://') ? 'system-url' : 'saved-connection', value } }); locator.value = ''; } },
      el('label', { for: 'connection-locator' }, 'System address or saved connection'), locator,
      el('button', { type: 'submit', class: 'button', disabled: controller.busy ? true : undefined }, 'Continue locally')));
    intro.append(el('p', { class: 'small-note' }, 'Kept in this local session only. No credentials are collected or stored. Secure sign-in becomes available after a supported provider is bound to the selected system; no live provider is shipped yet.'));
  } else intro.append(el('p', { class: 'small-note' }, 'To prepare a real connection, open the separate CoreLift local preview and enter its address there. This host view accepts only fictional demo choices; private locators are not sent through MCP.'));
  intro.append(el('div', { class: 'row discovery-actions' }, eventButton('Try guided demo', 'prepare', { scenario: 'success' }),
    el('details', {}, el('summary', {}, 'Try a simulated failure or missing capability'), SCENARIOS.filter(s => s !== 'success').map(s => eventButton(s.replaceAll('-', ' '), 'prepare', { scenario: s })))));
  const status = el('section', { class: 'surface', 'aria-live': 'polite' },
    el('h2', {}, state.mode === 'simulation' ? 'Simulated connection progress' : 'Connection status'),
    el('p', { class: 'small-note', role: 'status' }, state.notice),
    controller.error ? el('div', { class: 'error', role: 'alert' }, controller.error, eventButton('Reload discovery status', 'status')) : null);
  if (state.phase === 'scope-review') status.append(
    el('ol', {}, ['Read system identity and version metadata.', 'Inspect the supported read capabilities.', 'List a bounded set of application metadata for your scope choice.'].map(t => el('li', {}, t))),
    el('p', { class: 'small-note' }, 'In a real connection, sign-in belongs to the trusted SAP/identity-provider UI. This simulation has no username, password, token or authentication window.'),
    eventButton('Simulate sign-in', 'start'));
  if (['authenticating','discovering'].includes(state.phase)) status.append(eventButton('Cancel', 'cancel'));
  if (['auth-failed','auth-interrupted','unreachable','identity-mismatch','least-privilege','cancelled'].includes(state.phase) && state.mode === 'simulation') status.append(eventButton('Retry simulated connection', 'retry'));
  if (['provider-unavailable','saved-unavailable'].includes(state.phase)) status.append(button('Secure sign-in unavailable', () => {}, { disabled: true }),
    el('p', { class: 'small-note' }, 'Next step: bind an approved, supported SAP development connection to this locator. No release questionnaire is needed. If discovery remains unavailable, request only the missing metadata or an existing export.'));
  if (state.facts.length) status.append(el('h3', { class: 'discovery-heading' }, 'Discovered automatically'),
    el('dl', {}, state.facts.map(f => [el('dt', {}, f.key.replaceAll('-', ' ')), el('dd', {}, f.value ?? 'Unknown', ' · ', f.status === 'unknown' ? 'Not established' : 'Observed in simulation')])),
    el('p', { class: 'small-note' }, 'No value here is verified against a real server. Technical details are discovered when the provider can establish them; missing facts remain unknown.'),
    el('h3', { class: 'discovery-heading' }, 'Available analysis'),
    el('ul', {}, state.capabilities.map(c => el('li', {}, `${c.id}: ${c.status}. ${c.reason}`))));
  if (state.applications.length) status.append(el('h3', { class: 'discovery-heading' }, 'Choose a representative application'),
    ...state.applications.map(a => el('div', { class: 'discovery-candidate' }, el('strong', {}, a.name), el('p', { class: 'small-note' }, a.reason), eventButton(state.selected_application === a.id ? 'Selected for the next assessment' : 'Start with this app', 'select', { application_id: a.id }))),
    el('p', { class: 'small-note' }, 'These are discovered candidates, not assessed findings. Selection creates a local scope only. The existing synthetic assessment remains separate.'));
  if (state.phase !== 'idle') status.append(eventButton('Clear connection session', 'disconnect'));
  return el('div', { class: 'stack' }, intro, status);
}
