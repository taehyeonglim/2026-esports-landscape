import { caseSite } from "../src/record-scope.js";
import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { editorialModel } from "../src/editorial.js";

const site = caseSite(JSON.parse(await readFile(new URL("../data/site.v3.json", import.meta.url), "utf8")));

test("editorial model turns the full dataset into four movements and three evidence-linked stories", () => {
  const model = editorialModel(site);
  assert.deepEqual(model.insights.map(({ count }) => count), ['event','school','facility','other'].map(type=>site.entries.filter(e=>e.resource_type===type).length));
  assert.equal(model.insights.reduce((sum, insight) => sum + insight.count, 0), site.entries.length);
  assert.equal(model.featured.length, 3);
  for (const feature of model.featured) {
    assert.ok(site.entries.some((entry) => entry.id === feature.id));
    assert.ok(feature.name);
    assert.ok(feature.note);
    assert.ok(feature.operator);
  }
});
