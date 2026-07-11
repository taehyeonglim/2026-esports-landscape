import { createHash } from 'node:crypto';
import { access, cp, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('..', import.meta.url));
const dist = join(root, 'dist');
const probe = join(root, 'tests/.provenance-probe.txt');
const sha = bytes => createHash('sha256').update(bytes).digest('hex');

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch (error) {
    if (error?.code === 'ENOENT') return false;
    throw error;
  }
}

async function files(directory) {
  const output = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) output.push(...await files(path));
    else if (entry.isFile()) output.push(path);
    else throw new Error(`Verification graph contains a non-regular entry: ${path}`);
  }
  return output;
}

async function graph(directory) {
  const rows = [];
  for (const path of (await files(directory)).sort()) rows.push({ path: relative(directory, path), sha256: sha(await readFile(path)) });
  return rows;
}

function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, encoding: 'utf8' });
  if (result.status !== 0) throw new Error(`${command} ${args.join(' ')} failed:\n${result.stdout}\n${result.stderr}`);
}

async function manifest(directory = dist) {
  return JSON.parse(await readFile(join(directory, 'release-manifest.json'), 'utf8'));
}

if (await exists(probe)) throw new Error(`Refusing to overwrite existing verification probe: ${relative(root, probe)}`);
const mutated = await mkdtemp(join(tmpdir(), 'esports-mutated-dist-'));
try {
  run('npm', ['run', 'build']);
  const firstGraph = await graph(dist);
  const firstManifest = await manifest();
  const firstProvenance = sha(await readFile(join(dist, 'input-provenance.json')));

  run('npm', ['run', 'build']);
  const secondGraph = await graph(dist);
  const secondManifest = await manifest();

  await writeFile(probe, 'input provenance mutation fixture\n');
  run('npm', ['run', 'build']);
  const probeManifest = await manifest();
  const probeProvenance = sha(await readFile(join(dist, 'input-provenance.json')));

  await rm(probe, { force: true });
  run('npm', ['run', 'build']);
  const restoredManifest = await manifest();

  await cp(dist, mutated, { recursive: true });
  await writeFile(join(mutated, 'index.html'), `${await readFile(join(mutated, 'index.html'), 'utf8')}\n<!-- output mutation fixture -->\n`);
  run(process.execPath, ['scripts/hash-dist.mjs', '--dist', mutated]);
  const mutatedManifest = await manifest(mutated);

  const report = {
    schemaVersion: 1,
    kind: 'build-release-test-report',
    measuredAt: new Date().toISOString(),
    cleanBuildsEqual: JSON.stringify(firstGraph) === JSON.stringify(secondGraph),
    cleanReleaseIdsEqual: firstManifest.release_id === secondManifest.release_id,
    assetCount: restoredManifest.assets.length,
    releaseId: restoredManifest.release_id,
    inputOnlyMutationChangedProvenance: firstProvenance !== probeProvenance,
    inputOnlyMutationPreservedReleaseId: firstManifest.release_id === probeManifest.release_id,
    sourceRestorePreservedReleaseId: firstManifest.release_id === restoredManifest.release_id,
    outputMutationChangedReleaseId: restoredManifest.release_id !== mutatedManifest.release_id,
    allAssetsHaveBytesAndMime: restoredManifest.assets.every(asset => Number.isInteger(asset.bytes) && asset.bytes >= 0 && typeof asset.mime === 'string' && asset.mime.length > 0),
  };
  report.passed = Object.entries(report)
    .filter(([key]) => !['schemaVersion', 'kind', 'measuredAt', 'assetCount', 'releaseId', 'passed'].includes(key))
    .every(([, value]) => value === true);
  await mkdir(join(root, 'artifacts'), { recursive: true });
  await writeFile(join(root, 'artifacts/build-release-verification.json'), `${JSON.stringify(report, null, 2)}\n`);
  console.log(JSON.stringify(report, null, 2));
  if (!report.passed) process.exitCode = 1;
} finally {
  await rm(probe, { force: true });
  await rm(mutated, { recursive: true, force: true });
}
