const DENSITY_LEVELS = 5;

function requireArray(value, label) {
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  return value;
}

function recentFirst(left, right) {
  return String(right.year || "").localeCompare(String(left.year || ""), "ko") || left.name.localeCompare(right.name, "ko");
}

export function landscapeModel(entries, regions, { maximum: scaleMaximum } = {}) {
  requireArray(entries, "entries");
  requireArray(regions, "regions");
  const models = regions.map((region) => {
    const regionEntries = entries.filter((entry) => entry.region_id === region.id).sort(recentFirst);
    const categories = new Map();
    for (const entry of regionEntries) categories.set(entry.category, (categories.get(entry.category) ?? 0) + 1);
    const categoryTotals = [...categories].map(([category, count]) => ({ category, count }))
      .sort((left, right) => right.count - left.count || left.category.localeCompare(right.category, "ko"));
    return {
      id: region.id,
      name: region.name,
      shortName: region.short_name || region.name,
      total: regionEntries.length,
      categoryTotals,
      entries: regionEntries,
      featured: regionEntries.slice(0, 3),
    };
  });
  const maximum = scaleMaximum ?? Math.max(...models.map((region) => region.total), 1);
  const step = Math.max(1, Math.ceil(maximum / DENSITY_LEVELS));
  for (const region of models) region.density = region.total === 0 ? 0 : Math.min(DENSITY_LEVELS, Math.ceil(region.total / step));
  const byId = new Map(models.map((region) => [region.id, region]));
  const total = models.reduce((sum, region) => sum + region.total, 0);
  if (total !== entries.length) throw new RangeError("Landscape regions must cover every entry exactly once.");
  const nationalCategories = new Map();
  for (const entry of entries) nationalCategories.set(entry.category, (nationalCategories.get(entry.category) ?? 0) + 1);
  const nationalCategoryTotals = [...nationalCategories].map(([category, count]) => ({ category, count }))
    .sort((left, right) => right.count - left.count || left.category.localeCompare(right.category, "ko"));
  const topRegions = [...models].sort((left, right) => right.total - left.total || left.name.localeCompare(right.name, "ko")).slice(0, 3);
  return { regions: models, byId, total, maximum, step, nationalCategoryTotals, topRegions };
}

function svgElement(name) {
  return document.createElementNS("http://www.w3.org/2000/svg", name);
}

function pathBounds(path) {
  // The v1 asset contains polygon M/L/Z paths. Computing bounds from its vertices
  // also works when a direct link initially hides the map on a compact screen.
  if (/[^MLZ\d.,\s-]/i.test(path)) throw new TypeError("Unsupported map polygon path.");
  const values = path.match(/-?\d+(?:\.\d+)?/g).map(Number);
  const xs = values.filter((_, i) => i % 2 === 0);
  const ys = values.filter((_, i) => i % 2 === 1);
  return { left: Math.min(...xs), right: Math.max(...xs), top: Math.min(...ys), bottom: Math.max(...ys) };
}

export function renderNationalMap(svg, asset, model, { onSelect, onPreview } = {}) {
  if (!asset || asset.schema_version !== 1 || !Array.isArray(asset.regions) || asset.regions.length !== model.regions.length) {
    throw new TypeError("National map asset must cover every landscape region.");
  }
  svg.setAttribute("viewBox", asset.view_box);
  const group = svgElement("g");
  group.classList.add("national-map-regions");
  for (const shape of asset.regions) {
    const region = model.byId.get(shape.id);
    if (!region || typeof shape.path !== "string" || shape.path.length === 0) throw new TypeError(`Invalid national map region: ${shape.id}`);
    const path = svgElement("path");
    path.setAttribute("d", shape.path);
    path.setAttribute("class", "national-region");
    path.setAttribute("tabindex", "0");
    path.setAttribute("role", "button");
    path.setAttribute("aria-label", `${region.name}, 공개자료 확인 사례 ${region.total}건`);
    path.dataset.region = region.id;
    path.dataset.density = String(region.density);
    path.addEventListener("pointerenter", () => onPreview?.(region.id));
    path.addEventListener("focus", () => onPreview?.(region.id));
    path.addEventListener("click", () => onSelect?.(region.id));
    path.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      onSelect?.(region.id);
    });
    group.append(path);
  }
  svg.replaceChildren(group);
  // Layout anchors for metro labels, not venue coordinates. Leader lines connect
  // the text to the existing administrative shape; all regions have button alternatives.
  const anchors = { seoul: [155, 230], incheon: [100, 300], sejong: [130, 365], daejeon: [160, 415], gwangju: [120, 535], daegu: [580, 435], ulsan: [630, 515], busan: [575, 590] };
  const bounds = new Map(asset.regions.map(shape => [shape.id, pathBounds(shape.path)]));
  const boxes = [...bounds.values()];
  const left = Math.min(...boxes.map(box => box.left)) - 35;
  const top = Math.min(...boxes.map(box => box.top)) - 35;
  svg.setAttribute("viewBox", `${left} ${top} ${Math.max(...boxes.map(box => box.right)) - left + 35} ${Math.max(...boxes.map(box => box.bottom)) - top + 35}`);
  const labels = svgElement("g");
  labels.setAttribute("aria-hidden", "true");
  labels.classList.add("map-labels");
  for (const path of group.children) {
    const region = model.byId.get(path.dataset.region);
    const box = bounds.get(region.id);
    const center = [(box.left + box.right) / 2, (box.top + box.bottom) / 2];
    const [x, y] = anchors[region.id] || (region.id === "gyeonggi" ? [center[0] + 35, center[1] + 35] : center);
    if (anchors[region.id]) {
      const line = svgElement("line");
      ["x1", "y1", "x2", "y2"].forEach((key, i) => line.setAttribute(key, [...center, x, y][i]));
      labels.append(line);
    }
    const label = svgElement("text");
    label.setAttribute("x", x);
    label.setAttribute("y", y);
    label.dataset.regionLabel = region.id;
    label.textContent = `${region.shortName} ${region.total}`;
    const target = svgElement("g");
    target.dataset.regionLabelTarget = region.id;
    target.classList.add("map-label-target");
    const hit = svgElement("rect");
    hit.setAttribute("x", x - 65);
    hit.setAttribute("y", y - 25);
    hit.setAttribute("width", 130);
    hit.setAttribute("height", 50);
    target.append(hit, label);
    target.addEventListener("click", () => onSelect?.(region.id));
    labels.append(target);
  }
  svg.append(labels);
}

export function updateNationalMap(svg, selectedRegion, model) {
  svg.querySelectorAll("[data-region]").forEach((path) => {
    const selected = path.dataset.region === selectedRegion;
    path.classList.toggle("is-selected", selected);
    path.setAttribute("aria-pressed", String(selected));
    const region = model?.byId.get(path.dataset.region);
    if (region) {
      path.dataset.density = String(region.density);
      path.setAttribute("aria-label", `${region.name}, 현재 조건의 공개자료 ${region.total}건`);
    }
  });
  if (model) svg.querySelectorAll("[data-region-label]").forEach(label => {
    const region = model.byId.get(label.dataset.regionLabel);
    label.textContent = `${region.shortName} ${region.total}`;
  });
}

export function renderMapLegend(container, model) {
  container.replaceChildren(...Array.from({ length: DENSITY_LEVELS + 1 }, (_, level) => {
    const item = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.dataset.density = String(level);
    swatch.setAttribute("aria-hidden", "true");
    item.append(swatch, level === 0 ? "0건" : `${(level - 1) * model.step + 1}–${level * model.step}건`);
    return item;
  }));
}

export function renderMapReadout(container, region) {
  container.replaceChildren();
  const eyebrow = document.createElement("span");
  eyebrow.textContent = region ? "지역 자료" : "전국 자료";
  const title = document.createElement("strong");
  title.textContent = region ? region.name : "지역을 선택해 공개자료 건수를 확인하세요";
  const note = document.createElement("p");
  note.textContent = region
    ? (region.total ? `${region.total}건 · ${region.categoryTotals.slice(0, 2).map(({ category, count }) => `${category} ${count}`).join(" · ")}` : "현재 조건에 맞는 공개자료 없음")
    : "지역을 누르면 해당 조건의 사례 목록을 볼 수 있습니다.";
  container.append(eyebrow, title, note);
}

export function renderRegionShortcuts(container, model, selectedRegion, onSelect) {
  if (container.children.length === model.regions.length) {
    for (const button of container.children) {
      const region = model.byId.get(button.dataset.regionShortcut);
      button.textContent = `${region.shortName} ${region.total}`;
      button.setAttribute("aria-pressed", String(region.id === selectedRegion));
    }
    return;
  }
  container.replaceChildren(...model.regions.map((region) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.regionShortcut = region.id;
    button.setAttribute("aria-pressed", String(region.id === selectedRegion));
    button.textContent = `${region.shortName} ${region.total}`;
    button.addEventListener("click", () => onSelect(region.id));
    return button;
  }));
}

function appendText(parent, tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

export function renderRegionLens(container, model, selectedRegion, { onCategory, onEntry, onRegion } = {}) {
  const region = selectedRegion ? model.byId.get(selectedRegion) : null;
  container.replaceChildren();
  const intro = document.createElement("div");
  intro.className = "region-lens-copy";
  appendText(intro, "p", "section-number", region ? `REGION / ${region.shortName}` : "NATIONAL / 17 REGIONS");
  appendText(intro, "h2", "", region ? `${region.name} 공개자료 ${region.total}건` : "17개 시·도 공개자료 현황");
  appendText(intro, "p", "region-lens-lede", region
    ? "활동 유형별 건수와 최근 사례를 표시합니다."
    : "시·도를 선택하면 해당 지역의 활동 유형별 건수와 최근 사례를 표시합니다.");
  container.append(intro);

  const categories = document.createElement("div");
  categories.className = "region-category-grid";
  const categorySource = region ? region.categoryTotals : model.nationalCategoryTotals;
  for (const [index, item] of categorySource.entries()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "region-category";
    button.dataset.category = item.category;
    appendText(button, "span", "region-category-index", String(index + 1).padStart(2, "0"));
    appendText(button, "strong", "", String(item.count));
    appendText(button, "span", "", item.category);
    button.addEventListener("click", () => onCategory?.(region?.id ?? null, item.category));
    categories.append(button);
  }
  container.append(categories);

  const cards = document.createElement("div");
  cards.className = "region-featured-grid";
  if (!region) {
    for (const topRegion of model.topRegions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "region-featured-card region-ranking-card";
      button.dataset.regionId = topRegion.id;
      appendText(button, "span", "region-featured-meta", "PUBLIC RECORD COUNT");
      appendText(button, "strong", "", topRegion.name);
      appendText(button, "span", "region-ranking-count", `${topRegion.total}건`);
      appendText(button, "span", "region-featured-link", "지역 사례 보기 →");
      button.addEventListener("click", () => onRegion?.(topRegion.id));
      cards.append(button);
    }
    container.append(cards);
    return;
  }
  for (const entry of region.featured) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "region-featured-card";
    button.dataset.entryId = entry.id;
    appendText(button, "span", "region-featured-meta", `${entry.year || "연도 미기록"} · ${entry.category}`);
    appendText(button, "strong", "", entry.name);
    appendText(button, "span", "region-featured-link", "근거와 상세 보기 →");
    button.addEventListener("click", () => onEntry?.(entry.id));
    cards.append(button);
  }
  container.append(cards);
}
