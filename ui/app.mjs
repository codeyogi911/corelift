import { App, applyHostStyleVariables } from '@modelcontextprotocol/ext-apps';
import validateWorkspace from './generated/validate-workspace.mjs';
import { VIEWS, LABELS, DISPOSITIONS, safeSourceURL, routeFromContext, matchesApplication } from './presentation.mjs';

const root = document.querySelector('#root');
const preview = document.documentElement.dataset.preview === 'true';
const state = { view: 'applications', selected: null, search: '', data: null, loading: true, error: '', status: '', bridge: null, capabilities: {} };
let initialTimer;

// Export content is always a text node; no innerHTML, Markdown or template parsing.
function el(tag, attributes = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else if (value !== undefined && value !== null && value !== false) node.setAttribute(key, String(value));
  }
  for (const child of children.flat(Infinity)) if (child !== null && child !== undefined) node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return node;
}
const tag = (text, tone = '') => el('span', { class: `tag ${tone}` }, text);
const list = (items) => items.length ? el('ul', {}, items.map(item => el('li', {}, item))) : el('p', { class: 'small-note' }, 'No items in this export.');
const section = (title, ...children) => el('section', { class: 'section' }, el('h3', {}, title), ...children);
const button = (text, handler, extra = {}) => el('button', { type: 'button', class: 'button', onclick: handler, ...extra }, text);
const profile = (value) => `${value.family} ${value.release} · ${value.edition} · ${value.fps}`;

function changeView(view) {
  state.view = view; state.status = ''; render(); document.querySelector('#page-title')?.focus();
}
function showApplication(id) { state.selected = id; state.view = 'applications'; state.search = ''; render(); document.querySelector('#application-title')?.focus(); }
function sourceNode(source) {
  const url = safeSourceURL(source.url);
  let control = el('strong', {}, source.title);
  if (url && preview) control = el('a', { href: url, target: '_blank', rel: 'noopener noreferrer' }, source.title);
  else if (url && state.capabilities.openLinks) control = button(source.title, async () => {
    try { const result = await state.bridge.openLink({ url }); if (result?.isError) throw new Error(); }
    catch { state.status = 'The host could not open this source. Its URL remains available in the text result.'; render(); }
  }, { class: 'link-button' });
  return el('div', { class: 'source' }, control,
    el('p', {}, `${source.id} · checked ${source.checked_at}`),
    el('p', {}, source.revision), el('p', {}, source.scope),
    !url ? el('p', {}, 'Link unavailable: source URL is outside the supported documentation hosts.') : null,
    url && !preview && !state.capabilities.openLinks ? el('p', {}, 'Source links are unavailable in this host. See the structured/text result.') : null);
}
function evidenceDetails(ids) {
  const sources = state.data.assessment.sources.filter(source => !ids || ids.includes(source.id));
  return el('details', {}, el('summary', {}, 'Evidence and source revisions'), sources.map(sourceNode));
}
function metrics() {
  const decisions = state.data.assessment.decisions;
  return el('div', { class: 'metrics', 'aria-label': 'Assessment summary' },
    el('div', { class: 'metric' }, el('strong', {}, decisions.length), el('span', {}, 'applications')),
    el('div', { class: 'metric' }, el('strong', {}, decisions.filter(d => d.unknowns.length).length), el('span', {}, 'with unknowns')),
    el('div', { class: 'metric' }, el('strong', {}, state.data.assessment.migration_plan.stages.filter(s => s.status.startsWith('blocked')).length), el('span', {}, 'blocked stages')));
}
function dependencyTable(dependencies) {
  if (!dependencies.length) return el('p', { class: 'small-note' }, 'No classified dependency evidence exported.');
  return el('div', { class: 'table-wrap' }, el('table', {},
    el('caption', { class: 'visually-hidden' }, 'Dependency evidence and remote eligibility'),
    el('thead', {}, el('tr', {}, ['Dependency', 'Evidence', 'Access'].map(h => el('th', { scope: 'col' }, h)))),
    el('tbody', {}, dependencies.map(dep => el('tr', {},
      el('td', {}, el('code', {}, dep.object), el('p', { class: 'small-note' }, `Source: ${dep.source_id || 'missing'}`)),
      el('td', {}, tag(dep.state, dep.state === 'unknown' ? 'warn' : 'neutral'), el('p', { class: 'small-note' }, `Claim: ${dep.claimed_state} · ${dep.verification}`)),
      el('td', {}, el('strong', {}, dep.contract), el('p', { class: 'small-note' }, `Remote pathway: ${dep.remote_pathway}`),
        dep.uses.map(use => el('p', { class: 'small-note' }, `${use.application_id}: ${use.kind}/${use.operation}`))))))));
}
function detail(decision) {
  const a = state.data.assessment;
  const level = decision.clean_core_level_candidate;
  const screens = a.screen_plan.filter(screen => screen.application_id === decision.application_id);
  return el('article', { class: 'detail', 'aria-labelledby': 'application-title' },
    el('div', { class: 'detail-top' }, el('div', {}, el('h2', { id: 'application-title', tabindex: '-1' }, decision.application_id),
      el('p', { class: 'small-note' }, 'Future-target recommendation')), tag(DISPOSITIONS[decision.disposition], decision.unknowns.length ? 'warn' : 'neutral')),
    el('p', { class: 'reason' }, decision.reason),
    el('p', { class: 'small-note' }, `Dependency level candidate: ${level === 'unknown' ? 'Unknown' : level}. Architect/technology review is still required.`),
    decision.unknowns.length ? el('div', { class: 'callout' }, el('strong', {}, 'Resolve before placement'), list(decision.unknowns)) : null,
    section('Dependency evidence', dependencyTable(decision.dependencies)),
    section('Risk and coverage', list(decision.risks), decision.transitive_applications.length ? el('p', { class: 'small-note' }, `Inherited from: ${decision.transitive_applications.join(', ')}`) : null),
    screens.length ? section('Screen behavior', screens.map(screen => el('div', {},
      el('p', {}, `${screen.id} · ${screen.technology}`),
      el('div', { class: 'callout' }, screen.rebuild_required_for_btp ? 'A BTP UI would require behavior reconstruction and validation.' : 'Review behavior parity for the target UI.'),
      el('dl', {}, ['pbo','pai','validation','authorization','value_help','locking','errors'].map(key => [el('dt', {}, key.replaceAll('_',' ').toUpperCase()), el('dd', {}, screen[key].join('; ') || 'No behavior evidence exported')]))))) : null,
    decision.alternatives.length ? section('Alternatives to investigate', list(decision.alternatives.map(option => `${option.option}: ${option.risk} (${option.status})`))) : null,
    evidenceDetails([...new Set([...decision.source_ids, ...decision.alternatives.map(x => x.source_id), ...decision.dependencies.map(x => x.source_id)])]),
    el('p', { class: 'status-line' }, 'Not approved · no execution controls are available in this workspace.'));
}
function applicationList() {
  const rows = state.data.assessment.decisions.filter(d => matchesApplication(d, state.search));
  return el('div', { class: 'application-list', id: 'application-list', 'aria-label': 'Exported applications' }, rows.length ? rows.map(d =>
    el('button', { type: 'button', class: 'application-row', 'aria-pressed': String(state.selected === d.application_id), onclick: () => showApplication(d.application_id) },
      el('strong', {}, d.application_id), el('span', {}, DISPOSITIONS[d.disposition]))) : el('div', { class: 'empty' }, el('strong', {}, 'No matching applications'), el('p', {}, 'Try an application ID or a different decision.')));
}
function applications() {
  const decisions = state.data.assessment.decisions;
  if (!decisions.length) return el('div', { class: 'empty' }, el('h2', {}, 'No applications exported'), el('p', {}, 'Load an assessment with exported application coverage.'));
  const selected = decisions.find(d => d.application_id === state.selected) ?? decisions[0];
  state.selected = selected.application_id;
  const search = el('input', { id: 'search-applications', type: 'search', placeholder: 'Search ID or decision', value: state.search, oninput: event => {
    state.search = event.target.value;
    document.querySelector('#application-list').replaceWith(applicationList());
  } });
  return [metrics(), el('div', { class: 'application-layout' }, el('div', {}, el('label', { for: 'search-applications', class: 'search-label' }, 'Find an application'), search, applicationList()), detail(selected))];
}
function connections() {
  const a = state.data.assessment;
  return el('div', { class: 'stack' }, el('div', { class: 'surface' }, el('h2', {}, 'Assessment source'),
    el('p', { class: 'small-note' }, state.data.label),
    el('dl', {}, el('dt', {}, 'Current source'), el('dd', {}, profile(a.source_system)), el('dt', {}, 'Future target'), el('dd', {}, profile(a.target)),
      el('dt', {}, 'Snapshot'), el('dd', { class: 'mono' }, state.data.snapshot_hash), el('dt', {}, 'API revision'), el('dd', { class: 'mono' }, a.run_record.api_snapshot_revision)),
    el('div', { class: 'callout' }, 'This snapshot is fixed for this server session. Restart with an explicitly selected local assessment to change the source.')),
    el('div', { class: 'surface' }, state.data.connections.map(connection => section(connection.label,
      tag(connection.status === 'available' ? 'Local data available' : 'Not connected', 'neutral'),
      el('p', { class: 'small-note' }, connection.id === 'offline-export' ? 'Read-only normalized assessment. No live discovery has run.' : 'Live connector is not implemented. This workspace does not request credentials or create resources.')))),
    el('div', { class: 'surface' }, el('h2', {}, 'Source policy and provenance'), evidenceDetails()));
}
function findings() {
  const a = state.data.assessment;
  return el('div', { class: 'stack' }, metrics(), a.decisions.map(d => el('article', { class: 'surface' },
    el('div', { class: 'row' }, el('div', {}, el('h2', {}, d.application_id), el('p', {}, d.reason)), tag(d.clean_core_level_candidate === 'unknown' ? 'Unknown' : `Level ${d.clean_core_level_candidate} candidate`, d.unknowns.length ? 'warn' : 'neutral')),
    d.unknowns.length ? el('div', { class: 'callout' }, list(d.unknowns)) : el('p', { class: 'small-note' }, 'No unknowns recorded in this export. This is not independent verification.'),
    section('Recorded risks', list(d.risks)),
    button('Review application', () => showApplication(d.application_id), { 'aria-label': `Review ${d.application_id}` }))));
}
function plan() {
  const p = state.data.assessment.migration_plan;
  return el('div', { class: 'stack' }, el('div', { class: 'callout' }, el('strong', {}, 'Draft · not executable'), el('p', {}, 'ERP remains authoritative. No data transfer, deployment or approval is available here.')),
    el('div', { class: 'surface' }, el('h2', {}, 'Migration stages'), p.stages.map((stage, index) => el('div', { class: 'stage' },
      el('span', { class: 'stage-index' }, String(index+1).padStart(2,'0')), el('div', {}, el('h3', {}, stage.id.replaceAll('-',' ')), el('p', {}, stage.purpose),
        el('p', {}, `Approval: ${stage.approval_required ? 'required' : 'review only'} · Checkpoint: ${stage.checkpoint_required ? 'required' : 'not at this stage'}`)),
      tag(stage.status.startsWith('blocked') ? 'Blocked · provider absent' : 'Pending review', stage.status.startsWith('blocked') ? 'warn' : 'neutral')))),
    el('div', { class: 'surface' }, el('h2', {}, 'Data ownership and cutover'), p.data.length ? p.data.map(data => section(data.dataset_id,
      el('dl', {}, el('dt', {}, 'Ownership'), el('dd', {}, data.ownership), el('dt', {}, 'Owner'), el('dd', {}, data.owner), el('dt', {}, 'System of record'), el('dd', {}, data.system_of_record),
        el('dt', {}, 'Classification'), el('dd', {}, data.classification), el('dt', {}, 'Used by'), el('dd', {}, data.used_by.join(', ') || 'None exported')),
      el('p', { class: 'small-note' }, `Extension candidates: ${data.extension_candidates.join(', ') || 'none'} · No transfer approved`), list([...data.required_actions, ...data.unknowns]))) : el('p', { class: 'small-note' }, 'No datasets exported.')));
}
function verification() {
  const a = state.data.assessment;
  const rehearsal = state.data.mode === 'demo' ? state.data.rehearsal : null;
  return el('div', { class: 'stack' },
    el('div', { class: 'surface' }, el('h2', {}, rehearsal ? 'Synthetic rehearsal' : 'No independent verification attached'),
      el('p', { class: 'small-note' }, rehearsal ? 'Two fake extension-owned notes in a Python memory mock. These checks do not verify SAP behavior.' : 'Imported verification fields are assertions in the report. The demo rehearsal has not been applied to this assessment.'),
      rehearsal ? el('div', { class: 'table-wrap' }, el('table', {}, el('caption', { class: 'visually-hidden' }, 'Synthetic rehearsal results'),
        el('thead', {}, el('tr', {}, el('th', { scope: 'col' }, 'Mock check'), el('th', { scope: 'col' }, 'Result'))),
        el('tbody', {}, [['Idempotent replay', rehearsal.idempotent_replay], ['Semantic reconciliation', rehearsal.semantic_reconciliation], ['Checkpoint rollback', rehearsal.rollback_verified]].map(([label, passed]) => el('tr', {}, el('td', {}, label), el('td', {}, tag(passed ? 'Passed in mock' : 'Failed in mock', passed ? '' : 'danger'))))))) : null,
      rehearsal ? list(rehearsal.limitations) : null),
    el('div', { class: 'surface' }, el('h2', {}, 'Recorded assessment provenance'), el('p', { class: 'small-note' }, state.data.provenance_notice),
      el('dl', {}, el('dt', {}, 'Ruleset'), el('dd', {}, a.run_record.ruleset), el('dt', {}, 'Input connector'), el('dd', {}, a.run_record.connector),
        Object.entries(a.run_record.input_hashes).map(([key,value]) => [el('dt', {}, key.replaceAll('_',' ')),el('dd', { class: 'mono' }, value)])),
      section('Practical limits', list(a.run_record.limitations))),
    el('div', { class: 'callout' }, 'SAP access, authorizations, compilation, API sequencing, data migration, deployment and Codex sidebar acceptance have not been verified.'));
}
function render() {
  root.setAttribute('aria-busy', String(state.loading));
  if (!state.data) {
    if (state.error) root.replaceChildren(el('main', { id: 'main', class: 'boot' }, el('div', { class: 'error', role: 'alert' }, el('h1', {}, 'Assessment unavailable'),
      el('p', {}, state.error), el('p', {}, 'Use the structured tool result or the CoreLift CLI if this host cannot show MCP Apps.'),
      (preview || state.capabilities.serverTools) ? button('Try again', refresh) : null)));
    return;
  }
  const a = state.data.assessment;
  const captions = { applications: 'Review application decisions and the evidence behind them.', connections: 'See which local snapshot this assessment describes.', findings: 'Resolve unknowns and understand inherited clean-core risk.', plan: 'Review stage gates, data ownership and cutover requirements.', verification: 'Distinguish recorded assertions from completed mock checks.' };
  const canRefresh = preview || Boolean(state.capabilities.serverTools);
  const rail = el('aside', { class: 'rail' }, el('div', { class: 'brand' }, el('span', { class: 'brand-mark', 'aria-hidden': 'true' }, 'CL'), 'CoreLift'),
    el('p', { class: 'rail-caption' }, 'Assessment workspace'),
    el('nav', { 'aria-label': 'Workspace sections' }, VIEWS.map(view => el('button', { type: 'button', class: 'nav-button', 'aria-current': view === state.view ? 'page' : undefined, onclick: () => changeView(view) },
      LABELS[view], view === 'applications' ? el('span', { class: 'nav-count' }, a.decisions.length) : null))),
    el('div', { class: 'rail-footer' }, el('strong', {}, 'Read-only workspace'), el('span', {}, preview ? 'Local preview · host loading unverified' : 'MCP App · host capability detected'), el('span', { class: 'mono' }, `Snapshot ${state.data.snapshot_hash.slice(0,10)}`)));
  const page = ({ applications, connections, findings, plan, verification })[state.view]();
  const main = el('main', { id: 'main', tabindex: '-1' }, el('div', { class: 'page-heading' }, el('div', {}, el('h1', { id: 'page-title', tabindex: '-1' }, LABELS[state.view]), el('p', {}, captions[state.view])),
    canRefresh ? button(state.loading ? 'Loading…' : 'Reload snapshot', refresh, { disabled: state.loading ? true : undefined }) : null),
    state.error ? el('div', { class: 'error', role: 'alert' }, el('strong', {}, 'Snapshot could not be reloaded'), el('p', {}, state.error), el('p', {}, 'The previously loaded snapshot remains visible.')) : null,
    ...[page].flat(), el('p', { class: 'status-line', role: 'status', 'aria-live': 'polite' }, state.status || 'All recommendations remain unapproved.'));
  root.replaceChildren(el('div', { class: 'shell' }, rail, el('div', { class: 'workspace' },
    el('header', { class: 'context-bar' }, el('span', {}, el('strong', {}, `Source ${a.source_system.family} ${a.source_system.release}`), ` → Target ${a.target.family} ${a.target.release} · ${a.target.edition} · ${a.target.fps}`), tag('Not approved', 'neutral')),
    el('div', { class: 'notice' }, el('strong', {}, state.data.mode === 'demo' ? 'Synthetic demo' : 'Imported assessment'), state.data.provenance_notice), main)));
}
function acceptResult(result) {
  if (result.isError) throw new Error(result.content?.find(c => c.type === 'text')?.text || 'The local assessment could not be loaded.');
  const value = result.structuredContent;
  if (!validateWorkspace(value) || (value.mode === 'imported' && value.rehearsal !== null) || (value.mode === 'demo' && (!value.assessment.synthetic || !value.rehearsal))) throw new Error('The workspace received an invalid or unsupported assessment snapshot.');
  clearTimeout(initialTimer);
  state.data = value; state.loading = false; state.error = ''; render();
}
async function refresh() {
  state.loading = true; state.error = ''; render();
  try {
    let result;
    if (preview) {
      const response = await fetch('/api/workspace', { cache: 'no-store', signal: AbortSignal.timeout(12000) });
      result = await response.json(); if (!response.ok) throw new Error(result.error || 'Local preview could not load the assessment.');
    } else {
      if (!state.capabilities.serverTools) throw new Error('This host does not support refreshing server tools.');
      result = await state.bridge.callServerTool({ name: 'open_corelift_workspace', arguments: {} });
    }
    acceptResult(result);
  } catch (error) { state.loading = false; state.error = error.message || 'Assessment unavailable.'; render(); }
}
function hostContext(context) {
  if (context?.theme === 'dark' || context?.theme === 'light') document.documentElement.dataset.theme = context.theme;
  if (context?.styles?.variables) applyHostStyleVariables(context.styles.variables);
  const route = routeFromContext(context); if (route) state.view = route;
  if (state.data) render();
}
if (preview) {
  document.documentElement.dataset.theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  void refresh();
} else if (window.parent === window) {
  state.loading = false; state.error = 'This MCP resource needs a supported host. Start the separate local preview to inspect it in a browser.'; render();
} else {
  const app = new App({ name: 'CoreLift workspace', version: '0.2.0' }, {});
  state.bridge = app;
  app.ontoolresult = result => { try { acceptResult(result); } catch (error) { state.loading = false; state.error = error.message; render(); } };
  app.onhostcontextchanged = hostContext;
  app.ontoolcancelled = () => { state.loading = false; state.error = 'The host cancelled loading this assessment.'; render(); };
  initialTimer = setTimeout(() => { if (!state.data) { state.loading = false; state.error = 'No initial assessment arrived. Use the tool’s text result or retry through the host.'; render(); } }, 10000);
  app.connect(undefined, { timeout: 8000 }).then(() => { state.capabilities = app.getHostCapabilities() || {}; hostContext(app.getHostContext()); if (state.data) render(); }).catch(() => {
    clearTimeout(initialTimer); state.loading = false; state.error = 'This host did not complete MCP Apps initialization. The assessment remains available as structured data and text.'; render();
  });
  window.addEventListener('pagehide', () => { clearTimeout(initialTimer); void app.close(); }, { once: true });
}
