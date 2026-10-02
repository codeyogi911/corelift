import { randomUUID } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import Ajv2020 from 'ajv/dist/2020.js';
import { ROOT } from './shared.mjs';
import { DiscoverySession } from './discovery.mjs';

const ajv = new Ajv2020({ strict: false });
const validateEvent = ajv.compile(JSON.parse(await readFile(path.join(ROOT, 'schemas/discovery-event.schema.json'), 'utf8')));
const validateState = ajv.compile(JSON.parse(await readFile(path.join(ROOT, 'schemas/discovery-state.schema.json'), 'utf8')));
const MAX_BYTES = 8192;
export class DiscoveryError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
export function createDiscoveryService({ now = Date.now, maxSessions = 4, ttlMs = 600000, schedule } = {}) {
  const sessions = new Map();
  function expire() {
    for (const [id, item] of sessions) if (now() >= item.expires) { clearTimeout(item.timer); item.session.dispose(); sessions.delete(id); }
  }
  return {
    execute(body) {
      expire();
      if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).some(k => !['session_id','event'].includes(k)) || !validateEvent(body.event)) throw new DiscoveryError(400, 'Invalid discovery request.');
      let id = body.session_id;
      if (body.event.action === 'create') {
        if (id !== undefined) throw new DiscoveryError(400, 'Invalid discovery request.');
        if (sessions.size >= maxSessions) throw new DiscoveryError(429, 'Local discovery session limit reached. Close unused previews or wait for expiry.');
        id = randomUUID();
        const timer = setTimeout(() => { const item = sessions.get(id); item?.session.dispose(); sessions.delete(id); }, ttlMs); timer.unref();
        sessions.set(id, { session: new DiscoverySession({ schedule }), expires: now() + ttlMs, timer });
      }
      if (typeof id !== 'string' || !/^[a-f0-9-]{36}$/.test(id) || !sessions.has(id)) throw new DiscoveryError(403, 'Discovery session is unavailable. Start a new local session.');
      const item = sessions.get(id);
      let state;
      try { state = item.session.dispatch(body.event.action === 'create' ? { action: 'status' } : body.event); }
      catch { throw new DiscoveryError(409, 'Discovery event was rejected. Reload the current state before retrying.'); }
      if (!validateState(state)) throw new DiscoveryError(500, 'Discovery result could not be validated.');
      return { session_id: id, state };
    },
    close() { for (const item of sessions.values()) { clearTimeout(item.timer); item.session.dispose(); } sessions.clear(); },
  };
}
export async function readDiscoveryBody(req, { deadlineMs = 1500 } = {}) {
  if (req.headers['content-type'] !== 'application/json') throw new DiscoveryError(415, 'Discovery requires application/json.');
  if (req.headers['content-length'] && (!/^\d+$/.test(req.headers['content-length']) || Number(req.headers['content-length']) > MAX_BYTES)) throw new DiscoveryError(413, 'Discovery request exceeds the local limit.');
  return new Promise((resolve, reject) => {
    let bytes = 0, data = [], done = false;
    const finish = (error, value) => { if (done) return; done = true; clearTimeout(timer); req.removeListener('data', onData); req.removeListener('end', onEnd); req.removeListener('aborted', onAbort); req.removeListener('error', onAbort); error ? reject(error) : resolve(value); };
    const onData = chunk => { bytes += chunk.length; if (bytes > MAX_BYTES) { finish(new DiscoveryError(413, 'Discovery request exceeds the local limit.')); req.resume(); } else data.push(chunk); };
    const onEnd = () => { try { finish(null, JSON.parse(Buffer.concat(data).toString('utf8'))); } catch { finish(new DiscoveryError(400, 'Invalid discovery request.')); } };
    const onAbort = () => finish(new DiscoveryError(400, 'Discovery request interrupted.'));
    const timer = setTimeout(() => finish(new DiscoveryError(408, 'Discovery request timed out.')), deadlineMs);
    req.on('data', onData); req.once('end', onEnd); req.once('aborted', onAbort); req.once('error', onAbort);
  });
}
