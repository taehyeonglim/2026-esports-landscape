export const CATEGORY_ORDER = Object.freeze([
  "교육청대회·사업",
  "지자체정책·조례",
  "협회사업",
  "학교동아리·팀",
  "특성화고학과·과정",
  "대학학과·전공·동아리",
  "경기장·인프라",
  "언론보도",
]);

function requireArray(value, label) {
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  return value;
}

/** 알려진 정식 순서를 우선하고, 데이터에만 있는 카테고리는 뒤에 가나다순으로 붙인다. */
export function categoryColumns(entries) {
  const present = new Set(requireArray(entries, "entries").map((entry) => String(entry.category)));
  const known = CATEGORY_ORDER.filter((category) => present.has(category));
  const unknown = [...present].filter((category) => !CATEGORY_ORDER.includes(category))
    .sort((left, right) => left.localeCompare(right, "ko"));
  return [...known, ...unknown];
}

export function matrixModel(entries, regions) {
  requireArray(entries, "entries");
  requireArray(regions, "regions");
  const categories = categoryColumns(entries);
  const counts = new Map();
  for (const entry of entries) {
    const key = `${entry.region_id}|${entry.category}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const rows = regions.map((region) => {
    const cells = categories.map((category) => ({
      category,
      count: counts.get(`${region.id}|${category}`) ?? 0,
    }));
    return {
      regionId: region.id,
      regionName: region.name,
      cells,
      total: cells.reduce((sum, cell) => sum + cell.count, 0),
    };
  });
  const columnTotals = categories.map((category, index) => ({
    category,
    count: rows.reduce((sum, row) => sum + row.cells[index].count, 0),
  }));
  const grandTotal = rows.reduce((sum, row) => sum + row.total, 0);
  if (grandTotal !== entries.length) throw new RangeError("Matrix totals must cover every entry exactly once.");
  return { categories, rows, columnTotals, grandTotal };
}
