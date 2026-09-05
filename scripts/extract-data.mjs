import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

import { applyReviews } from './review-overlay.mjs';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const RESOURCE_TYPES = Object.freeze(['school', 'event', 'facility', 'other']);
const RESOURCE_MAP_STATUSES = new Set(['mechanically_derived_pending_owner_approval', 'approved']);
const stableJson = value => `${JSON.stringify(value, null, 2)}\n`;
const sha256 = value => createHash('sha256').update(value).digest('hex');
const publicNote = status => ({
  current: '운영상태는 공개 자료를 바탕으로 현재로 기록되었습니다.',
  ended: '운영상태는 공개 자료를 바탕으로 종료로 기록되었습니다.',
  needs_review: '운영상태는 확인이 필요합니다. 이용 전 공개 자료를 확인해 주세요.',
}[status]);
const URL_PATTERN = /https?:\/\/[^\s;,)\]]+/g;

function sourceUrls(raw) {
  return [...new Set(raw.match(URL_PATTERN) ?? [])];
}

function sourceTokens(raw) {
  const tokens = [];
  const matcher = new RegExp(URL_PATTERN.source, 'g');
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


function normalizedSource(entry) {
  const raw = entry.source ?? '';
  if (typeof raw !== "string" || raw.trim() === "" || sourceTokens(raw).length === 0) fail(`Entry ${entry.id} has no mappable public source evidence.`);
  const urls = sourceUrls(raw);
  return { id: `source-${entry.id}`, entry_id: entry.id, raw, urls, kind: 'raw_source', verification_status: 'needs_review', checked_at: null };
}

function resourceMapById(resourceMap, allEntries) {
  if (resourceMap.schema_version !== 1 || !RESOURCE_MAP_STATUSES.has(resourceMap.status) || !resourceMap.owner_roles || Array.isArray(resourceMap.owner_roles)) fail('Resource map approval metadata is invalid.');
  if (resourceMap.status === 'approved' && (typeof resourceMap.approved_by !== 'string' || !resourceMap.approved_by || typeof resourceMap.approved_at !== 'string' || !resourceMap.approved_at)) fail('Approved resource map requires approver and timestamp.');
  if (resourceMap.status !== 'approved' && (resourceMap.approved_by !== null || resourceMap.approved_at !== null)) fail('Pending resource map must not claim approval.');
  if (!Array.isArray(resourceMap.entries) || resourceMap.entries.length !== allEntries.length) fail('Resource map must cover every published entry.');
  const byId = new Map();
  for (const row of resourceMap.entries) {
    if (!row || typeof row.entry_id !== 'string' || !row.entry_id || typeof row.category !== 'string' || !row.category || !RESOURCE_TYPES.includes(row.resource_type)) fail('Resource map contains an invalid entry.');
    if (byId.has(row.entry_id)) fail(`Resource map contains duplicate entry ID: ${row.entry_id}.`);
    byId.set(row.entry_id, row);
  }
  if (byId.size !== allEntries.length || new Set([...byId.values()].map(row => row.resource_type)).size !== 4) fail('Resource map must contain exactly four resource types.');
  if (new Set(allEntries.map(entry => entry.id)).size !== allEntries.length) fail('Published entries must have unique IDs.');
  for (const entry of allEntries) {
    const mapped = byId.get(entry.id);
    if (!mapped || mapped.category !== entry.category) fail(`Resource map does not match baseline ID/category: ${entry.id}.`);
  }
  return byId;
}

function fail(message) {
  throw new Error(message);
}

async function generate(output) {
  const [siteText, geoText, additionsText, resourceMapText, schemaText] = await Promise.all([
    readFile(join(ROOT, 'baseline/v2/site.v2.json'), 'utf8'),
    readFile(join(ROOT, 'baseline/v2/region-geo.v2.json'), 'utf8'),
    readFile(join(ROOT, 'data/additions.v1.json'), 'utf8'),
    readFile(join(ROOT, 'data/resource-map.v1.json'), 'utf8'),
    readFile(join(ROOT, 'schemas/site.v3.schema.json'), 'utf8'),
  ]);
  const siteV2 = JSON.parse(siteText);
  const regionGeoV2 = JSON.parse(geoText);
  const additions = JSON.parse(additionsText);
  const resourceMap = JSON.parse(resourceMapText);
  JSON.parse(schemaText);
  if (siteV2.entries?.length !== 230 || siteV2.regions?.length !== 17) fail('Expected the authoritative v2 input to contain 230 entries and 17 regions.');
  if (additions.schema_version !== 1 || !/^\d{4}-\d{2}-\d{2}$/.test(additions.updated_at) || !Array.isArray(additions.entries)) fail('Additions file is invalid.');
  const sourceEntries = [...siteV2.entries, ...additions.entries];
  const resourceById = resourceMapById(resourceMap, sourceEntries);
  const regionIds = siteV2.regions.map(region => region.id);
  if (new Set(regionIds).size !== 17 || regionIds.some(id => !regionGeoV2[id] || regionGeoV2[id].type !== 'FeatureCollection')) fail('Authoritative region lineage is incomplete.');

  const sources = sourceEntries.map(normalizedSource);
  const crosswalk = sources.map(source => ({
    entry_id: source.entry_id,
    raw_source: source.raw,
    source_ids: [source.id],
    tokens: sourceTokens(source.raw).map((token, index) => ({
      position: index,
      kind: token.kind,
      raw_token: token.value,
      disposition: 'mapped',
      source_id: source.id,
    })),
  }));
  const entries = sourceEntries.map(entry => {
    const mapped = resourceById.get(entry.id);
    return {
      ...entry,
      category: mapped.category,
      resource_type: mapped.resource_type,
      source_ids: [`source-${entry.id}`],
      operational_status: 'needs_review',
      public_note: publicNote('needs_review'),
      status_provenance: null,
      status_checked_at: null,
      review: { status: 'needs_review', reason: 'Current/ended status has not been independently verified.' },
      off_map: !(entry.scope === 'regional' && entry.lat != null && entry.lng != null),
    };
  });
  const migrations = entries.slice(0, siteV2.entries.length).map(entry => ({
    entry_id: entry.id,
    changes: [
      { op: 'add', path: '/resource_type', old: null, value: entry.resource_type },
      { op: 'add', path: '/source_ids', old: null, value: entry.source_ids },
      { op: 'add', path: '/operational_status', old: null, value: entry.operational_status },
      { op: 'add', path: '/public_note', old: null, value: entry.public_note },
      { op: 'add', path: '/status_provenance', old: null, value: entry.status_provenance },
      { op: 'add', path: '/status_checked_at', old: null, value: entry.status_checked_at },
      { op: 'add', path: '/review', old: null, value: entry.review },
      { op: 'add', path: '/off_map', old: null, value: entry.off_map },
    ],
  }));
  const v3 = {
    ...siteV2,
    schema_version: 3,
    meta: { ...siteV2.meta, entry_count: entries.length, data_updated_at: additions.updated_at, source_schema_version: siteV2.schema_version, extraction: { input: 'baseline/v2/site.v2.json', sha256: sha256(siteText) }, additions: { input: 'data/additions.v1.json', count: additions.entries.length, sha256: sha256(additionsText) }, region_lineage: { input: 'baseline/v2/region-geo.v2.json', sha256: sha256(geoText) } },
    coverage_by_category: [...entries.reduce((counts, entry) => counts.set(entry.category, (counts.get(entry.category) ?? 0) + 1), new Map())].map(([category, count]) => ({ category, count })).sort((left, right) => right.count - left.count || left.category.localeCompare(right.category, 'ko')),
    resource_types: RESOURCE_TYPES,
    resource_map: { schema_version: resourceMap.schema_version, status: resourceMap.status, owner_roles: resourceMap.owner_roles, approved_by: resourceMap.approved_by, approved_at: resourceMap.approved_at, input: 'data/resource-map.v1.json', sha256: sha256(resourceMapText) },
    entries,
    sources,
    raw_source_crosswalk: crosswalk,
  };
  const published = process.argv.includes('--base-only') ? v3 : applyReviews(v3, JSON.parse(await readFile(join(ROOT, 'data/approved-reviews.v1.json'), 'utf8')));
  const coverage = { schema_version: 1, total_entries: published.entries.length, covered_entries: published.entries.length, entries: published.entries.map(entry => ({ id: entry.id, category: entry.category, resource_type: entry.resource_type })) };
  const migration = { schema_version: 1, from_schema_version: 2, to_schema_version: 3, entries: migrations };
  const normalization = {
    schema_version: 1,
    raw_source_tokens: crosswalk.reduce((count, row) => count + row.tokens.length, 0),
    mapped_source_tokens: crosswalk.reduce((count, row) => count + row.tokens.filter(token => token.disposition === 'mapped').length, 0),
    omitted_source_tokens: 0,
    summary: { entries: entries.length, sources: sources.length, crosswalk_rows: crosswalk.length, mapped_entries: entries.length, omitted_entries: 0 },
  };
  await Promise.all([
    mkdir(join(output, 'data'), { recursive: true }),
    mkdir(join(output, 'geo/regions'), { recursive: true }),
    mkdir(join(output, 'migrations'), { recursive: true }),
    mkdir(join(output, 'reports'), { recursive: true }),
  ]);
  await Promise.all([
    writeFile(join(output, 'data/site.v3.json'), stableJson(published)),
    writeFile(join(output, 'data/resource-coverage.v3.json'), stableJson(coverage)),
    writeFile(join(output, 'data/sources.v3.json'), stableJson({ schema_version: 1, sources: published.sources })),
    writeFile(join(output, 'data/source-crosswalk.v1.json'), stableJson({ schema_version: 1, crosswalk })),
    writeFile(join(output, 'data/schema.v3.json'), schemaText),
    writeFile(join(output, 'migrations/v2-to-v3.json'), stableJson(migration)),
    writeFile(join(output, 'reports/source-normalization.json'), stableJson(normalization)),
    ...siteV2.regions.map(region => writeFile(join(output, 'geo/regions', `${region.id}.geojson`), stableJson(regionGeoV2[region.id]))),
  ]);
  return { entries: entries.length, regions: regionIds.length, sources: sources.length };
}

async function replaceGenerated(stage) {
  const stagedGeo = join(stage, 'geo/regions');
  const targetGeo = join(ROOT, 'geo/regions');
  await mkdir(join(ROOT, 'data'), { recursive: true });
  await mkdir(join(ROOT, 'migrations'), { recursive: true });
  await mkdir(join(ROOT, 'reports'), { recursive: true });
  await mkdir(targetGeo, { recursive: true });
  for (const file of ['site.v3.json', 'resource-coverage.v3.json', 'sources.v3.json', 'source-crosswalk.v1.json', 'schema.v3.json']) await rename(join(stage, 'data', file), join(ROOT, 'data', file));
  await rename(join(stage, 'migrations/v2-to-v3.json'), join(ROOT, 'migrations/v2-to-v3.json'));
  await rename(join(stage, 'reports/source-normalization.json'), join(ROOT, 'reports/source-normalization.json'));
  const allowed = new Set(await readdir(stagedGeo));
  for (const file of await readdir(targetGeo)) if (file.endsWith('.geojson') && !allowed.has(file)) await rm(join(targetGeo, file));
  for (const file of allowed) await rename(join(stagedGeo, file), join(targetGeo, file));
}

const outputFlag = process.argv.indexOf('--output');
const output = outputFlag === -1 ? null : process.argv[outputFlag + 1];
if (process.argv.includes('--base-only') && !output) throw new Error('Base-only extraction requires an isolated output directory');
if (outputFlag !== -1 && !output) throw new Error('Usage: extract-data.mjs [--output directory]');
const stage = output ?? join(ROOT, `.extract-stage-${process.pid}`);
if (!output) {
  await rm(stage, { recursive: true, force: true });
  await mkdir(stage, { recursive: true });
}
try {
  const result = await generate(stage);
  if (!output) await replaceGenerated(stage);
  console.log(`Extracted ${result.entries} entries, ${result.regions} regions, and ${result.sources} normalized sources.`);
} finally {
  if (!output) await rm(stage, { recursive: true, force: true });
}
