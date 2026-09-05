import assert from "node:assert/strict";
import test from "node:test";
import { access, readFile, readdir } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";

const root = new URL("../dist/", import.meta.url);
const read = (relativePath) => readFile(new URL(relativePath, root), "utf8");
const readBytes = (relativePath) => readFile(new URL(relativePath, root));
const exists = async (relativePath) => { await access(new URL(relativePath, root)); };
const localReferences = (html) => [...html.matchAll(/(?:href|src)="([^"]+)"/g)].map((match) => match[1])
  .filter((reference) => !/^(?:[a-z]+:|#)/i.test(reference));
const releasePath = (reference) => reference.replace(/^\//, "").replace(/\/$/, "/index.html");

async function releaseFiles(directory = root, prefix = "") {
  const entries = await readdir(directory, { withFileTypes: true });
  const nested = await Promise.all(entries.map((entry) => {
    const relative = path.posix.join(prefix, entry.name);
    const target = new URL(entry.isDirectory() ? `${entry.name}/` : entry.name, directory);
    return entry.isDirectory() ? releaseFiles(target, relative) : [relative];
  }));
  return nested.flat().sort();
}

test("built release has base-aware app, data, GeoJSON, and research surfaces", async () => {
  for (const relativePath of [
    "index.html", "src/app.js", "src/research.js", "styles/main.css", "styles/research.css", "styles/shell.css",
    "assets/esports-landscape-mark.png", "assets/favicon-32.png", "assets/icon-192.png", "assets/icon-512.png", "assets/apple-touch-icon.png",
    "data/site.v3.json", "data/national-map.v1.json", "data/resource-coverage.v3.json", "geo/regions/busan.geojson", "research/index.html", "release-manifest.json",
  ]) await exists(relativePath);
  const [app, research] = await Promise.all([read("src/app.js"), read("src/research.js")]);
  assert.match(app, /new URL\("\.\/", document\.baseURI\)/);
  assert.match(app, /new URL\("data\/site\.v3\.json", baseUrl\)/);
  assert.match(app, /new URL\("data\/national-map\.v1\.json", baseUrl\)/);
  assert.match(research, /new URL\("\.\.\/data\/site\.v3\.json", import\.meta\.url\)/);
});

test("public DOM exposes the search-first workspace before one national map and responsive detail panel", async () => {
  const [html, app] = await Promise.all([read("index.html"), read("src/app.js")]);
  const cardsAt = html.indexOf('id="result-list"');
  const mapAt = html.indexOf('id="national-map"');
  assert.ok(cardsAt >= 0 && mapAt > cardsAt, "entry cards must precede the map in DOM order");
  for (const selector of ["workspace", "browse-tab", "compare-tab", "browse-view", "compare-view", "region-select", "entry-search", "filter-panel", "active-filters", "detail-panel", "detail-back", "live-status"]) assert.match(html, new RegExp(`id="${selector}"`));
  assert.match(html, /id="compare-matrix"/);
  assert.match(html, /role="tablist"/);
  assert.match(html, /시·도 공식 순서로 비교합니다/);
  for (const selector of ["national-map", "map-readout", "region-shortcuts", "map-context", "snapshot", "selected", "editorial-insights", "featured-stories", "load-more"]) assert.match(html, new RegExp(`id="${selector}"`));
  assert.doesNotMatch(html, /id="region-map"|id="region-lens"|class="story-break"/);
  assert.match(html, /assets\/esports-landscape-mark\.png/);
  assert.match(html, /rel="icon"[^>]+assets\/favicon-32\.png/);
  assert.match(html, /href="https:\/\/github\.com\/taehyeonglim"/);
  assert.match(html, />Taehyeong Lim<\/a>/);
  assert.match(html, /class="category-actions"/);
  assert.match(html, /id="type-filter"/);
  assert.match(html, /aria-live=/);
  assert.match(html, /<dialog\s+id="detail-panel"/);
  assert.match(html, /<dialog\s+id="filter-panel"/);
  assert.doesNotMatch(app, /RegionLoader|projectGeoJson|geo\/regions|map-worker/);
  assert.match(app, /data\/national-map\.v1\.json/);
  assert.match(app, /view:\s*"browse"/);
});

test("landing copy presents data directly without editorial metaphors", async () => {
  const [html, editorial, landscape] = await Promise.all([
    read("index.html"), read("src/editorial.js"), read("src/landscape.js"),
  ]);
  const landingCopy = `${html}\n${editorial}\n${landscape}`;
  assert.doesNotMatch(landingCopy, /시작|흐름|장면|출발점|이어|놓인다|이동하세요|생태계|숫자가 현장/);
  for (const statement of ["공개자료 사례를 검색", "공개자료 유형별 현황", "대표 사례", "원문 출처"]) {
    assert.match(html, new RegExp(statement));
  }
  assert.match(editorial, /대회·행사 유형으로 분류된 공개자료입니다/);
  assert.match(landscape, /17개 시·도 공개자료 현황/);
});

test("release graph resolves local links, all 17 GeoJSON regions, and checked manifest assets", async () => {
  const [index, research, researchScript, dataText, manifestText] = await Promise.all([
    read("index.html"), read("research/index.html"), read("src/research.js"), read("data/site.v3.json"), read("release-manifest.json"),
  ]);
  assert.match(research, /href="\.\.\/index\.html#workspace"/);
  assert.match(research, /rel="icon"[^>]+\.\.\/assets\/favicon-32\.png/);
  assert.match(research, /src="\.\.\/src\/research\.js"/);
  assert.match(research, /id="research-load-error"[^>]*role="alert"/);
  assert.match(research, /<(?:ul)[^>]*id="(?:typology-axes|negative-evidence|data-gaps|site-notes)"/);
  assert.match(researchScript, /미기록/);
  assert.match(research, /현재 운영 상태를 보장하지 않습니다/);
  for (const [documentPath, html] of [["index.html", index], ["research/index.html", research]]) {
    for (const reference of localReferences(html)) {
      const target = path.posix.normalize(path.posix.join(path.posix.dirname(documentPath), releasePath(reference)));
      await exists(target);
    }
  }

  const data = JSON.parse(dataText);
  assert.equal(data.regions.length, 17);
  for (const region of data.regions) {
    assert.match(region.geojson_ref, /^geo\/regions\/[a-z]+\.geojson$/);
    const geojson = JSON.parse(await read(region.geojson_ref));
    assert.equal(geojson.type, "FeatureCollection", `${region.id} must publish GeoJSON`);
  }

  const manifest = JSON.parse(manifestText);
  assert.ok(Array.isArray(manifest.assets));
  assert.deepEqual(manifest.assets.map((asset) => asset.path), [...manifest.assets.map((asset) => asset.path)].sort(), "manifest assets must be path-sorted");
  const paths = new Set();
  for (const asset of manifest.assets) {
    assert.equal(typeof asset.path, "string");
    assert.match(asset.path, /^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$)).+/, "manifest paths must be release-relative");
    assert.ok(!paths.has(asset.path), `duplicate manifest path: ${asset.path}`);
    paths.add(asset.path);
    assert.match(asset.sha256, /^[a-f0-9]{64}$/);
    assert.ok(Number.isInteger(asset.bytes) && asset.bytes >= 0, `${asset.path} must record byte length`);
    assert.equal(typeof asset.mime, "string", `${asset.path} must record MIME`);
    const bytes = await readBytes(asset.path);
    assert.equal(bytes.length, asset.bytes, `${asset.path} byte length`);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), asset.sha256, `${asset.path} checksum`);
  }
  const expectedGeo = new Set(data.regions.map((region) => region.geojson_ref));
  assert.deepEqual(new Set([...paths].filter((entry) => entry.startsWith("geo/regions/"))), expectedGeo);
  for (const required of ["index.html", "research/index.html", "src/research.js", "src/landscape.js", "styles/shell.css", "styles/research.css", "data/site.v3.json", "data/national-map.v1.json", "input-provenance.json"]) assert.ok(paths.has(required));
  assert.ok(!paths.has("release-manifest.json"), "self artifact must not affect release identity");
  assert.deepEqual(
    [...paths].sort(),
    (await releaseFiles()).filter((assetPath) => assetPath !== "release-manifest.json"),
    "manifest must cover every deployed regular file exactly once",
  );
  assert.deepEqual(manifest.identity_exclusions, ["input-provenance.json"], "identity exclusions are a closed allowlist");
  const projection = manifest.assets
    .filter((asset) => !manifest.identity_exclusions.includes(asset.path))
    .map(({ path: assetPath, sha256 }) => ({ path: assetPath, sha256 }));
  const digest = createHash("sha256").update(JSON.stringify(projection)).digest("hex");
  assert.equal(manifest.content_digest, digest);
  assert.equal(manifest.release_id, digest);
  assert.equal(manifest.release_sha256, digest);
});

test("research deployment preserves one accessible failure surface and diagnostics", async () => {
  const [research, researchHtml] = await Promise.all([read("src/research.js"), read("research/index.html")]);
  assert.match(researchHtml, /id="research-load-error"[^>]*role="alert"[^>]*hidden/);
  assert.match(research, /catch \(error\)/);
  assert.match(research, /console\.error\("Research data loading or rendering failed:"/);
  assert.doesNotMatch(research, /review\?\./);
});


test("private workbench and approval inputs are absent from public artifacts", async () => {
  for (const file of ['admin/index.html','admin/admin.js','artifacts/workbench/reviews.sqlite3','data/approved-reviews.v1.json','src/esports_data/admin.py']) await assert.rejects(access(new URL(file,root)));
});
