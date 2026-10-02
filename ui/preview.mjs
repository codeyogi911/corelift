import http from 'node:http';
import { pathToFileURL } from 'node:url';
import { loadSnapshot, parseArgs, resourceHTML, localResultFor } from './shared.mjs';

export async function startPreview({ assessment, port = 4173, signal } = {}) {
  let snapshotJSON, loadError;
  try { snapshotJSON = await loadSnapshot(assessment, signal); } catch (error) { loadError = error.message; }
  signal?.throwIfAborted();
  const html = await resourceHTML(true);
  signal?.throwIfAborted();
  const server = http.createServer((req, res) => {
    const authority = `127.0.0.1:${server.address().port}`;
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'");
    if (req.headers.host !== authority || (req.headers.origin && req.headers.origin !== `http://${authority}`)) {
      res.writeHead(403); res.end('Local preview origin rejected.'); return;
    }
    if (req.method !== 'GET') { res.writeHead(405, { Allow: 'GET' }); res.end('Read-only preview.'); return; }
    if (req.url === '/') { res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end(html); return; }
    if (req.url === '/api/workspace') {
      res.writeHead(loadError ? 422 : 200, { 'Content-Type': 'application/json; charset=utf-8' });
      res.end(JSON.stringify(loadError ? { error: loadError } : localResultFor(snapshotJSON))); return;
    }
    res.writeHead(404); res.end('Unknown preview route.');
  });
  const close = () => { signal?.removeEventListener('abort', close); server.close(); };
  signal?.addEventListener('abort', close, { once: true });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve); });
  signal?.throwIfAborted();
  return { server, url: `http://127.0.0.1:${server.address().port}`, close };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const abort = new AbortController();
  for (const signal of ['SIGINT', 'SIGTERM']) process.once(signal, () => abort.abort());
  try {
    const preview = await startPreview({ ...parseArgs(process.argv.slice(2), true), signal: abort.signal });
    process.stdout.write(`CoreLift local preview: ${preview.url}\nLocal preview only; Codex sidebar loading has not been verified.\n`);
  } catch { if (!abort.signal.aborted) process.stderr.write('CoreLift preview could not start. Check build, arguments and available loopback port.\n'); process.exitCode = abort.signal.aborted ? 0 : 1; }
}
