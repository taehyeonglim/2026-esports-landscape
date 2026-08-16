import { actions, appReducer, createAppState } from "./state.js";
import { decodeUrl, encodeUrl } from "./url-codec.js";
import { filterEntries } from "./search.js";
import { CONFIDENCE_LABELS, OPERATIONAL_STATUS_LABELS, SCOPE_LABELS, SORT_LABELS, SOURCE_LABELS, TYPE_LABELS, renderCards } from "./cards.js";
import { renderDetail } from "./detail.js";
import { renderStatRibbon } from "./stat-ribbon.js";
import { matrixModel, renderMatrix } from "./matrix.js";
import { editorialModel, renderEditorial } from "./editorial.js";
import { landscapeModel, renderMapReadout, renderNationalMap, renderRegionShortcuts, updateNationalMap } from "./landscape.js";

const baseUrl = new URL("./", document.baseURI).href;
const byId = (id) => document.getElementById(id);
const elements = Object.freeze({
  region: byId("region-select"),
  search: byId("entry-search"),
  typeFilter: byId("type-filter"),
  schoolLevel: byId("school-level-filter"),
  status: byId("status-filter"),
  scope: byId("scope-filter"),
  sort: byId("sort-filter"),
  reset: byId("reset-filters"),
  cards: byId("result-list"),
  count: byId("result-count"),
  visible: byId("result-visible"),
  loadMore: byId("load-more"),
  live: byId("live-status"),
  activeFilters: byId("active-filters"),
  categoryActions: document.querySelector(".category-actions"),
  detail: byId("detail-panel"),
  detailContent: byId("detail-content"),
  back: byId("detail-back"),
  mapContext: byId("map-context"),
  nationalMap: byId("national-map"),
  mapReadout: byId("map-readout"),
  regionShortcuts: byId("region-shortcuts"),
  browseTab: byId("browse-tab"),
  compareTab: byId("compare-tab"),
  browseView: byId("browse-view"),
  compareView: byId("compare-view"),
  tabs: document.querySelector(".workspace-tabs"),
  matrix: byId("compare-matrix"),
  filterPanel: byId("filter-panel"),
  filterTrigger: byId("mobile-filter-trigger"),
  filterCount: byId("mobile-filter-count"),
  filterClose: byId("filter-panel-close"),
  filterResult: byId("filter-panel-result"),
  advancedFilters: document.querySelector(".advanced-filters"),
  statRibbon: byId("stat-ribbon"),
  editorialInsights: byId("editorial-insights"),
  featuredStories: byId("featured-stories"),
  dataUpdatedAt: byId("data-updated-at"),
});

const PAGE_SIZE = 12;
const mobileQuery = matchMedia("(max-width: 767px)");
const compactQuery = matchMedia("(max-width: 1023px)");
let state = createAppState();
let data;
let entries = [];
let landscape;
let comparisonModel;
let matrixRendered = false;
let filterModalActive = false;
let detailModalActive = false;
let entryById = new Map();
let sourcesByEntry = new Map();
let searchTimer = null;
let visibleCount = PAGE_SIZE;
let lastEntryTriggerId = null;

function populateStaticSelects() {
  populateSelect(elements.typeFilter, Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label })));
  populateSelect(elements.scope, Object.entries(SCOPE_LABELS).map(([value, label]) => ({ value, label })));
  populateSelect(elements.sort, Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label })));
}

class DataRequestError extends Error {
  constructor(message, cause) { super(message, { cause }); this.name = "DataRequestError"; }
}

class DataJsonError extends Error {
  constructor(message, cause) { super(message, { cause }); this.name = "DataJsonError"; }
}

class DataIntegrityError extends Error {
  constructor(message) { super(message); this.name = "DataIntegrityError"; }
}

function requireRecord(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new DataIntegrityError(`${label} must be an object.`);
  return value;
}

function requireId(value, label) {
  if (typeof value !== "string" || value.trim() === "") throw new DataIntegrityError(`${label} must have a non-empty id.`);
  return value;
}

function uniqueIds(records, label) {
  const ids = new Set();
  records.forEach((record, index) => {
    const id = requireId(requireRecord(record, `${label}[${index}]`).id, `${label}[${index}]`);
    if (ids.has(id)) throw new DataIntegrityError(`${label} contains duplicate id "${id}".`);
    ids.add(id);
  });
  return ids;
}

function validatePublicData(payload) {
  const site = requireRecord(payload, "site.v3.json");
  if (site.schema_version !== 3) throw new DataIntegrityError("schema_version must be 3.");
  if (!Array.isArray(site.entries) || site.entries.length < 230 || site.meta?.entry_count !== site.entries.length) throw new DataIntegrityError("entries must match the published entry count and retain the 230-entry baseline.");
  if (typeof site.meta?.data_updated_at !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(site.meta.data_updated_at)) throw new DataIntegrityError("meta.data_updated_at must be a valid date.");
  if (!Array.isArray(site.regions) || site.regions.length !== 17) throw new DataIntegrityError("regions must contain exactly 17 records.");
  if (!Array.isArray(site.sources)) throw new DataIntegrityError("sources must be an array.");

  const regionIds = uniqueIds(site.regions, "regions");
  const entryIds = uniqueIds(site.entries, "entries");
  const sourceIds = uniqueIds(site.sources, "sources");
  const sourceById = new Map(site.sources.map((source) => [source.id, source]));
  site.regions.forEach((region, index) => {
    if (typeof region.name !== "string" || region.name.trim() === "") throw new DataIntegrityError(`regions[${index}] requires a public name.`);
  });

  site.entries.forEach((entry, index) => {
    requireRecord(entry, `entries[${index}]`);
    if (typeof entry.name !== "string" || entry.name.trim() === "") throw new DataIntegrityError(`entries[${index}] requires a public name.`);
    if (typeof entry.category !== "string" || entry.category.trim() === "") throw new DataIntegrityError(`entries[${index}] requires a public category.`);
    if (!TYPE_LABELS[entry.resource_type]) throw new DataIntegrityError(`entries[${index}] requires a supported resource_type.`);
    if (entry.confidence != null && !CONFIDENCE_LABELS[entry.confidence]) throw new DataIntegrityError(`entries[${index}] has an unsupported confidence.`);
    if (!regionIds.has(entry.region_id)) throw new DataIntegrityError(`entries[${index}] references an unknown region.`);
    if (!Array.isArray(entry.source_ids) || entry.source_ids.length === 0 || new Set(entry.source_ids).size !== entry.source_ids.length) {
      throw new DataIntegrityError(`entries[${index}] must reference unique sources.`);
    }
    entry.source_ids.forEach((sourceId) => {
      const source = sourceById.get(sourceId);
      if (!source || source.entry_id !== entry.id) throw new DataIntegrityError(`entries[${index}] has an invalid source owner.`);
    });
    if (typeof entry.operational_status !== "string" || !OPERATIONAL_STATUS_LABELS[entry.operational_status]) throw new DataIntegrityError(`entries[${index}] requires a supported operational_status.`);
    if (!SCOPE_LABELS[entry.scope]) throw new DataIntegrityError(`entries[${index}] requires a supported scope.`);
    if (typeof entry.public_note !== "string" || entry.public_note.trim() === "") throw new DataIntegrityError(`entries[${index}] requires a safe public_note.`);
    const reviewReason = entry.review?.reason;
    if (typeof reviewReason !== "string" || reviewReason.trim() === "") throw new DataIntegrityError(`entries[${index}] requires a status review reason.`);
    if (entry.operational_status === "needs_review") {
      if (entry.status_checked_at !== null || entry.status_provenance !== null) throw new DataIntegrityError(`entries[${index}] cannot claim verification metadata.`);
    } else if (
      typeof entry.status_checked_at !== "string"
      || !/^\d{4}-\d{2}-\d{2}$/.test(entry.status_checked_at)
      || typeof entry.status_provenance !== "string"
      || entry.status_provenance.trim() === ""
    ) {
      throw new DataIntegrityError(`entries[${index}] requires complete status verification.`);
    }
    if (entry.off_map !== !(entry.scope === "regional" && Number.isFinite(entry.lat) && Number.isFinite(entry.lng))) {
      throw new DataIntegrityError(`entries[${index}] has an unsafe map eligibility state.`);
    }
  });
  site.sources.forEach((source, index) => {
    requireRecord(source, `sources[${index}]`);
    if (!SOURCE_LABELS[source.kind]) throw new DataIntegrityError(`sources[${index}] requires a supported public kind.`);
    if (
      !Array.isArray(source.urls)
      || new Set(source.urls).size !== source.urls.length
      || source.urls.some((url) => typeof url !== "string" || !/^https?:\/\//.test(url))
    ) {
      throw new DataIntegrityError(`sources[${index}] requires unique HTTP(S) URLs.`);
    }
    if (!["needs_review", "verified", "rejected"].includes(source.verification_status)) throw new DataIntegrityError(`sources[${index}] requires a supported verification status.`);
    if (!entryIds.has(source.entry_id)) throw new DataIntegrityError(`sources[${index}] references an unknown entry.`);
    if (!site.entries.find((entry) => entry.id === source.entry_id).source_ids.includes(source.id)) throw new DataIntegrityError(`sources[${index}] is not linked by its entry.`);
  });
  if (sourceIds.size !== site.sources.length) throw new DataIntegrityError("sources must have unique ids.");
  return site;
}

function renderDataUpdatedAt(value) {
  const [year, month, day] = value.split("-");
  elements.dataUpdatedAt.textContent = `자료 반영일 ${year}.${month}.${day}`;
  elements.dataUpdatedAt.dateTime = value;
}

async function loadPublicData() {
  let response;
  try {
    response = await fetch(new URL("data/site.v3.json", baseUrl), { headers: { Accept: "application/json" } });
  } catch (cause) {
    throw new DataRequestError("Data request failed.", cause);
  }
  if (!response.ok) throw new DataRequestError(`Data request failed (${response.status}).`);
  try {
    return await response.json();
  } catch (cause) {
    throw new DataJsonError("Data response was not valid JSON.", cause);
  }
}

async function loadNationalMap() {
  const response = await fetch(new URL("data/national-map.v1.json", baseUrl), { headers: { Accept: "application/json" } });
  if (!response.ok) throw new DataRequestError(`National map request failed (${response.status}).`);
  return response.json();
}

function reportStartError(error) {
  const messageByType = {
    DataRequestError: "데이터 요청에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    DataJsonError: "데이터 응답을 읽을 수 없습니다. 잠시 후 다시 시도해 주세요.",
    DataIntegrityError: "공개 데이터 무결성 검증에 실패했습니다. 표시를 중단했습니다.",
  };
  const message = document.createElement("p");
  message.className = "empty-state data-error";
  message.textContent = messageByType[error?.name] || "화면을 표시하는 중 오류가 발생했습니다.";
  elements.cards.replaceChildren(message);
  elements.count.textContent = "데이터를 표시할 수 없습니다.";
  elements.visible.textContent = "";
  elements.live.textContent = message.textContent;
  console.error("Public data startup error:", error);
}

function populateSelect(select, values) {
  select.append(...values.map(({ value, label }) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    return option;
  }));
}

function optionValues(key) {
  const aliases = { category: "category", schoolLevel: "school_level", scope: "scope", status: "operational_status" };
  return [...new Set(entries.map((entry) => entry[aliases[key]]).filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b, "ko"));
}

function allowed() {
  return {
    region: data.regions.map((region) => region.id),
    type: ["school", "event", "facility", "other"],
    category: optionValues("category"),
    schoolLevel: optionValues("schoolLevel"),
    scope: Object.keys(SCOPE_LABELS),
    status: optionValues("status"),
    sort: Object.keys(SORT_LABELS),
    entry: entries.map((entry) => entry.id),
  };
}

function updateUrl(mode = "push") {
  const query = encodeUrl(state, { allowed: allowed(), entries });
  const url = `${location.pathname}${query}${location.hash}`;
  if (mode === "replace") history.replaceState(null, "", url);
  else history.pushState(null, "", url);
}

function dispatch(action, historyMode = "push") {
  if (action.type !== "SET_ENTRY") visibleCount = PAGE_SIZE;
  state = appReducer(state, action);
  updateUrl(historyMode);
  render();
}

function sheetFilterCount() {
  return state.category.length
    + state.schoolLevel.length
    + state.status.length
    + state.scope.length
    + Number(Boolean(state.type))
    + Number(Boolean(state.sort));
}

function activeFilterDescriptors() {
  const descriptors = [];
  if (state.query) descriptors.push({ key: "query", label: `검색: ${state.query}` });
  if (state.region) descriptors.push({ key: "region", label: `지역: ${landscape?.byId.get(state.region)?.name || state.region}` });
  if (state.type) descriptors.push({ key: "type", label: `유형: ${TYPE_LABELS[state.type]}` });
  state.category.forEach((value) => descriptors.push({ key: "category", label: `카테고리: ${value}` }));
  state.schoolLevel.forEach((value) => descriptors.push({ key: "schoolLevel", label: `학교급: ${value}` }));
  state.status.forEach((value) => descriptors.push({ key: "status", label: `상태: ${OPERATIONAL_STATUS_LABELS[value]}` }));
  state.scope.forEach((value) => descriptors.push({ key: "scope", label: `범위: ${SCOPE_LABELS[value]}` }));
  if (state.sort) descriptors.push({ key: "sort", label: `정렬: ${SORT_LABELS[state.sort]}` });
  return descriptors;
}

function renderActiveFilters() {
  elements.activeFilters.replaceChildren(...activeFilterDescriptors().map(({ key, label }) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "active-filter";
    button.dataset.clearFilter = key;
    button.setAttribute("aria-label", `${label} 필터 제거`);
    button.textContent = label;
    return button;
  }));
}

function renderWorkspaceView() {
  const compare = state.view === "compare";
  elements.browseTab.setAttribute("aria-selected", String(!compare));
  elements.compareTab.setAttribute("aria-selected", String(compare));
  elements.browseTab.tabIndex = compare ? -1 : 0;
  elements.compareTab.tabIndex = compare ? 0 : -1;
  elements.browseView.hidden = compare;
  elements.compareView.hidden = !compare;
  if (compare && !matrixRendered) {
    renderMatrix(elements.matrix, comparisonModel, moveToResults);
    matrixRendered = true;
  }
}

function syncDetailSurface(entry) {
  if (!entry) {
    if (elements.detail.open) elements.detail.close();
    detailModalActive = false;
    elements.mapContext.hidden = false;
    return;
  }

  if (mobileQuery.matches) {
    elements.mapContext.hidden = false;
    if (!detailModalActive) {
      if (elements.detail.open) elements.detail.close();
      elements.detail.showModal();
      detailModalActive = true;
    }
    return;
  }

  if (detailModalActive && elements.detail.open) elements.detail.close();
  detailModalActive = false;
  if (!elements.detail.open) elements.detail.setAttribute("open", "");
  elements.mapContext.hidden = true;
}

function render() {
  const filtered = filterEntries(entries, state);
  elements.region.value = state.region || "";
  elements.search.value = state.query;
  elements.typeFilter.value = state.type || "";
  elements.schoolLevel.value = state.schoolLevel[0] || "";
  elements.status.value = state.status[0] || "";
  elements.scope.value = state.scope[0] || "";
  elements.sort.value = state.sort || "";
  elements.categoryActions.querySelectorAll("[data-category-chip]").forEach((chip) => {
    chip.setAttribute("aria-pressed", String(chip.dataset.categoryChip === (state.category[0] || "")));
  });

  const selectedIndex = state.entry ? filtered.findIndex((entry) => entry.id === state.entry) : -1;
  const limit = Math.min(filtered.length, Math.max(visibleCount, selectedIndex + 1));
  renderCards(elements.cards, filtered.slice(0, limit), state.entry);
  elements.count.textContent = `${filtered.length}건`;
  elements.visible.textContent = `${limit}개 표시`;
  elements.live.textContent = `검색 결과 ${filtered.length}건 중 ${limit}개 표시`;
  elements.loadMore.hidden = limit >= filtered.length;
  if (!elements.loadMore.hidden) elements.loadMore.textContent = `사례 ${Math.min(PAGE_SIZE, filtered.length - limit)}개 더 보기`;
  elements.filterCount.textContent = String(sheetFilterCount());
  elements.filterResult.textContent = `${filtered.length}건 결과 보기`;
  renderActiveFilters();
  renderWorkspaceView();

  const entry = entryById.get(state.entry);
  if (entry) renderDetail(elements.detailContent, entry, sourcesByEntry.get(entry.id) || []);
  syncDetailSurface(entry);

  if (landscape) {
    updateNationalMap(elements.nationalMap, state.region);
    renderMapReadout(elements.mapReadout, state.region ? landscape.byId.get(state.region) : null);
    renderRegionShortcuts(elements.regionShortcuts, landscape, state.region, selectLandscapeRegion);
  }
}

function resultsHeading({ scroll = true } = {}) {
  const heading = byId("results-heading");
  if (scroll) heading?.scrollIntoView({ behavior: "auto", block: "start" });
  heading?.focus({ preventScroll: true });
}

function openEntry(id) {
  lastEntryTriggerId = id;
  clearTimeout(searchTimer);
  searchTimer = null;
  const pendingQuery = elements.search.value;
  if (state.entry !== id || state.query !== pendingQuery) {
    dispatch(actions.hydrate({ ...state, view: "browse", query: pendingQuery, entry: id }));
  }
  requestAnimationFrame(() => byId("detail-heading")?.focus({ preventScroll: !mobileQuery.matches }));
}

function restoreEntryFocus(entryId) {
  requestAnimationFrame(() => requestAnimationFrame(() => {
    const card = entryId ? document.querySelector(`[data-entry-id="${CSS.escape(entryId)}"]`) : null;
    (card || byId("results-heading"))?.focus({ preventScroll: true });
  }));
}

function closeDetail() {
  const closingEntryId = state.entry || lastEntryTriggerId;
  dispatch(actions.setEntry(null), "replace");
  restoreEntryFocus(closingEntryId);
}

function moveToResults({ regionId = null, category = null } = {}) {
  closeFilterPanel({ restoreFocus: false });
  dispatch(actions.hydrate({ view: "browse", region: regionId, category: category ? [category] : [] }));
  resultsHeading();
}

function selectLandscapeRegion(regionId) {
  const nextState = state.view === "browse"
    ? appReducer(state, actions.setRegion(regionId))
    : createAppState({ ...state, view: "browse", region: regionId, entry: null });
  state = nextState;
  visibleCount = PAGE_SIZE;
  updateUrl();
  render();
  resultsHeading();
}

function openFeaturedEntry(id) {
  lastEntryTriggerId = id;
  dispatch(actions.hydrate({ ...state, view: "browse", entry: id }));
  byId("workspace")?.scrollIntoView({ behavior: "auto", block: "start" });
  requestAnimationFrame(() => byId("detail-heading")?.focus({ preventScroll: !mobileQuery.matches }));
}

function selectView(view) {
  if (state.view === view) return;
  dispatch(actions.setView(view));
  requestAnimationFrame(() => byId(`${view}-tab`)?.focus({ preventScroll: true }));
}

function openFilterPanel() {
  if (!mobileQuery.matches || filterModalActive) return;
  if (elements.filterPanel.open) elements.filterPanel.close();
  elements.advancedFilters.open = true;
  elements.filterPanel.showModal();
  filterModalActive = true;
  elements.filterTrigger.setAttribute("aria-expanded", "true");
  requestAnimationFrame(() => elements.filterClose.focus());
}

function closeFilterPanel({ restoreFocus = true } = {}) {
  if (!filterModalActive) return;
  elements.filterPanel.close();
  filterModalActive = false;
  elements.filterTrigger.setAttribute("aria-expanded", "false");
  if (restoreFocus) requestAnimationFrame(() => elements.filterTrigger.focus());
}

function syncResponsiveUi() {
  if (mobileQuery.matches) {
    if (elements.filterPanel.open && !filterModalActive) elements.filterPanel.close();
  } else {
    if (filterModalActive) closeFilterPanel({ restoreFocus: false });
    if (!elements.filterPanel.open) elements.filterPanel.setAttribute("open", "");
  }

  elements.mapContext.open = !compactQuery.matches;
  syncDetailSurface(entryById.get(state.entry));
}

function clearActiveFilter(key) {
  const actionsByKey = {
    query: () => actions.setQuery(""),
    region: () => actions.setRegion(null),
    type: () => actions.setType(null),
    category: () => actions.setFilter("category", []),
    schoolLevel: () => actions.setFilter("schoolLevel", []),
    status: () => actions.setFilter("status", []),
    scope: () => actions.setFilter("scope", []),
    sort: () => actions.setSort(null),
  };
  const action = actionsByKey[key]?.();
  if (action) dispatch(action, "replace");
}

function bindEvents() {
  elements.region.addEventListener("change", (event) => dispatch(actions.setRegion(event.target.value || null)));
  elements.search.addEventListener("input", (event) => {
    const query = event.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      searchTimer = null;
      dispatch(actions.setQuery(query), "replace");
    }, 150);
  });
  elements.typeFilter.addEventListener("change", (event) => dispatch(actions.setType(event.target.value || null), "replace"));
  elements.categoryActions.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-category-chip]");
    if (!chip) return;
    const value = chip.dataset.categoryChip;
    dispatch(actions.setFilter("category", state.category[0] === value ? [] : [value]));
  });
  elements.schoolLevel.addEventListener("change", (event) => dispatch(actions.setFilter("schoolLevel", event.target.value ? [event.target.value] : []), "replace"));
  elements.status.addEventListener("change", (event) => dispatch(actions.setFilter("status", event.target.value ? [event.target.value] : []), "replace"));
  elements.scope.addEventListener("change", (event) => dispatch(actions.setFilter("scope", event.target.value ? [event.target.value] : []), "replace"));
  elements.sort.addEventListener("change", (event) => dispatch(actions.setSort(event.target.value || null), "replace"));
  elements.reset.addEventListener("click", () => {
    clearTimeout(searchTimer);
    searchTimer = null;
    dispatch(actions.resetFilters(), "replace");
  });
  elements.activeFilters.addEventListener("click", (event) => {
    const button = event.target.closest("[data-clear-filter]");
    if (button) clearActiveFilter(button.dataset.clearFilter);
  });
  elements.loadMore.addEventListener("click", () => {
    visibleCount += PAGE_SIZE;
    render();
  });
  elements.cards.addEventListener("click", (event) => {
    const card = event.target.closest("[data-entry-id]");
    if (card) openEntry(card.dataset.entryId);
  });
  elements.featuredStories?.addEventListener("click", (event) => {
    const feature = event.target.closest("[data-feature-entry]");
    if (feature) openFeaturedEntry(feature.dataset.featureEntry);
  });
  elements.back.addEventListener("click", closeDetail);
  elements.detail.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeDetail();
  });
  elements.tabs.addEventListener("click", (event) => {
    const tab = event.target.closest("[role=tab]");
    if (tab) selectView(tab.dataset.view);
  });
  elements.tabs.addEventListener("keydown", (event) => {
    const order = ["browse", "compare"];
    const current = order.indexOf(state.view);
    let next = null;
    if (["ArrowRight", "ArrowDown"].includes(event.key)) next = order[(current + 1) % order.length];
    if (["ArrowLeft", "ArrowUp"].includes(event.key)) next = order[(current - 1 + order.length) % order.length];
    if (event.key === "Home") next = order[0];
    if (event.key === "End") next = order.at(-1);
    if (!next) return;
    event.preventDefault();
    selectView(next);
  });
  elements.filterTrigger.addEventListener("click", openFilterPanel);
  elements.filterClose.addEventListener("click", () => closeFilterPanel());
  elements.filterResult.addEventListener("click", () => closeFilterPanel());
  elements.filterPanel.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeFilterPanel();
  });
  elements.filterPanel.addEventListener("click", (event) => {
    if (event.target === elements.filterPanel && filterModalActive) closeFilterPanel();
  });
  mobileQuery.addEventListener("change", syncResponsiveUi);
  compactQuery.addEventListener("change", syncResponsiveUi);
  addEventListener("popstate", () => {
    const previousEntry = state.entry;
    clearTimeout(searchTimer);
    searchTimer = null;
    state = decodeUrl(location.search, { allowed: allowed(), entries });
    visibleCount = PAGE_SIZE;
    render();
    if (state.entry && state.entry !== previousEntry) {
      requestAnimationFrame(() => byId("detail-heading")?.focus());
    } else if (previousEntry && !state.entry) {
      restoreEntryFocus(previousEntry);
    }
  });
}

async function initializeNationalMap() {
  try {
    const nationalMapAsset = await loadNationalMap();
    renderNationalMap(elements.nationalMap, nationalMapAsset, landscape, {
      onSelect: selectLandscapeRegion,
      onPreview: (regionId) => renderMapReadout(elements.mapReadout, landscape.byId.get(regionId)),
    });
    elements.nationalMap.addEventListener("pointerleave", () => renderMapReadout(elements.mapReadout, state.region ? landscape.byId.get(state.region) : null));
    elements.nationalMap.addEventListener("focusout", (event) => {
      if (!elements.nationalMap.contains(event.relatedTarget)) renderMapReadout(elements.mapReadout, state.region ? landscape.byId.get(state.region) : null);
    });
    updateNationalMap(elements.nationalMap, state.region);
    renderMapReadout(elements.mapReadout, state.region ? landscape.byId.get(state.region) : null);
    renderRegionShortcuts(elements.regionShortcuts, landscape, state.region, selectLandscapeRegion);
  } catch (error) {
    console.error("National landscape map unavailable:", error);
    elements.nationalMap.hidden = true;
    elements.mapContext.classList.add("map-unavailable");
    renderMapReadout(elements.mapReadout, null);
  }
}

async function start() {
  try {
    data = validatePublicData(await loadPublicData());
    renderDataUpdatedAt(data.meta.data_updated_at);
    const regionIndex = new Map(data.regions.map((region) => [region.id, region]));
    const sourceIndex = new Map(data.sources.map((source) => [source.id, source]));
    entries = data.entries.map((entry) => {
      const entrySources = entry.source_ids.map((id) => sourceIndex.get(id));
      return { ...entry, region_name: regionIndex.get(entry.region_id).name, source_kind: entrySources[0].kind, search_sources: entrySources };
    });
    entryById = new Map(entries.map((entry) => [entry.id, entry]));
    sourcesByEntry = new Map(entries.map((entry) => [entry.id, entry.source_ids.map((id) => sourceIndex.get(id))]));
    landscape = landscapeModel(entries, data.regions);
    comparisonModel = matrixModel(data.entries, data.regions);

    renderStatRibbon(elements.statRibbon, data);
    renderEditorial(elements.editorialInsights, elements.featuredStories, editorialModel(data));
    elements.categoryActions.replaceChildren(...comparisonModel.categories.map((category) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.dataset.categoryChip = category;
      chip.setAttribute("aria-pressed", "false");
      chip.textContent = category;
      return chip;
    }));
    populateSelect(elements.region, data.regions.map((region) => ({ value: region.id, label: region.name })));
    populateSelect(elements.schoolLevel, optionValues("schoolLevel").map((value) => ({ value, label: value })));
    populateSelect(elements.status, optionValues("status").map((value) => ({ value, label: OPERATIONAL_STATUS_LABELS[value] })));

    state = decodeUrl(location.search, { allowed: allowed(), entries });
    if (encodeUrl(state, { allowed: allowed(), entries }) !== location.search) updateUrl("replace");
    bindEvents();
    syncResponsiveUi();
    render();
    void initializeNationalMap();
    if (state.entry) requestAnimationFrame(() => byId("detail-heading")?.focus());
  } catch (error) {
    reportStartError(error);
  }
}

populateStaticSelects();
start();
