export const VIEWS = ['connections', 'applications', 'findings', 'plan', 'verification'];
export const LABELS = { connections: 'Connections', applications: 'Applications', findings: 'Clean-core findings', plan: 'Migration plan', verification: 'Verification' };
export const DISPOSITIONS = {
  'retain-core': 'Keep ERP core', 'retire-candidate': 'Review retirement', 'investigate': 'Needs investigation',
  'rebuild-candidate': 'Rebuild candidate', 'retain-with-risk-review': 'Retain · risk review',
  'retain-on-stack-candidate': 'On-stack candidate', 'btp-sidecar-candidate': 'BTP sidecar candidate',
};
export function safeSourceURL(value) {
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.port) return null;
    if (['help.sap.com', 'learning.sap.com', 'www.sap.com', 'community.sap.com', 'pages.api.community.sap.com', 'cap.cloud.sap', 'developers.sap.com', 'developers.openai.com', 'modelcontextprotocol.io', 'apps.extensions.modelcontextprotocol.io', 'agent-plugins.org'].includes(url.hostname)) return url.href;
    if (url.hostname === 'github.com' && /^\/(SAP|openai|modelcontextprotocol|cap-js|SAP-samples)\//.test(url.pathname)) return url.href;
    return null;
  } catch { return null; }
}
export function routeFromContext(context) {
  const route = context?.['openai/deepLink']?.url;
  if (typeof route !== 'string' || !route.startsWith('/') || route.startsWith('//') || route.includes('#')) return null;
  const [pathname] = route.split('?');
  const value = pathname.slice(1) || 'applications';
  return VIEWS.includes(value) ? value : null;
}
export function matchesApplication(decision, query) {
  return `${decision.application_id} ${decision.disposition} ${DISPOSITIONS[decision.disposition]}`.toLowerCase().includes(query.trim().toLowerCase());
}
