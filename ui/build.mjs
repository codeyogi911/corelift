import { build } from 'esbuild';
import Ajv2020 from 'ajv/dist/2020.js';
import standaloneCode from 'ajv/dist/standalone/index.js';
import { readFile, writeFile, mkdir, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const generated = path.join(root, 'ui/generated');
await mkdir(generated, { recursive: true });
const schema = JSON.parse(await readFile(path.join(root, 'schemas/workspace.schema.json'), 'utf8'));
const ajv = new Ajv2020({ strict: false, code: { source: true, esm: true } });
await writeFile(path.join(generated, 'validate-workspace.mjs'), standaloneCode(ajv, ajv.compile(schema)));
const bundled = await build({ absWorkingDir: root, metafile: true, entryPoints: [path.join(root, 'ui/app.mjs')], bundle: true, write: false, minify: true, format: 'esm', platform: 'browser', target: 'es2022', legalComments: 'inline' });
const template = await readFile(path.join(root, 'ui/index.html'), 'utf8');
const css = await readFile(path.join(root, 'ui/styles.css'), 'utf8');
const script = bundled.outputFiles[0].text.replaceAll('</script', '<\\/script');
const html = template.replace('/* CORE_LIFT_STYLES */', () => css).replace('/* CORE_LIFT_SCRIPT */', () => script);
await writeFile(path.join(generated, 'workspace.html'), html);
const serverBundle = await build({ absWorkingDir: root, metafile: true, entryPoints: [path.join(root, 'ui/server.mjs')], outfile: path.join(generated, 'server.mjs'),
  bundle: true, minify: true, format: 'esm', platform: 'node', target: 'node22',
  banner: { js: 'import { createRequire as __coreliftCreateRequire } from "node:module"; const require = __coreliftCreateRequire(import.meta.url);' },
  legalComments: 'inline' });
console.log(`Built self-contained MCP App resource (${Buffer.byteLength(html)} bytes).`);

// Preserve full upstream licenses for every dependency actually included by esbuild.
const packageRoots = new Set();
for (const input of [...Object.keys(bundled.metafile.inputs), ...Object.keys(serverBundle.metafile.inputs)]) {
  if (!input.includes('node_modules/')) continue;
  let directory = path.dirname(path.resolve(root, input));
  while (directory.startsWith(path.join(root, 'node_modules'))) {
    try { const metadata = JSON.parse(await readFile(path.join(directory, 'package.json'), 'utf8')); if (metadata.name) { packageRoots.add(directory); break; } directory = path.dirname(directory); }
    catch { directory = path.dirname(directory); }
  }
}
const licenses = [];
for (const directory of [...packageRoots].sort()) {
  const pkg = JSON.parse(await readFile(path.join(directory, 'package.json'), 'utf8'));
  const names = (await readdir(directory)).filter(name => /^(license|licence|copying|notice)(\.|$)/i.test(name)).sort();
  if (!pkg.name || !pkg.license || !names.length) throw new Error(`Missing redistribution license: ${pkg.name || directory}`);
  const texts = await Promise.all(names.map(async name => ({ file: name, text: await readFile(path.join(directory, name), 'utf8') })));
  licenses.push({ name: pkg.name, version: pkg.version, license: pkg.license, texts });
}
licenses.sort((a, b) => a.name.localeCompare(b.name));
await writeFile(path.join(generated, 'THIRD_PARTY_NOTICES.txt'),
  'Third-party software included in CoreLift workspace bundles.\nOriginal license and attribution texts follow.\n\n' +
  licenses.map(pkg => `${pkg.name}@${pkg.version} — ${pkg.license}\n${'='.repeat(72)}\n` + pkg.texts.map(item => `${item.file}\n${item.text}`).join('\n')).join('\n\n'));
await writeFile(path.join(generated, 'bundle-licenses.json'), JSON.stringify(licenses.map(({texts, ...metadata}) => ({...metadata, notice_files: texts.map(item => item.file)})), null, 2) + '\n');
console.log(`Preserved licenses for ${licenses.length} bundled third-party packages.`);
