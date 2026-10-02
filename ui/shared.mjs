import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';

const moduleDirectory = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(moduleDirectory, path.basename(moduleDirectory) === 'generated' ? '../..' : '..');
export const RESOURCE_URI = 'ui://corelift/workspace-v0.2.0';
export const TOOL_NAME = 'open_corelift_workspace';
export const execFileAsync = promisify(execFile);
export const schema = JSON.parse(await readFile(path.join(ROOT, 'schemas/workspace.schema.json'), 'utf8'));
export const validateWorkspace = new Ajv2020({ strict: false, allErrors: false }).compile(schema);

export function parseArgs(args, preview = false) {
  let assessment;
  let port = 4173;
  for (let index = 0; index < args.length; index++) {
    const argument = args[index];
    if (argument === '--assessment' && args[index + 1] && !assessment) assessment = path.resolve(args[++index]);
    else if (preview && argument === '--port' && /^\d+$/.test(args[index + 1] ?? '')) port = Number(args[++index]);
    else throw new Error('Use --assessment <local-json> and, for preview, --port <number>.');
  }
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw new Error('Invalid loopback port.');
  return { assessment, port };
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

export function resultFor(snapshotJSON) {
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

export async function resourceHTML(preview = false) {
  const html = await readFile(path.join(ROOT, 'ui/generated/workspace.html'), 'utf8');
  return preview ? html.replace('data-preview="false"', 'data-preview="true"') : html;
}
