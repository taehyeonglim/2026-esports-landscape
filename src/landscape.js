const DENSITY_LEVELS = 5;

function requireArray(value, label) {
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  return value;
}

function recentFirst(left, right) {
  return String(right.year || "").localeCompare(String(left.year || ""), "ko") || left.name.localeCompare(right.name, "ko");
}

export function landscapeModel(entries, regions) {
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
  const maximum = Math.max(...models.map((region) => region.total), 1);
  for (const region of models) region.density = Math.max(1, Math.ceil((region.total / maximum) * DENSITY_LEVELS));
  const byId = new Map(models.map((region) => [region.id, region]));
  const total = models.reduce((sum, region) => sum + region.total, 0);
  if (total !== entries.length) throw new RangeError("Landscape regions must cover every entry exactly once.");
  const nationalCategories = new Map();
  for (const entry of entries) nationalCategories.set(entry.category, (nationalCategories.get(entry.category) ?? 0) + 1);
  const nationalCategoryTotals = [...nationalCategories].map(([category, count]) => ({ category, count }))
    .sort((left, right) => right.count - left.count || left.category.localeCompare(right.category, "ko"));
  const topRegions = [...models].sort((left, right) => right.total - left.total || left.name.localeCompare(right.name, "ko")).slice(0, 3);
  return { regions: models, byId, total, maximum, nationalCategoryTotals, topRegions };
}

function svgElement(name) {
  return document.createElementNS("http://www.w3.org/2000/svg", name);
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
}

export function updateNationalMap(svg, selectedRegion) {
  svg.querySelectorAll("[data-region]").forEach((path) => {
    const selected = path.dataset.region === selectedRegion;
    path.classList.toggle("is-selected", selected);
    path.setAttribute("aria-pressed", String(selected));
  });
}

export function renderMapReadout(container, region) {
  container.replaceChildren();
  const eyebrow = document.createElement("span");
  eyebrow.textContent = region ? "SELECTED REGION" : "EXPLORE 17 REGIONS";
  const title = document.createElement("strong");
  title.textContent = region ? region.name : "지역을 선택해 공개자료 건수를 확인하세요";
  const note = document.createElement("p");
  note.textContent = region
    ? `${region.total}건 · ${region.categoryTotals.slice(0, 2).map(({ category, count }) => `${category} ${count}`).join(" · ")}`
    : "색이 밝을수록 공개자료에서 확인된 사례가 많습니다. 실제 활동 규모나 순위는 아닙니다.";
  container.append(eyebrow, title, note);
}

export function renderRegionShortcuts(container, model, selectedRegion, onSelect) {
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
