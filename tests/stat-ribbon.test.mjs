import assert from "node:assert/strict";
import test from "node:test";
import { statRibbonModel } from "../src/stat-ribbon.js";

test("stat ribbon model mirrors loaded public data counts exactly", () => {
  const site = { entries: Array(3).fill({}), regions: Array(2).fill({}), sources: Array(5).fill({}) };
  assert.deepEqual(statRibbonModel(site), [
    { value: 3, label: "ENTRIES" },
    { value: 2, label: "REGIONS" },
    { value: 5, label: "SOURCES" },
  ]);
});

test("stat ribbon model fails closed on malformed collections", () => {
  assert.throws(() => statRibbonModel({ entries: [], regions: null, sources: [] }), /array/);
});
