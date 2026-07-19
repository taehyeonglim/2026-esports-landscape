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

const CATEGORY_COLORS = Object.freeze([
  "#f4c64f",
  "#52c7dc",
  "#f07c67",
  "#78c79b",
  "#a995e8",
  "#ef9abb",
  "#79a7db",
  "#b4c1cb",
]);

function renderExactTable(model, onSelect) {
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

  return table;
}

function chartRow(row, maximum, colors, onSelect) {
  const article = document.createElement("div");
  article.className = "matrix-chart-row";
  article.dataset.region = row.regionId;

  const regionButton = document.createElement("button");
  regionButton.type = "button";
  regionButton.className = "matrix-chart-label";
  regionButton.dataset.region = row.regionId;
  regionButton.textContent = row.regionName;
  regionButton.setAttribute("aria-label", `${row.regionName} 전체 사례 ${row.total}건 보기`);
  regionButton.addEventListener("click", () => onSelect({ regionId: row.regionId }));

  const track = document.createElement("div");
  track.className = "matrix-bar-track";
  track.setAttribute("aria-label", `${row.regionName} 유형별 공개자료`);
  for (const [index, cell] of row.cells.entries()) {
    if (cell.count === 0) continue;
    const segment = document.createElement("button");
    segment.type = "button";
    segment.className = "matrix-segment";
    segment.dataset.region = row.regionId;
    segment.dataset.category = cell.category;
    segment.dataset.count = String(cell.count);
    segment.style.setProperty("--segment-width", `${(cell.count / maximum) * 100}%`);
    segment.style.setProperty("--category-color", colors[index]);
    segment.setAttribute("aria-label", `${row.regionName} ${cell.category} ${cell.count}건 보기`);
    segment.title = `${cell.category} · ${cell.count}건`;
    if (cell.count / maximum >= 0.075) {
      const count = document.createElement("span");
      count.textContent = String(cell.count);
      count.setAttribute("aria-hidden", "true");
      segment.append(count);
    }
    segment.addEventListener("click", () => onSelect({ regionId: row.regionId, category: cell.category }));
    track.append(segment);
  }

  const total = document.createElement("strong");
  total.className = "matrix-chart-total";
  total.textContent = String(row.total);
  total.setAttribute("aria-label", `${row.total}건`);
  article.append(regionButton, track, total);
  return article;
}

export function renderMatrix(container, model, onSelect) {
  const colors = model.categories.map((_, index) => CATEGORY_COLORS[index % CATEGORY_COLORS.length]);
  const maximum = Math.max(1, ...model.rows.map((row) => row.total));
  const visualization = document.createElement("section");
  visualization.className = "matrix-visualization";
  visualization.setAttribute("aria-labelledby", "matrix-chart-title");

  const chartHeader = document.createElement("div");
  chartHeader.className = "matrix-chart-header";
  const headingGroup = document.createElement("div");
  const title = document.createElement("h3");
  title.id = "matrix-chart-title";
  title.textContent = "지역별 공개자료 구성";
  const summary = document.createElement("p");
  summary.className = "matrix-chart-summary";
  summary.textContent = `${model.grandTotal}건 · ${model.rows.length}개 시·도 · ${model.categories.length}개 유형`;
  headingGroup.append(title, summary);

  chartHeader.append(headingGroup);

  const legend = document.createElement("div");
  legend.className = "matrix-legend";
  legend.setAttribute("aria-label", "활동 유형 필터");
  for (const [index, column] of model.columnTotals.entries()) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.category = column.category;
    button.style.setProperty("--category-color", colors[index]);
    button.setAttribute("aria-label", `전 지역 ${column.category} ${column.count}건 보기`);
    const swatch = document.createElement("i");
    swatch.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = column.category;
    const count = document.createElement("strong");
    count.textContent = String(column.count);
    button.append(swatch, label, count);
    button.addEventListener("click", () => onSelect({ category: column.category }));
    legend.append(button);
  }

  const axis = document.createElement("div");
  axis.className = "matrix-chart-axis";
  axis.innerHTML = `<span></span><div><span>0</span><span>${Math.round(maximum / 2)}</span><span>${maximum}</span></div><span>건</span>`;
  const rowContainer = document.createElement("div");
  rowContainer.className = "matrix-chart-rows";
  rowContainer.replaceChildren(...model.rows.map((row) => chartRow(row, maximum, colors, onSelect)));
  visualization.append(chartHeader, legend, axis, rowContainer);

  const tableDetails = document.createElement("details");
  tableDetails.className = "matrix-table-details";
  const tableSummary = document.createElement("summary");
  tableSummary.textContent = "정확한 수치 표 보기";
  const tableScroll = document.createElement("div");
  tableScroll.className = "matrix-scroll";
  tableScroll.append(renderExactTable(model, onSelect));
  tableDetails.append(tableSummary, tableScroll);

  container.replaceChildren(visualization, tableDetails);
}
