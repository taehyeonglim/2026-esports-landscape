import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { CATEGORY_ORDER, categoryColumns, matrixModel } from "../src/matrix.js";

const site = JSON.parse(await readFile(new URL("../data/site.v3.json", import.meta.url), "utf8"));

test("matrix model is an exact 232-entry partition across 17 regions", () => {
  const model = matrixModel(site.entries, site.regions);
  assert.equal(model.grandTotal, 232);
  assert.equal(model.rows.length, 17);
  assert.equal(model.rows.reduce((sum, row) => sum + row.total, 0), 232);
  assert.equal(model.columnTotals.reduce((sum, column) => sum + column.count, 0), 232);
  assert.deepEqual(model.rows.map((row) => row.regionId), site.regions.map((region) => region.id));
  const busan = model.rows.find((row) => row.regionId === "busan");
  assert.equal(busan.cells.find((cell) => cell.category === "교육청대회·사업").count, 3);
  assert.equal(busan.cells.find((cell) => cell.category === "특성화고학과·과정").count, 2);
});

test("category columns keep canonical order and append unknown categories alphabetically", () => {
  const entries = [
    { region_id: "a", category: "언론보도" },
    { region_id: "a", category: "새유형B" },
    { region_id: "b", category: "교육청대회·사업" },
    { region_id: "b", category: "새유형A" },
  ];
  assert.deepEqual(categoryColumns(entries), ["교육청대회·사업", "언론보도", "새유형A", "새유형B"]);
  assert.equal(CATEGORY_ORDER.length, 8);
  const model = matrixModel(entries, [{ id: "a", name: "A" }, { id: "b", name: "B" }]);
  assert.deepEqual(model.rows.map((row) => row.total), [2, 2]);
  assert.equal(model.grandTotal, 4);
});

test("matrix model fails closed on malformed input and uncovered regions", () => {
  assert.throws(() => matrixModel(null, []), /array/);
  assert.throws(() => matrixModel([{ region_id: "ghost", category: "x" }], [{ id: "a", name: "A" }]), /exactly once/);
});
