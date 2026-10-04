import { caseSite } from "../src/record-scope.js";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { landscapeModel } from "../src/landscape.js";
import { initialPane, panelMode } from "../src/explorer-view.js";
import { createAppState } from "../src/state.js";
import { filterEntries } from "../src/search.js";

const site = caseSite(JSON.parse(await readFile(new URL("../data/site.v3.json", import.meta.url), "utf8")));
const nationalMap = JSON.parse(await readFile(new URL("../data/national-map.v1.json", import.meta.url), "utf8"));

test("landscape model partitions all case entries into 17 interactive regions", () => {
  const model = landscapeModel(site.entries, site.regions);
  assert.equal(model.total, site.entries.length);
  assert.equal(model.regions.length, 17);
  assert.equal(model.byId.size, 17);
  assert.equal(model.regions.reduce((sum, region) => sum + region.total, 0), site.entries.length);
  assert.equal(model.nationalCategoryTotals.reduce((sum, category) => sum + category.count, 0), site.entries.length);
  assert.equal(model.topRegions.length, 3);
  for (const region of model.regions) {
    assert.ok(region.total > 0);
    assert.ok(region.density >= 1 && region.density <= 5);
    assert.equal(region.categoryTotals.reduce((sum, category) => sum + category.count, 0), region.total);
    assert.ok(region.featured.length > 0 && region.featured.length <= 3);
  }
});

test("national map is a compact exact 17-region runtime asset", () => {
  assert.equal(nationalMap.schema_version, 1);
  assert.equal(nationalMap.regions.length, 17);
  assert.deepEqual(new Set(nationalMap.regions.map((region) => region.id)), new Set(site.regions.map((region) => region.id)));
  assert.ok(Buffer.byteLength(JSON.stringify(nationalMap)) <= 150_000);
  for (const region of nationalMap.regions) assert.match(region.path, /^M/);
});

test("landscape model fails closed when entries escape the region partition", () => {
  assert.throws(() => landscapeModel(null, site.regions), /array/);
  assert.throws(() => landscapeModel([{ ...site.entries[0], region_id: "ghost" }], site.regions), /exactly once/);
});

test("map scale stays fixed while filtered counts partition results including empty regions", () => {
  const all = landscapeModel(site.entries, site.regions);
  for (const category of ["학교동아리·팀", "교육청대회·사업", "no-matches"]) {
    const conditions = { category: [category] };
    const map = landscapeModel(filterEntries(site.entries, conditions), site.regions, { maximum: all.maximum });
    assert.equal(map.step, all.step);
    for (const region of map.regions) {
      assert.equal(region.total, filterEntries(site.entries, { ...conditions, region: region.id }).length);
      assert.equal(region.density === 0, region.total === 0);
    }
  }
});

test("cold visits start on map while every existing deep-link filter opens results", () => {
  assert.equal(initialPane(createAppState()), "map");
  for (const key of ["entry", "region", "type", "query", "sort", "category", "schoolLevel", "theme", "scope", "status", "reviewState"]) {
    const value = key === "sort" ? "year-desc" : "example";
    assert.equal(initialPane(createAppState({ [key]: value })), "list", key);
  }
});


test("result panel presentation preserves full-map, half-sheet and short-screen states without URL fields", () => {
  assert.equal(panelMode("map", { compact: true, expanded: true }), "closed");
  assert.equal(panelMode("list"), "list");
  assert.equal(panelMode("list", { compact: true }), "list");
  assert.equal(panelMode("list", { compact: true, expanded: true }), "expanded");
  assert.equal(panelMode("list", { compact: true, shortViewport: true }), "expanded");
  assert.equal(panelMode("list", { expanded: true }), "list");
});
