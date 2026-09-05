import { caseSite } from "../src/record-scope.js";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { landscapeModel } from "../src/landscape.js";

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
