import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { createProjection, geometryPath, projectPosition } from "../src/projection.js";
import { RegionLoader, regionGeoUrl, validateRegionGeoJson } from "../src/region-loader.js";
import { filterEntries, matchesQuery, parseSearchTerms } from "../src/search.js";
import { createAppState } from "../src/state.js";
import { canonicalUrl, decodeUrl, encodeUrl } from "../src/url-codec.js";
import { validateResearchData } from "../src/research.js";

const loadJson = async (path) => JSON.parse(await readFile(new URL(path, import.meta.url), "utf8"));
const data = await loadJson("../data/site.v3.json");
const coverage = await loadJson("../data/resource-coverage.v3.json");
const resourceMap = await loadJson("../data/resource-map.v1.json");
const sourcesDocument = await loadJson("../data/sources.v3.json");
const crosswalkDocument = await loadJson("../data/source-crosswalk.v1.json");
const migrationDocument = await loadJson("../migrations/v2-to-v3.json");

test("state normalizes query and deduplicates multi-select filters", () => {
  const state = createAppState({ query: "  부산   e스포츠 ", category: ["시설", "시설", "정책"] });
  assert.equal(state.query, "부산 e스포츠");
  assert.deepEqual(state.category, ["시설", "정책"]);
});

test("URL codec keeps only allowed values and has canonical ordering", () => {
  const options = { allowed: { region: ["busan"], category: ["시설", "정책"] }, entries: ["busan-001"] };
  assert.throws(() => decodeUrl("?type=bogus"), /requires allowed values/);
  const decoded = decodeUrl("?type=bogus&category=%EC%A0%95%EC%B1%85&region=invalid&region=busan&q=%20%EB%B6%80%EC%82%B0%20%20&entry=bad&entry=busan-001", options);
  assert.equal(decoded.region, "busan");
  assert.equal(decoded.type, null);
  assert.equal(decoded.query, "부산");
  assert.equal(decoded.entry, "busan-001");
  assert.equal(encodeUrl(decoded, options), "?region=busan&q=%EB%B6%80%EC%82%B0&category=%EC%A0%95%EC%B1%85&entry=busan-001");
  assert.equal(canonicalUrl({ pathname: "/2026-esports-landscape/", search: "?q=%EB%B6%80%EC%82%B0&region=busan", hash: "#map" }, options), "/2026-esports-landscape/?region=busan&q=%EB%B6%80%EC%82%B0#map");
});

test("search supports quoted AND terms across entry fields", () => {
  const entry = { id: "entry-1", name: "부산 e스포츠 파크", operator: "부산교육청", address: "북구 의성로", search_sources: [{ id: "source-1", raw: "공식 자료", urls: ["https://example.test/evidence"], kind: "raw_source", verification_status: "verified", checked_at: "2026-01-01" }] };
  assert.deepEqual(parseSearchTerms('부산 "e스포츠 파크"'), ["부산", "e스포츠 파크"]);
  assert.equal(matchesQuery(entry, '부산 "e스포츠 파크"'), true);
  assert.equal(filterEntries([entry], { query: "서울" }).length, 0);
  assert.equal(matchesQuery(entry, "의성로"), true);
  assert.equal(matchesQuery(entry, "example.test/evidence"), true);
  assert.throws(() => matchesQuery({ id: "unresolved", name: "자료" }, "자료"), /unresolved source references/);
});

test("projection retains geometry within padded canvas and rejects invalid positions", () => {
  const geometry = { type: "Polygon", coordinates: [[[0, 0], [10, 0], [10, 5], [0, 5], [0, 0]]] };
  const projection = createProjection(geometry, { width: 100, height: 80, padding: 10 });
  const point = projectPosition([0, 5], projection);
  assert.deepEqual(point, [10, 20]);
  assert.throws(() => projectPosition([null, 5], projection), /finite positions/);
});
test("projection removes only consecutive coordinates that serialize to the same 0.1px point", () => {
  const geometry = { type: "Polygon", coordinates: [[[0, 0], [0.001, 0.001], [10, 0], [10, 10], [0, 10], [0, 0]]] };
  const projection = createProjection(geometry, { width: 100, height: 100, padding: 0 });
  assert.equal(geometryPath(geometry, projection), "M0.0,100.0L100.0,100.0L100.0,0.0L0.0,0.0L0.0,100.0Z");
});

test("projection rejects degenerate geometry and non-positive custom scales", () => {
  const flat = { type: "Polygon", coordinates: [[[0, 0], [1, 0], [2, 0], [0, 0]]] };
  assert.throws(() => createProjection(flat), /span both projection axes/);
  assert.throws(() => projectPosition([0, 0], { offsetX: 0, offsetY: 0, minX: 0, maxY: 1, scale: 0 }), /Valid projection/);
});

test("projection rejects finite coordinates whose arithmetic would overflow", () => {
  const huge = { type: "Polygon", coordinates: [[[-1e308, 0], [1e308, 0], [1e308, 1], [-1e308, 0]]] };
  assert.throws(() => createProjection(huge), /finite projection range/);
});

test("region loader uses deployment base, caches successful GeoJSON, and reports failure", async () => {
  assert.equal(regionGeoUrl("/2026-esports-landscape/", "busan"), "/2026-esports-landscape/geo/regions/busan.geojson");
  assert.throws(() => regionGeoUrl("/", "../busan"), /Invalid region id/);
  let requests = 0;
  const validGeoJson = {
    type: "FeatureCollection",
    features: [{
      type: "Feature",
      properties: {},
      geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] },
    }],
  };
  const loader = new RegionLoader({ baseUrl: "/2026-esports-landscape/", fetchImpl: async () => {
    requests += 1;
    return { ok: true, json: async () => validGeoJson };
  } });
  await loader.load("busan");
  await loader.load("busan");
  assert.equal(requests, 1);
  assert.equal(loader.getState().status, "ready");
  const failing = new RegionLoader({ baseUrl: "/", fetchImpl: async () => ({ ok: false, status: 404 }) });
  await assert.rejects(failing.load("seoul"), /404/);
  assert.equal(failing.getState().status, "error");
});

test("search applies explicit stable sort modes without promoting empty ranks", () => {
  const entries = [
    { id: "b", name: "나", year: 2024, sort: null },
    { id: "a", name: "가", year: 2025, sort: 2 },
    { id: "c", name: "다", year: null, sort: "" },
  ];
  assert.deepEqual(filterEntries(entries, { sort: "name-asc" }).map((entry) => entry.id), ["a", "b", "c"]);
  assert.deepEqual(filterEntries(entries, { sort: "year-desc" }).map((entry) => entry.id), ["a", "b", "c"]);
  assert.deepEqual(filterEntries(entries, {}).map((entry) => entry.id), ["b", "a", "c"]);
});

test("explicit sorts use canonical entry id as their deterministic tie-breaker", () => {
  const entries = [
    { id: "b", name: "동일", year: 2025 },
    { id: "a", name: "동일", year: 2025 },
  ];
  assert.deepEqual(filterEntries(entries, { sort: "name-asc" }).map((entry) => entry.id), ["a", "b"]);
  assert.deepEqual(filterEntries(entries, { sort: "year-desc" }).map((entry) => entry.id), ["a", "b"]);
  assert.deepEqual(filterEntries(entries, {}).map((entry) => entry.id), ["b", "a"]);
});

test("region loader rejects unsafe bases, missing ids, and malformed GeoJSON before ready", async () => {
  assert.throws(() => regionGeoUrl("//evil.example/base/", "busan"), /absolute path or HTTP/);
  assert.throws(() => regionGeoUrl("/", null), /region id/);
  assert.throws(() => regionGeoUrl("https://evil.example/base/", "busan", "https://example.test"), /current origin/);
  assert.throws(() => validateRegionGeoJson({ type: "FeatureCollection", features: [] }), /non-empty FeatureCollection/);
  const malformed = new RegionLoader({
    baseUrl: "/2026-esports-landscape/",
    fetchImpl: async () => ({ ok: true, json: async () => ({ type: "FeatureCollection", features: [] }) }),
  });
  await assert.rejects(malformed.load("busan"), /non-empty FeatureCollection/);
  assert.equal(malformed.getState().status, "error");
});

test("current-generation AbortError returns the loader to idle", async () => {
  const aborted = new RegionLoader({
    baseUrl: "/2026-esports-landscape/",
    fetchImpl: async () => { throw new DOMException("cancelled", "AbortError"); },
  });
  assert.equal(await aborted.load("busan"), null);
  assert.equal(aborted.getState().status, "idle");
});

test("v3 canonical public-data contract has a fixed ID digest and exact coverage", () => {
  assert.equal(data.schema_version, 3);
  assert.equal(data.meta.entry_count, 230);
  assert.equal(data.meta.region_count, 17);
  assert.equal(data.regions.length, 17);
  assert.equal(data.entries.length, 230);
  assert.equal(coverage.total_entries, 230);
  assert.equal(coverage.covered_entries, 230);
  assert.equal(coverage.entries.length, 230);

  const entryIds = data.entries.map((entry) => entry.id);
  assert.equal(new Set(entryIds).size, 230);
  assert.equal(createHash("sha256").update([...entryIds].sort().join("\n")).digest("hex"), "cedfc252550b9d9404ed19a785fd2e71d33c77fb14fd20e799c0067746d993e0");

  const sourceIds = new Set(data.sources.map((source) => source.id));
  assert.equal(sourceIds.size, data.sources.length, "source IDs must be unique");
  assert.ok(data.sources.every((source) => entryIds.includes(source.entry_id)), "each source must reference one entry");
  const coverageById = new Map(coverage.entries.map((item) => [item.id, item]));
  assert.equal(coverageById.size, 230, "coverage IDs must be unique");
  for (const entry of data.entries) {
    const covered = coverageById.get(entry.id);
    assert.deepEqual(
      covered && { id: covered.id, category: covered.category, resource_type: covered.resource_type },
      { id: entry.id, category: entry.category, resource_type: entry.resource_type },
      `${entry.id} must have exactly one matching coverage record`,
    );
    assert.ok(Array.isArray(entry.source_ids) && entry.source_ids.length > 0, `${entry.id} needs a source ref`);
    assert.ok(entry.source_ids.every((id) => sourceIds.has(id)), `${entry.id} has an unknown source ref`);
    assert.ok(entry.confidence === null || ["high", "medium", "low"].includes(entry.confidence), `${entry.id} has an invalid confidence`);
    assert.ok(typeof entry.operational_status === "string" && entry.operational_status.trim(), `${entry.id} needs an operational status`);
    assert.ok(typeof entry.public_note === "string" && entry.public_note.trim(), `${entry.id} needs a safe public note`);
  }
  assert.doesNotThrow(() => validateResearchData(data));
});

test("resource, source, token, and migration contracts are exact 230-row bijections", () => {
  const entryIds = new Set(data.entries.map((entry) => entry.id));
  assert.ok(["mechanically_derived_pending_owner_approval", "approved"].includes(resourceMap.status));
  if (resourceMap.status === "approved") {
    assert.ok(resourceMap.approved_by);
    assert.ok(resourceMap.approved_at);
  } else {
    assert.equal(resourceMap.approved_by, null);
    assert.equal(resourceMap.approved_at, null);
  }
  assert.equal(resourceMap.entries.length, 230);
  assert.equal(new Set(resourceMap.entries.map((row) => row.entry_id)).size, 230);
  assert.equal(sourcesDocument.sources.length, 230);
  assert.equal(crosswalkDocument.crosswalk.length, 230);
  assert.equal(migrationDocument.entries.length, 230);
  for (const row of crosswalkDocument.crosswalk) {
    assert.ok(entryIds.has(row.entry_id));
    assert.ok(row.tokens.length > 0);
    assert.ok(row.tokens.every((token, index) => token.position === index && token.disposition === "mapped" && row.source_ids.includes(token.source_id)));
  }
  assert.ok(migrationDocument.entries.every((row) => entryIds.has(row.entry_id) && row.changes.every((change) => change.op === "add" && change.old === null)));
});

test("research validator fails closed on source ownership, confidence, and collection corruption", () => {
  const wrongOwner = structuredClone(data);
  wrongOwner.sources[0].entry_id = wrongOwner.entries[1].id;
  assert.throws(() => validateResearchData(wrongOwner), /source ownership/);

  const invalidConfidence = structuredClone(data);
  invalidConfidence.entries[0].confidence = "certain";
  assert.throws(() => validateResearchData(invalidConfidence), /confidence/);

  const nullableConfidence = structuredClone(data);
  nullableConfidence.entries[0].confidence = null;
  assert.doesNotThrow(() => validateResearchData(nullableConfidence));
  const missingConfidence = structuredClone(data);
  delete missingConfidence.entries[0].confidence;
  assert.throws(() => validateResearchData(missingConfidence), /confidence/);

  const missingRegionName = structuredClone(data);
  delete missingRegionName.regions[0].short_name;
  assert.throws(() => validateResearchData(missingRegionName), /short region name/);

  const orphanSource = structuredClone(data);
  orphanSource.sources.push({ ...orphanSource.sources[0], id: "source-orphan" });
  assert.throws(() => validateResearchData(orphanSource), /source reverse ownership/);

  const malformedResearch = structuredClone(data);
  delete malformedResearch.negative_evidence[0].finding;
  assert.throws(() => validateResearchData(malformedResearch), /negative evidence finding/);
});

test("off-map and status disclosure invariants remain explicit", () => {
  for (const entry of data.entries) {
    if (entry.scope !== "regional" || entry.off_map) assert.equal(entry.off_map, true, `${entry.id} must remain off-map`);
    if (["current", "ended"].includes(entry.operational_status)) {
      assert.ok(entry.status_checked_at, `${entry.id} needs a status check date`);
      assert.ok(entry.status_provenance, `${entry.id} needs status provenance`);
    }
    if (entry.status_checked_at == null || entry.status_provenance == null) {
      assert.match(entry.review?.reason ?? "", /Current\/ended status has not been independently verified/);
    }
  }
});
