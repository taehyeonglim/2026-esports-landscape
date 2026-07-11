import { createHash } from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020.js';
import { fileURLToPath } from 'node:url';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const rootIndex = process.argv.indexOf('--root');
if (rootIndex !== -1 && !process.argv[rootIndex + 1]) throw new Error('--root requires a path.');
const ROOT = rootIndex === -1 ? fileURLToPath(new URL('..', import.meta.url)) : resolve(process.argv[rootIndex + 1]);
const run = promisify(execFile);
const readJson = async path => JSON.parse(await readFile(path, 'utf8'));
const stableJson = value => `${JSON.stringify(value, null, 2)}\n`;
const hash = value => createHash('sha256').update(value).digest('hex');
const fail = message => { throw new Error(message); };
const resourceTypes = ['school', 'event', 'facility', 'other'];
const generatedPaths = [
  'data/site.v3.json',
  'data/resource-coverage.v3.json',
  'data/sources.v3.json',
  'data/source-crosswalk.v1.json',
  'data/schema.v3.json',
  'migrations/v2-to-v3.json',
  'reports/source-normalization.json',
];
const originalTopLevel = ['regions', 'negative_evidence', 'data_gaps', 'site_notes', 'typology_axes', 'coverage_by_category'];
const originalEntryFields = ['name', 'category', 'subtype', 'operator', 'school_level', 'district', 'address', 'lat', 'lng', 'year', 'games', 'source', 'theme_link', 'confidence', 'subtype_note', 'notes', 'loc_approx', 'id', 'region_id', 'scope', 'evidence_ids', 'coord_method', 'coord_note'];

async function generatedFiles(root) {
  const regions = (await readdir(join(root, 'geo/regions'))).filter(name => name.endsWith('.geojson')).sort();
  return [...generatedPaths, ...regions.map(name => `geo/regions/${name}`)];
}
async function byteGraph(root) {
  const files = await generatedFiles(root);
  return Promise.all(files.map(async path => ({ path, bytes: await readFile(join(root, path)) })));
}
function equalGraph(left, right, label) {
  if (left.length !== right.length || left.some((item, index) => item.path !== right[index].path || !item.bytes.equals(right[index].bytes))) fail(`${label} differs.`);
}
function publicNote(status) {
  return ({ current: '운영상태는 공개 자료를 바탕으로 현재로 기록되었습니다.', ended: '운영상태는 공개 자료를 바탕으로 종료로 기록되었습니다.', needs_review: '운영상태는 확인이 필요합니다. 이용 전 공개 자료를 확인해 주세요.' })[status];
}
function urls(raw) {
  return [...new Set(raw.match(/https?:\/\/[^\s;,)\]]+/g) ?? [])];
}
function sourceTokens(raw) {
  const tokens = [];
  const matcher = /https?:\/\/[^\s;,)\]]+/g;
  let cursor = 0;
  for (const match of raw.matchAll(matcher)) {
    const text = raw.slice(cursor, match.index).replace(/^[\s;,]+|[\s;,]+$/g, '');
    if (text) tokens.push({ kind: 'text', value: text });
    tokens.push({ kind: 'url', value: match[0] });
    cursor = match.index + match[0].length;
  }
  const trailing = raw.slice(cursor).replace(/^[\s;,]+|[\s;,]+$/g, '');
  if (trailing) tokens.push({ kind: 'text', value: trailing });
  return tokens;
}

function mapBy(rows, key, label) {
  const result = new Map(rows.map(row => [row[key], row]));
  if (result.size !== rows.length) fail(`${label} contains duplicate keys.`);
  return result;
}

function applyMigration(base, changes, { idempotent = false } = {}) {
  const result = structuredClone(base);
  for (const change of changes) {
    if (change?.op !== 'add' || typeof change.path !== 'string' || !/^\/[A-Za-z0-9_]+$/.test(change.path) || change.old !== null) {
      fail('Migration contains an unsupported operation or precondition.');
    }
    const key = change.path.slice(1);
    if (Object.hasOwn(result, key)) {
      if (!idempotent || stableJson(result[key]) !== stableJson(change.value)) fail(`Migration add precondition conflict at ${change.path}.`);
      continue;
    }
    result[key] = structuredClone(change.value);
  }
  return result;
}

const [first, second] = await Promise.all([mkdtemp(join(tmpdir(), 'esports-validate-')), mkdtemp(join(tmpdir(), 'esports-validate-'))]);
try {
  await run(process.execPath, ['scripts/extract-data.mjs', '--output', first], { cwd: ROOT });
  await run(process.execPath, ['scripts/extract-data.mjs', '--output', second], { cwd: ROOT });
  const firstGraph = await byteGraph(first);
  equalGraph(firstGraph, await byteGraph(second), 'Independent extraction byte graph');
  equalGraph(firstGraph, await byteGraph(ROOT), 'Tracked generated output');

  const [v2, v3, geoV2, coverage, resourceMap, sourcesFile, crosswalkFile, migration, report, schemaText, copiedSchemaText] = await Promise.all([
    readJson(join(ROOT, 'baseline/v2/site.v2.json')),
    readJson(join(ROOT, 'data/site.v3.json')),
    readJson(join(ROOT, 'baseline/v2/region-geo.v2.json')),
    readJson(join(ROOT, 'data/resource-coverage.v3.json')),
    readJson(join(ROOT, 'data/resource-map.v1.json')),
    readJson(join(ROOT, 'data/sources.v3.json')),
    readJson(join(ROOT, 'data/source-crosswalk.v1.json')),
    readJson(join(ROOT, 'migrations/v2-to-v3.json')),
    readJson(join(ROOT, 'reports/source-normalization.json')),
    readFile(join(ROOT, 'schemas/site.v3.schema.json'), 'utf8'),
    readFile(join(ROOT, 'data/schema.v3.json'), 'utf8'),
  ]);
  if (schemaText !== copiedSchemaText) fail('Published schema copy differs from the tracked schema contract.');
  const schema = JSON.parse(schemaText);
  const validateSchema = new Ajv2020({ allErrors: true, strict: true, strictRequired: false }).compile(schema);
  if (!validateSchema(v3)) fail(`Published v3 fails JSON Schema: ${JSON.stringify(validateSchema.errors)}`);
  if (v3.schema_version !== 3 || v2.entries.length !== 230 || v3.entries.length !== 230 || v2.regions.length !== 17 || v3.regions.length !== 17) fail('Expected schema v3 with 230 entries and 17 regions.');
  for (const key of originalTopLevel) if (!(key in v3) || stableJson(v2[key]) !== stableJson(v3[key])) fail(`Original top-level collection changed: ${key}.`);
  for (const key of Object.keys(v2.meta)) if (!(key in v3.meta) || stableJson(v2.meta[key]) !== stableJson(v3.meta[key])) fail(`Original metadata changed: ${key}.`);
  const v2ById = mapBy(v2.entries, 'id', 'Baseline entries');
  const v3Ids = v3.entries.map(entry => entry.id);
  if (v3Ids.length !== 230 || new Set(v3Ids).size !== 230 || v3Ids.some(id => !v2ById.has(id))) fail('Entry IDs are not a unique v2/v3 bijection.');
  if (stableJson(v2.regions) !== stableJson(v3.regions)) fail('Region lineage does not preserve the authoritative baseline.');
  if (new Set(v3.resource_types).size !== 4 || resourceTypes.some(type => !v3.resource_types.includes(type))) fail('Resource type contract is incomplete.');
  if (resourceMap.schema_version !== 1 || !['mechanically_derived_pending_owner_approval', 'approved'].includes(resourceMap.status) || !resourceMap.owner_roles || stableJson(v3.resource_map.owner_roles) !== stableJson(resourceMap.owner_roles) || v3.resource_map.status !== resourceMap.status || v3.resource_map.approved_by !== resourceMap.approved_by || v3.resource_map.approved_at !== resourceMap.approved_at || v3.resource_map.sha256 !== hash(await readFile(join(ROOT, 'data/resource-map.v1.json'), 'utf8')) || resourceMap.status === 'approved' && (!resourceMap.approved_by || !resourceMap.approved_at) || resourceMap.status !== 'approved' && (resourceMap.approved_by !== null || resourceMap.approved_at !== null)) fail('Resource map approval provenance was not preserved.');
  const mapById = mapBy(resourceMap.entries, 'entry_id', 'Resource map');
  if (resourceMap.entries.length !== 230 || mapById.size !== 230 || new Set(resourceMap.entries.map(row => row.resource_type)).size !== 4 || resourceMap.entries.some(row => !resourceTypes.includes(row.resource_type))) fail('Resource map must contain exactly 230 entries and four resource types.');
  for (const entry of v2.entries) if (mapById.get(entry.id)?.category !== entry.category) fail(`Resource map baseline category mismatch: ${entry.id}.`);
  if (coverage.total_entries !== 230 || coverage.covered_entries !== 230 || coverage.entries.length !== 230) fail('Resource coverage manifest is incomplete.');
  const coverageById = mapBy(coverage.entries, 'id', 'Coverage');
  const sourceById = mapBy(v3.sources, 'id', 'Embedded sources');
  const sourceFileById = mapBy(sourcesFile.sources, 'id', 'Published sources');
  const crosswalkById = mapBy(v3.raw_source_crosswalk, 'entry_id', 'Embedded crosswalk');
  const crosswalkFileById = mapBy(crosswalkFile.crosswalk, 'entry_id', 'Published crosswalk');
  const migrationById = mapBy(migration.entries, 'entry_id', 'Migration');
  if (sourcesFile.schema_version !== 1 || crosswalkFile.schema_version !== 1 || migration.schema_version !== 1 || migration.from_schema_version !== 2 || migration.to_schema_version !== 3 || v3.sources.length !== 230 || sourcesFile.sources.length !== 230 || v3.raw_source_crosswalk.length !== 230 || crosswalkFile.crosswalk.length !== 230 || migration.entries.length !== 230 || sourceById.size !== 230 || sourceFileById.size !== 230 || crosswalkById.size !== 230 || crosswalkFileById.size !== 230 || migrationById.size !== 230) fail('Source, crosswalk, or migration collection is incomplete.');
  for (const entry of v3.entries) {
    const original = v2ById.get(entry.id);
    for (const key of originalEntryFields) if (stableJson(entry[key]) !== stableJson(original[key])) fail(`Baseline value changed for ${entry.id}.${key}.`);
    const mapped = mapById.get(entry.id);
    if (!mapped || entry.category !== mapped.category || entry.resource_type !== mapped.resource_type || coverageById.get(entry.id)?.category !== entry.category || coverageById.get(entry.id)?.resource_type !== entry.resource_type) fail(`Resource-map-derived value changed for ${entry.id}.`);
    if (!resourceTypes.includes(entry.resource_type) || entry.source_ids?.length !== 1 || entry.source_ids[0] !== `source-${entry.id}`) fail(`Invalid resource/source reference for ${entry.id}.`);
    const source = sourceById.get(entry.source_ids[0]);
    if (!source || stableJson(source) !== stableJson(sourceFileById.get(source.id)) || source.entry_id !== entry.id || source.raw !== (original.source ?? '') || typeof source.raw !== 'string' || !source.raw.trim() || stableJson(source.urls) !== stableJson(urls(source.raw)) || source.verification_status !== 'needs_review' || source.checked_at !== null) fail(`Invalid normalized source for ${entry.id}.`);
    const crosswalk = crosswalkById.get(entry.id);
    const expectedTokens = sourceTokens(source.raw).map((token, index) => ({ position: index, kind: token.kind, raw_token: token.value, disposition: 'mapped', source_id: source.id }));
    if (expectedTokens.length === 0 || !crosswalk || stableJson(crosswalk) !== stableJson(crosswalkFileById.get(entry.id)) || crosswalk.raw_source !== source.raw || stableJson(crosswalk.source_ids) !== stableJson([source.id]) || stableJson(crosswalk.tokens) !== stableJson(expectedTokens)) fail(`Invalid source ownership/crosswalk for ${entry.id}.`);
    if (entry.off_map !== !(entry.scope === 'regional' && entry.lat != null && entry.lng != null) || !['needs_review', 'current', 'ended'].includes(entry.operational_status) || entry.public_note !== publicNote(entry.operational_status)) fail(`Unsafe derived value for ${entry.id}.`);
    if (entry.operational_status === 'needs_review' && (entry.status_provenance !== null || entry.status_checked_at !== null)) fail(`Unverified status must retain null provenance for ${entry.id}.`);
    const changes = migrationById.get(entry.id)?.changes;
    const expectedChanges = [
      { op: 'add', path: '/resource_type', old: null, value: entry.resource_type },
      { op: 'add', path: '/source_ids', old: null, value: entry.source_ids },
      { op: 'add', path: '/operational_status', old: null, value: entry.operational_status },
      { op: 'add', path: '/public_note', old: null, value: entry.public_note },
      { op: 'add', path: '/status_provenance', old: null, value: entry.status_provenance },
      { op: 'add', path: '/status_checked_at', old: null, value: entry.status_checked_at },
      { op: 'add', path: '/review', old: null, value: entry.review },
      { op: 'add', path: '/off_map', old: null, value: entry.off_map },
    ];
    if (stableJson(changes) !== stableJson(expectedChanges)) fail(`Migration manifest mismatch for ${entry.id}.`);
    const once = applyMigration(original, changes);
    const twice = applyMigration(once, changes, { idempotent: true });
    if (stableJson(once) !== stableJson(entry) || stableJson(twice) !== stableJson(once)) fail(`Migration application is not exact and idempotent for ${entry.id}.`);
  }
  const tokenCount = v3.raw_source_crosswalk.reduce((count, row) => count + row.tokens.length, 0);
  if (report.schema_version !== 1 || report.raw_source_tokens !== tokenCount || report.mapped_source_tokens !== tokenCount || report.omitted_source_tokens !== 0 || stableJson(report.summary) !== stableJson({ entries: 230, sources: 230, crosswalk_rows: 230, mapped_entries: 230, omitted_entries: 0 })) fail('Source normalization token counts are incomplete.');
  const expectedRegions = v2.regions.map(region => region.id).sort();
  const regionFiles = (await readdir(join(ROOT, 'geo/regions'))).filter(name => name.endsWith('.geojson')).sort();
  if (JSON.stringify(regionFiles) !== JSON.stringify(expectedRegions.map(id => `${id}.geojson`))) fail('Expected exactly 17 region GeoJSON files.');
  for (const id of expectedRegions) {
    const geo = await readJson(join(ROOT, 'geo/regions', `${id}.geojson`));
    if (geo.type !== 'FeatureCollection' || stableJson(geo) !== stableJson(geoV2[id])) fail(`GeoJSON baseline mismatch for ${id}.`);
  }
  console.log('Data validation passed: deterministic 230-entry, 17-region graph with resource, source, migration, and schema contracts.');
} finally {
  await Promise.all([rm(first, { recursive: true, force: true }), rm(second, { recursive: true, force: true })]);
}
