import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, open, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { tmpdir } from 'node:os';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const DIST = join(ROOT, 'dist');
const STAGING = join(ROOT, `.dist-stage-${process.pid}`);
const BACKUP = join(ROOT, `.dist-backup-${process.pid}`);
const LOCK = join(ROOT, '.dist-build.lock');
const run = promisify(execFile);
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const ignoredName = name => name === '.DS_Store' || name === '__pycache__' || name.endsWith('.pyc');

async function exists(path) {
  try {
    await stat(path);
    return true;
  } catch (error) {
    if (error?.code === 'ENOENT') return false;
    throw error;
  }
}

async function sourceFiles(directory, prefix) {
  const entries = (await readdir(directory, { withFileTypes: true })).filter(entry => !ignoredName(entry.name));
  const files = await Promise.all(entries.map(async entry => {
    const absolute = join(directory, entry.name);
    const relative = `${prefix}/${entry.name}`;
    if (entry.isDirectory()) return sourceFiles(absolute, relative);
    if (!entry.isFile()) throw new Error(`Unsupported input file type: ${relative}`);
    return [relative];
  }));
  return files.flat().sort();
}

async function snapshot(paths) {
  const values = new Map();
  for (const path of paths) values.set(path, await readFile(join(ROOT, path)));
  return values;
}

async function writeSnapshotFile(path, bytes) {
  const target = join(STAGING, path);
  await mkdir(dirname(target), { recursive: true });
  await writeFile(target, bytes);
}

async function materializeSnapshot(root, values) {
  for (const [path, bytes] of values) {
    const target = join(root, path);
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, bytes);
  }
}

const packageJson = JSON.parse(await readFile(join(ROOT, 'package.json'), 'utf8'));
const basePath = packageJson.config?.githubPagesBase;
if (basePath !== '/2026-esports-landscape/') throw new Error('package.json must define the GitHub Pages base path.');


const regionFiles = (await readdir(join(ROOT, 'geo/regions'))).filter(name => name.endsWith('.geojson')).sort();
if (regionFiles.length !== 17) throw new Error('Validated staging requires exactly 17 region GeoJSON files.');
const publicDataContracts = [
  'data/national-map.v1.json',
  'data/site.v3.json',
  'data/resource-coverage.v3.json',
  'data/sources.v3.json',
  'data/source-crosswalk.v1.json',
  'data/schema.v3.json',
  'migrations/v2-to-v3.json',
];
const provenanceOnlyContracts = [
  // Normalization counts are operational QA evidence, not a public runtime dependency.
  'reports/source-normalization.json',
];
const publicFiles = [
  'index.html',
  ...(await sourceFiles(join(ROOT, 'assets'), 'assets')).filter(path => /\.(?:avif|png|webp)$/.test(path)),
  ...(await sourceFiles(join(ROOT, 'src'), 'src')).filter(path => path.endsWith('.js')),
  ...(await sourceFiles(join(ROOT, 'styles'), 'styles')).filter(path => /\.(?:css|woff2|txt)$/.test(path)),
  ...(await sourceFiles(join(ROOT, 'research'), 'research')).filter(path => path.endsWith('.html')),
  ...publicDataContracts,
  ...regionFiles.map(name => `geo/regions/${name}`),
].sort();

const requiredRootInputs = ['index.html', 'package.json', 'package-lock.json', 'pyproject.toml', 'requirements.lock'];
const optionalRootInputs = ['playwright.config.mjs'];
const inputPaths = [...new Set([
  ...requiredRootInputs,
  ...(await Promise.all(optionalRootInputs.map(async path => await exists(join(ROOT, path)) ? path : null))).filter(Boolean),
  ...(await sourceFiles(join(ROOT, '.github'), '.github')),
  ...(await sourceFiles(join(ROOT, 'assets'), 'assets')),
  ...(await sourceFiles(join(ROOT, 'adr'), 'adr')),
  ...(await sourceFiles(join(ROOT, 'config'), 'config')),
  ...(await sourceFiles(join(ROOT, 'data/reference'), 'data/reference')),
  ...(await sourceFiles(join(ROOT, 'docs'), 'docs')),
  ...(await sourceFiles(join(ROOT, 'migrations'), 'migrations')),
  ...(await sourceFiles(join(ROOT, 'schemas'), 'schemas')),
  ...(await sourceFiles(join(ROOT, 'src'), 'src')),
  ...(await sourceFiles(join(ROOT, 'styles'), 'styles')),
  ...(await sourceFiles(join(ROOT, 'research'), 'research')),
  ...(await sourceFiles(join(ROOT, 'scripts'), 'scripts')),
  ...(await sourceFiles(join(ROOT, 'tests'), 'tests')),
  'baseline/v2/site.v2.json',
  'baseline/v2/region-geo.v2.json',
  'data/additions.v1.json',
  'data/site.v3.json',
  'data/resource-coverage.v3.json',
  'data/resource-map.v1.json',
  ...publicDataContracts,
  ...provenanceOnlyContracts,
  ...regionFiles.map(name => `geo/regions/${name}`),
])].sort();
const inputSnapshot = await snapshot(inputPaths);
const validationRoot = await mkdtemp(join(tmpdir(), 'esports-build-input-'));
try {
  await materializeSnapshot(validationRoot, inputSnapshot);
  await run(process.execPath, [join(ROOT, 'scripts/validate-data.mjs'), '--root', validationRoot], { cwd: ROOT });
} catch (error) {
  await rm(validationRoot, { recursive: true, force: true });
  throw error;
}
const lock = await open(LOCK, 'wx').catch(async (error) => {
  await rm(validationRoot, { recursive: true, force: true });
  if (error?.code === 'EEXIST') throw new Error('Another build already owns the dist publisher lock.');
  throw error;
});

try {
  await rm(STAGING, { recursive: true, force: true });
  await rm(BACKUP, { recursive: true, force: true });
  await mkdir(STAGING, { recursive: true });
  for (const path of publicFiles) await writeSnapshotFile(path, inputSnapshot.get(path));
  const inputs = inputPaths.map(path => ({ path, sha256: sha256(inputSnapshot.get(path)) }));
  const provenance = {
    schema_version: 1,
    input_digest: sha256(Buffer.from(JSON.stringify(inputs))),
    inputs,
  };
  await writeFile(join(STAGING, 'input-provenance.json'), `${JSON.stringify(provenance, null, 2)}\n`);
  await run(process.execPath, ['scripts/hash-dist.mjs', '--dist', STAGING], { cwd: ROOT });

  if (await exists(DIST)) await rename(DIST, BACKUP);
  try {
    await rename(STAGING, DIST);
  } catch (error) {
    if (await exists(BACKUP)) await rename(BACKUP, DIST);
    throw error;
  }
  await rm(BACKUP, { recursive: true, force: true });
  console.log('Built native static MPA at dist/.');
} finally {
  await rm(STAGING, { recursive: true, force: true });
  await rm(BACKUP, { recursive: true, force: true });
  await rm(validationRoot, { recursive: true, force: true });
  await lock.close();
  await rm(LOCK, { force: true });
}
