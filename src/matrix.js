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

export function renderMatrix(container, model, onSelect) {
  const table = document.createElement("table");
  table.className = "compare-matrix";
  const caption = document.createElement("caption");
  caption.className = "sr-only";
  caption.textContent = "시·도별, 카테고리별 공개자료 확인 사례 수";
  table.append(caption);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.scope = "col";
  corner.textContent = "시·도";
  headRow.append(corner);
  for (const category of model.categories) {
    const th = document.createElement("th");
    th.scope = "col";
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.category = category;
    button.textContent = category;
    button.setAttribute("aria-label", `전 지역 ${category} 사례 보기`);
    button.addEventListener("click", () => onSelect({ category }));
    th.append(button);
    headRow.append(th);
  }
  const totalHead = document.createElement("th");
  totalHead.scope = "col";
  totalHead.textContent = "합계";
  headRow.append(totalHead);
  thead.append(headRow);
  table.append(thead);

  const tbody = document.createElement("tbody");
  for (const row of model.rows) {
    const tr = document.createElement("tr");
    const rowHead = document.createElement("th");
    rowHead.scope = "row";
    const regionButton = document.createElement("button");
    regionButton.type = "button";
    regionButton.dataset.region = row.regionId;
    regionButton.textContent = row.regionName;
    regionButton.setAttribute("aria-label", `${row.regionName} 전체 사례 보기`);
    regionButton.addEventListener("click", () => onSelect({ regionId: row.regionId }));
    rowHead.append(regionButton);
    tr.append(rowHead);
    for (const cell of row.cells) {
      const td = document.createElement("td");
      if (cell.count > 0) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.region = row.regionId;
        button.dataset.category = cell.category;
        button.textContent = String(cell.count);
        button.setAttribute("aria-label", `${row.regionName} ${cell.category} ${cell.count}건 보기`);
        button.addEventListener("click", () => onSelect({ regionId: row.regionId, category: cell.category }));
        td.append(button);
      } else {
        td.textContent = "·";
        td.className = "matrix-empty";
      }
      tr.append(td);
    }
    const rowTotal = document.createElement("td");
    rowTotal.className = "matrix-total";
    rowTotal.textContent = String(row.total);
    tr.append(rowTotal);
    tbody.append(tr);
  }
  table.append(tbody);

  const tfoot = document.createElement("tfoot");
  const footRow = document.createElement("tr");
  const footHead = document.createElement("th");
  footHead.scope = "row";
  footHead.textContent = "합계";
  footRow.append(footHead);
  for (const column of model.columnTotals) {
    const td = document.createElement("td");
    td.className = "matrix-total";
    td.textContent = String(column.count);
    footRow.append(td);
  }
  const grand = document.createElement("td");
  grand.className = "matrix-total";
  grand.textContent = String(model.grandTotal);
  footRow.append(grand);
  tfoot.append(footRow);
  table.append(tfoot);

  container.replaceChildren(table);
}
