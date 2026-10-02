import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';

const moduleDirectory = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(moduleDirectory, path.basename(moduleDirectory) === 'generated' ? '../..' : '..');
export const RESOURCE_URI = 'ui://corelift/workspace-v0.4.0';
export const TOOL_NAME = 'open_corelift_workspace';
export const execFileAsync = promisify(execFile);
export const schema = JSON.parse(await readFile(path.join(ROOT, 'schemas/workspace.schema.json'), 'utf8'));
export const validateWorkspace = new Ajv2020({ strict: false, allErrors: false }).compile(schema);
export const hostSummarySchema = JSON.parse(await readFile(path.join(ROOT, 'schemas/host-summary.schema.json'), 'utf8'));
const demoSchema = { ...schema, properties: { ...schema.properties, mode: { const: 'demo' } } };
export const hostOutputSchema = { type: 'object', anyOf: [demoSchema, hostSummarySchema] };
export const validateHostOutput = new Ajv2020({ strict: false }).compile(hostOutputSchema);

export function parseArgs(args, preview = false) {
  let assessment;
  let shareSummary = false;
  let port = 4173;
  for (let index = 0; index < args.length; index++) {
    const argument = args[index];
    if (argument === '--assessment' && args[index + 1] && !assessment) assessment = path.resolve(args[++index]);
    else if (!preview && argument === '--share-summary' && !shareSummary) shareSummary = true;
    else if (preview && argument === '--port' && /^\d+$/.test(args[index + 1] ?? '')) port = Number(args[++index]);
    else throw new Error('Use --assessment <local-json>; --share-summary is an explicit MCP-only disclosure choice. Preview accepts --port <number>.');
  }
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('Invalid loopback port.');
  if (shareSummary && !assessment) throw new Error('--share-summary requires an explicitly selected local assessment.');
  return { assessment, port, shareSummary };
}

export async function loadSnapshot(assessment, signal) {
  const args = [path.join(ROOT, 'scripts/workspace_snapshot.py')];
  if (assessment) args.push('--assessment', assessment);
  try {
    const { stdout } = await execFileAsync(process.env.CORELIFT_PYTHON || 'python3', args, {
      cwd: ROOT, timeout: 10000, maxBuffer: 6_000_000, signal,
      env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
    });
    const value = JSON.parse(stdout);
    if (!validateWorkspace(value)) throw new Error('schema');
    return JSON.stringify(value); // frozen bytes, parsed afresh per response
  } catch {
    throw new Error('The selected local assessment could not be loaded. Check the JSON schema, file size and Python 3.11+ runtime. No demo substitution was made.');
  }
}

export function localResultFor(snapshotJSON) {
  const data = JSON.parse(snapshotJSON);
  const a = data.assessment;
  return {
    content: [{ type: 'text', text: `${data.mode === 'demo' ? 'Synthetic demo' : 'Imported assessment'}: ${a.decisions.length} applications. ` +
      `${a.source_system.family} ${a.source_system.release} to ${a.target.family} ${a.target.release} ${a.target.fps}. ` +
      `${data.provenance_notice} All decisions are unapproved and migration stages are not executable. ` +
      `Snapshot ${data.snapshot_hash}. The structured result includes application decisions, evidence, screen behavior, data ownership and stage gates; use these when this host cannot show the workspace.` }],
    structuredContent: data,
  };
}


// Only this projection may cross the MCP boundary. No imported object is spread
// into a response, including _meta, content, resource URIs or dynamic metadata.
export function hostResultFor(snapshotJSON, { shareSummary = false } = {}) {
  const data = JSON.parse(snapshotJSON);
  if (!validateWorkspace(data)) throw new Error('Invalid local snapshot.');
  if (data.mode === 'demo') {
    if (!data.assessment.synthetic || !data.rehearsal) throw new Error('Invalid synthetic demo.');
    return localResultFor(snapshotJSON);
  }
  const counts = shareSummary ? {
    applications: data.assessment.decisions.length,
    applications_with_unknowns: data.assessment.decisions.filter(value => value.unknowns.length > 0).length,
    blocked_stages: data.assessment.migration_plan.stages.filter(value => value.status.startsWith('blocked')).length,
  } : null;
  const value = { host_summary_version: '1.0.0', mode: 'imported', read_only: true,
    disclosure: shareSummary ? 'aggregate-counts' : 'withheld', counts };
  if (!validateHostOutput(value)) throw new Error('Invalid disclosure projection.');
  return { content: [{ type: 'text', text: shareSummary
    ? `Explicit aggregate disclosure: ${counts.applications} applications, ${counts.applications_with_unknowns} with unknowns, ${counts.blocked_stages} blocked stages. These are imported report assertions, not independently verified. Only these three counts and fixed disclosure/version metadata are sent to this host. Full evidence remains in the local CLI/preview. This does not authorize SAP access or any additional disclosure.`
    : 'An imported report is configured locally. No report contents or counts are disclosed. This host receives only fixed imported/withheld/read-only/version metadata. Detailed evidence remains in the local CLI/preview. Connecting a system does not authorize disclosure to an AI host.' }], structuredContent: value };
}

export async function resourceHTML(preview = false) {
  const html = await readFile(path.join(ROOT, 'ui/generated/workspace.html'), 'utf8');
  return preview ? html.replace('data-preview="false"', 'data-preview="true"') : html;
}
