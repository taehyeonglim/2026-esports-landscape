import { actions, appReducer, createAppState } from "./state.js";
import { decodeUrl, encodeUrl } from "./url-codec.js";
import { filterEntries } from "./search.js";
import { RegionLoader } from "./region-loader.js";
import { projectGeoJson } from "./projection.js";
import { CONFIDENCE_LABELS, OPERATIONAL_STATUS_LABELS, SCOPE_LABELS, SORT_LABELS, SOURCE_LABELS, TYPE_LABELS, renderCards } from "./cards.js";
import { renderDetail } from "./detail.js";
import { renderStatRibbon } from "./stat-ribbon.js";
import { matrixModel, renderMatrix } from "./matrix.js";
import { editorialModel, renderEditorial } from "./editorial.js";
import { landscapeModel, renderMapReadout, renderNationalMap, renderRegionLens, renderRegionShortcuts, updateNationalMap } from "./landscape.js";

const baseUrl = new URL("./", document.baseURI).href;
const byId = (id) => document.getElementById(id);
const elements = Object.freeze({
  region: byId("region-select"), search: byId("entry-search"),
  schoolLevel: byId("school-level-filter"), status: byId("status-filter"), scope: byId("scope-filter"), sort: byId("sort-filter"), reset: byId("reset-filters"),
  cards: byId("result-list"), count: byId("result-count"), detail: byId("detail-panel"), detailContent: byId("detail-content"),
  matrix: byId("compare-matrix"), typeFilter: byId("type-filter"), categoryActions: document.querySelector(".category-actions"),
  back: byId("detail-back"), map: byId("region-map"), mapGeometry: byId("region-map-geometry"), mapStatus: byId("map-status"), live: byId("live-status"),
  statRibbon: byId("stat-ribbon"),
  editorialInsights: byId("editorial-insights"), featuredStories: byId("featured-stories"),
  storyPaths: byId("paths"),
  nationalMap: byId("national-map"), mapReadout: byId("map-readout"), regionShortcuts: byId("region-shortcuts"), regionLens: byId("region-lens"),
  loadMore: byId("load-more"),
});
const PAGE_SIZE = 12;
let state = createAppState();
let data;
let entries = [];
let landscape;
let entryById = new Map();
let sourcesByEntry = new Map();
const loader = new RegionLoader({ baseUrl, origin: location.origin });
let mapRequestId = 0;
let mapLoadTimer = null;
let mapWorker = null;
let searchTimer = null;
let visibleCount = PAGE_SIZE;


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
  elements.live.textContent = message.textContent;
  console.error("Public data startup error:", error);
}

function optionValues(key) {
  const aliases = { category: "category", schoolLevel: "school_level", scope: "scope", status: "operational_status" };
  return [...new Set(entries.map((entry) => entry[aliases[key]]).filter(Boolean).map(String))].sort((a, b) => a.localeCompare(b, "ko"));
}

function allowed() {
  return {
    region: data.regions.map((region) => region.id), type: ["school", "event", "facility", "other"],
    category: optionValues("category"), schoolLevel: optionValues("schoolLevel"), scope: Object.keys(SCOPE_LABELS), status: optionValues("status"),
    sort: Object.keys(SORT_LABELS),
    entry: entries.map((entry) => entry.id),
  };
}

function updateUrl(mode = "push") {
  const query = encodeUrl(state, { allowed: allowed(), entries });
  const url = `${location.pathname}${query}${location.hash}`;
  if (mode === "replace") history.replaceState(null, "", url); else history.pushState(null, "", url);
}

function dispatch(action, historyMode = "push") {
  if (!['SET_ENTRY', 'SET_MAP_LOAD_STATE'].includes(action.type)) visibleCount = PAGE_SIZE;
  state = appReducer(state, action);
  updateUrl(historyMode);
  render();
  if (action.type === "SET_REGION") scheduleMap(state.region);
}

function populateSelect(select, values) {
  select.append(...values.map(({ value, label }) => {
    const option = document.createElement("option"); option.value = value; option.textContent = label; return option;
  }));
}

function renderMapPath(path) {
  if (typeof path !== "string" || path.trim() === "") throw new Error("표시할 경계가 없습니다.");
  elements.mapGeometry.replaceChildren();
  const svgPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
  svgPath.setAttribute("d", path); svgPath.setAttribute("class", "boundary");
  elements.mapGeometry.append(svgPath);
}

function cancelMapWork() {
  clearTimeout(mapLoadTimer);
  mapLoadTimer = null;
  loader.abort();
  mapWorker?.terminate();
  mapWorker = null;
}

function loadMapInWorker(regionId, requestId) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./map-worker.js", import.meta.url), { type: "module" });
    mapWorker = worker;
    const finish = () => {
      if (mapWorker === worker) mapWorker = null;
      worker.terminate();
    };
    worker.addEventListener("message", ({ data }) => {
      finish();
      if (data?.requestId !== requestId) {
        reject(new Error("지도 작업자가 다른 요청의 응답을 반환했습니다."));
        return;
      }
      if (!data?.ok) {
        reject(new Error(typeof data?.error === "string" ? data.error : "지도 작업자가 잘못된 응답을 반환했습니다."));
        return;
      }
      resolve(data.path);
    }, { once: true });
    worker.addEventListener("error", (event) => {
      finish();
      reject(event.error || new Error(event.message || "지도 작업자를 시작하지 못했습니다."));
    }, { once: true });
    try {
      worker.postMessage({ baseUrl, origin: location.origin, regionId, requestId });
    } catch (error) {
      finish();
      reject(error);
    }
  });
}

function scheduleMap(regionId) {
  const requestId = ++mapRequestId;
  cancelMapWork();
  elements.mapGeometry.replaceChildren();
  if (!regionId) {
    elements.mapStatus.textContent = "지역을 선택하면 경계를 불러옵니다.";
    return;
  }
  elements.mapStatus.textContent = "지역 경계를 불러오는 중입니다.";
  mapLoadTimer = setTimeout(() => loadMap(regionId, requestId), 150);
}

async function loadMap(regionId, requestId = ++mapRequestId) {
  try {
    if (typeof Worker === "function") {
      const path = await loadMapInWorker(regionId, requestId);
      if (requestId !== mapRequestId || state.region !== regionId) return;
      renderMapPath(path);
    } else {
      const geojson = await loader.load(regionId);
      if (requestId !== mapRequestId || state.region !== regionId) return;
      if (geojson == null) throw new Error("현재 요청의 지도 응답이 비어 있습니다.");
      renderMapPath(projectGeoJson(geojson).path);
    }
    elements.mapStatus.textContent = "지역 경계를 표시했습니다.";
  } catch (error) {
    if (requestId === mapRequestId && state.region === regionId) {
      console.error(`Map request or rendering failed for ${regionId}:`, error);
      elements.mapStatus.textContent = "지도를 불러오지 못했습니다. 카드 탐색은 계속 사용할 수 있습니다.";
    }
  }
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
  elements.count.textContent = `${filtered.length}개 중 ${limit}개 표시`;
  elements.live.textContent = `검색 결과 ${filtered.length}개 중 ${limit}개 표시`;
  elements.loadMore.hidden = limit >= filtered.length;
  if (!elements.loadMore.hidden) elements.loadMore.textContent = `사례 ${Math.min(PAGE_SIZE, filtered.length - limit)}개 더 보기`;
  const entry = entryById.get(state.entry);
  elements.detail.hidden = !entry;
  if (entry) renderDetail(elements.detailContent, entry, sourcesByEntry.get(entry.id) || []);
  if (landscape) {
    updateNationalMap(elements.nationalMap, state.region);
    renderMapReadout(elements.mapReadout, state.region ? landscape.byId.get(state.region) : null);
    renderRegionShortcuts(elements.regionShortcuts, landscape, state.region, selectLandscapeRegion);
    renderRegionLens(elements.regionLens, landscape, state.region, {
      onCategory: (regionId, category) => moveToResults({ regionId, category }),
      onEntry: openFeaturedEntry,
      onRegion: selectLandscapeRegion,
    });
  }
}

function openEntry(id) {
  if (state.entry !== id) dispatch(actions.setEntry(id));
  byId("detail-heading")?.focus();
}

function moveToResults({ regionId = null, category = null } = {}) {
  dispatch(actions.hydrate({ region: regionId, category: category ? [category] : [] }));
  scheduleMap(state.region);
  const heading = byId("results-heading");
  // Matrix controls can be activated again immediately. An in-flight smooth
  // scroll made the second activation unreliable in iOS WebKit.
  heading?.scrollIntoView({ behavior: "auto", block: "start" });
  heading?.focus({ preventScroll: true });
}

function selectLandscapeRegion(regionId) {
  dispatch(actions.hydrate({ region: regionId }));
  scheduleMap(state.region);
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  elements.regionLens?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}

function openFeaturedEntry(id) {
  dispatch(actions.hydrate({ entry: id }));
  const detail = elements.detail;
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  detail?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  byId("detail-heading")?.focus({ preventScroll: true });
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
  elements.loadMore.addEventListener("click", () => {
    visibleCount += PAGE_SIZE;
    render();
  });
  elements.cards.addEventListener("click", (event) => { const card = event.target.closest("[data-entry-id]"); if (card) openEntry(card.dataset.entryId); });
  elements.storyPaths?.addEventListener("click", (event) => {
    const path = event.target.closest("[data-story-category]");
    if (path) moveToResults({ category: path.dataset.storyCategory });
  });
  elements.featuredStories?.addEventListener("click", (event) => {
    const feature = event.target.closest("[data-feature-entry]");
    if (feature) openFeaturedEntry(feature.dataset.featureEntry);
  });
  elements.back.addEventListener("click", () => {
    const closingEntryId = state.entry;
    dispatch(actions.setEntry(null));
    const card = closingEntryId ? document.querySelector(`[data-entry-id="${CSS.escape(closingEntryId)}"]`) : null;
    (card || byId("results-heading"))?.focus();
  });
  addEventListener("popstate", () => {
    const previousEntry = state.entry;
    const previousRegion = state.region;
    clearTimeout(searchTimer);
    searchTimer = null;
    state = decodeUrl(location.search, { allowed: allowed(), entries });
    visibleCount = PAGE_SIZE;
    render();
    if (state.region !== previousRegion) scheduleMap(state.region);
    if (state.entry && state.entry !== previousEntry) {
      byId("detail-heading")?.focus();
    } else if (previousEntry && !state.entry) {
      const card = document.querySelector(`[data-entry-id="${CSS.escape(previousEntry)}"]`);
      (card || byId("results-heading"))?.focus();
    }
  });
}

async function start() {
  try {
    data = validatePublicData(await loadPublicData());
    const regionIndex = new Map(data.regions.map((region) => [region.id, region]));
    const sourceIndex = new Map(data.sources.map((source) => [source.id, source]));
    entries = data.entries.map((entry) => {
      const entrySources = entry.source_ids.map((id) => sourceIndex.get(id));
      return { ...entry, region_name: regionIndex.get(entry.region_id).name, source_kind: entrySources[0].kind, search_sources: entrySources };
    });
    entryById = new Map(entries.map((entry) => [entry.id, entry]));
    sourcesByEntry = new Map(entries.map((entry) => [entry.id, entry.source_ids.map((id) => sourceIndex.get(id))]));
    landscape = landscapeModel(entries, data.regions);
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
    } catch (error) {
      console.error("National landscape map unavailable:", error);
      elements.nationalMap.hidden = true;
      elements.nationalMap.closest(".hero-map")?.classList.add("map-unavailable");
      renderMapReadout(elements.mapReadout, null);
    }
    if (elements.statRibbon) renderStatRibbon(elements.statRibbon, data);
    if (elements.editorialInsights && elements.featuredStories) {
      renderEditorial(elements.editorialInsights, elements.featuredStories, editorialModel(data));
    }
    const model = matrixModel(data.entries, data.regions);
    elements.categoryActions.replaceChildren(...model.categories.map((category) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.dataset.categoryChip = category;
      chip.setAttribute("aria-pressed", "false");
      chip.textContent = category;
      return chip;
    }));
    renderMatrix(elements.matrix, model, moveToResults);
    populateSelect(elements.region, data.regions.map((region) => ({ value: region.id, label: region.name })));
    populateSelect(elements.schoolLevel, optionValues("schoolLevel").map((value) => ({ value, label: value })));
    populateSelect(elements.status, optionValues("status").map((value) => ({ value, label: OPERATIONAL_STATUS_LABELS[value] })));
    state = decodeUrl(location.search, { allowed: allowed(), entries });
    if (encodeUrl(state, { allowed: allowed(), entries }) !== location.search) updateUrl("replace");
    bindEvents(); render(); scheduleMap(state.region);
  } catch (error) {
    reportStartError(error);
  }
}

populateStaticSelects();
start();
