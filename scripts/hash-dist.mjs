import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { extname, join, relative } from 'node:path';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const argument = process.argv.indexOf('--dist');
const DIST = argument === -1 ? join(ROOT, 'dist') : process.argv[argument + 1];
if (argument !== -1 && (!DIST || process.argv.length !== argument + 2)) throw new Error('Usage: hash-dist.mjs [--dist directory]');
const selfArtifacts = new Set(['release-manifest.json']);
const identityExclusions = new Set(['input-provenance.json']);
const mimeTypes = Object.freeze({
  '.css': 'text/css; charset=utf-8',
  '.geojson': 'application/geo+json; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
});
async function files(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (await Promise.all(entries.map(async entry => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return files(path);
    if (!entry.isFile()) throw new Error(`Dist contains a non-regular entry: ${relative(DIST, path)}`);
    return [path];
  }))).flat();
}
const all = (await files(DIST)).filter(path => !selfArtifacts.has(relative(DIST, path).split('\\').join('/'))).sort();
const assets = await Promise.all(all.map(async path => {
  const bytes = await readFile(path);
  const assetPath = relative(DIST, path).split('\\').join('/');
  const mime = mimeTypes[extname(assetPath).toLowerCase()] ?? 'application/octet-stream';
  return { path: assetPath, sha256: createHash('sha256').update(bytes).digest('hex'), bytes: bytes.length, mime };
}));
const identityProjection = assets
  .filter(asset => !identityExclusions.has(asset.path))
  .map(({ path, sha256 }) => ({ path, sha256 }));
const digest = createHash('sha256').update(JSON.stringify(identityProjection)).digest('hex');
const release = {
  schema_version: 1,
  assets,
  identity_exclusions: [...identityExclusions].sort(),
  content_digest: digest,
  release_id: digest,
  release_sha256: digest,
};
await writeFile(join(DIST, 'release-manifest.json'), `${JSON.stringify(release, null, 2)}\n`);
console.log(`Hashed ${assets.length} dist assets.`);
