import { actions, appReducer, createAppState } from "./state.js";
import { decodeUrl, encodeUrl } from "./url-codec.js";
import { filterEntries } from "./search.js";
import { RegionLoader } from "./region-loader.js";
import { projectGeoJson } from "./projection.js";
import { CONFIDENCE_LABELS, OPERATIONAL_STATUS_LABELS, SCOPE_LABELS, SORT_LABELS, SOURCE_LABELS, TYPE_LABELS, renderCards } from "./cards.js";
import { renderDetail } from "./detail.js";

const baseUrl = new URL("./", document.baseURI).href;
const byId = (id) => document.getElementById(id);
const elements = Object.freeze({
  region: byId("region-select"), search: byId("entry-search"), category: byId("category-filter"),
  schoolLevel: byId("school-level-filter"), status: byId("status-filter"), scope: byId("scope-filter"), sort: byId("sort-filter"), reset: byId("reset-filters"),
  cards: byId("result-list"), count: byId("result-count"), detail: byId("detail-panel"), detailContent: byId("detail-content"),
  back: byId("detail-back"), map: byId("region-map"), mapGeometry: byId("region-map-geometry"), mapStatus: byId("map-status"), live: byId("live-status"),
});
let state = createAppState();
let data;
let entries = [];
let entryById = new Map();
let sourcesByEntry = new Map();
const loader = new RegionLoader({ baseUrl, origin: location.origin });
let mapRequestId = 0;
let mapLoadTimer = null;
let mapWorker = null;
let searchTimer = null;


function populateStaticSelects() {
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
  if (!Array.isArray(site.entries) || site.entries.length !== 230) throw new DataIntegrityError("entries must contain exactly 230 records.");
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
  const readyToBrowse = Boolean(state.region && state.type);
  const filtered = readyToBrowse ? filterEntries(entries, state) : [];
  elements.region.value = state.region || "";
  elements.search.value = state.query;
  elements.category.value = state.category[0] || "";
  elements.schoolLevel.value = state.schoolLevel[0] || "";
  elements.status.value = state.status[0] || "";
  elements.scope.value = state.scope[0] || "";
  elements.sort.value = state.sort || "";
  document.querySelectorAll("[data-type]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.type === state.type)));
  if (readyToBrowse) {
    renderCards(elements.cards, filtered, state.entry);
    elements.count.textContent = `${filtered.length}개 항목`;
    elements.live.textContent = `검색 결과 ${filtered.length}개`;
  } else {
    elements.cards.replaceChildren();
    const prompt = document.createElement("p");
    prompt.className = "empty-state";
    prompt.textContent = "지역과 학교·대회·시설 유형을 선택하면 확인된 사례가 표시됩니다.";
    elements.cards.append(prompt);
    elements.count.textContent = "지역과 유형을 선택해 주세요";
    elements.live.textContent = "지역과 탐색 유형 선택이 필요합니다.";
  }
  const entry = entryById.get(state.entry);
  elements.detail.hidden = !entry;
  if (entry) renderDetail(elements.detailContent, entry, sourcesByEntry.get(entry.id) || []);
}

function openEntry(id) {
  if (state.entry !== id) dispatch(actions.setEntry(id));
  byId("detail-heading")?.focus();
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
  elements.category.addEventListener("change", (event) => dispatch(actions.setFilter("category", event.target.value ? [event.target.value] : []), "replace"));
  elements.schoolLevel.addEventListener("change", (event) => dispatch(actions.setFilter("schoolLevel", event.target.value ? [event.target.value] : []), "replace"));
  elements.status.addEventListener("change", (event) => dispatch(actions.setFilter("status", event.target.value ? [event.target.value] : []), "replace"));
  elements.scope.addEventListener("change", (event) => dispatch(actions.setFilter("scope", event.target.value ? [event.target.value] : []), "replace"));
  elements.sort.addEventListener("change", (event) => dispatch(actions.setSort(event.target.value || null), "replace"));
  elements.reset.addEventListener("click", () => {
    clearTimeout(searchTimer);
    searchTimer = null;
    dispatch(actions.resetFilters(), "replace");
  });
  document.querySelector(".type-actions").addEventListener("click", (event) => {
    const button = event.target.closest("[data-type]"); if (button) dispatch(actions.setType(state.type === button.dataset.type ? null : button.dataset.type));
  });
  elements.cards.addEventListener("click", (event) => { const card = event.target.closest("[data-entry-id]"); if (card) openEntry(card.dataset.entryId); });
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
    populateSelect(elements.region, data.regions.map((region) => ({ value: region.id, label: region.name })));
    populateSelect(elements.category, optionValues("category").map((value) => ({ value, label: value })));
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
