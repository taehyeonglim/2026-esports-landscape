const dataUrl = new URL("../data/site.v3.json", import.meta.url);

const EXPECTED_SCHEMA_VERSION = 3;
const MINIMUM_ENTRY_COUNT = 230;
const EXPECTED_REGION_COUNT = 17;
const RENDER_TARGETS = [
  "#dataset-facts",
  "#typology-axes",
  "#coverage-by-category",
  "#negative-evidence",
  "#data-gaps",
  "#site-notes",
  "#coordinate-source",
  "#boundary-license",
];

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = String(text);
  return node;
}

function appendText(parent, tag, text, className) {
  const node = element(tag, text, className);
  parent.append(node);
  return node;
}

function displayNote(note) {
  return typeof note === "string" ? note : note?.note ?? "";
}

function regionName(regions, id) {
  return regions.find((region) => region.id === id)?.short_name ?? "미기록";
}

function renderFacts(data, target) {
  const statusCounts = Object.fromEntries([...OPERATIONAL_STATUS_VALUES].map((status) => [status, data.entries.filter((entry) => entry.operational_status === status).length]));
  const resourceCounts = Object.fromEntries([...RESOURCE_TYPE_VALUES].map((type) => [type, data.entries.filter((entry) => entry.resource_type === type).length]));
  const values = [
    ["스키마", `v${data.schema_version}`],
    ["등록 항목", `${data.meta.entry_count}건`],
    ["대상 지역", `${data.meta.region_count}개 시·도`],
    ["원문 참조", `${data.sources.length}개 source ref`],
    ["자료 반영일", data.meta.data_updated_at],
    ["상태 기준일", data.meta.validation_as_of ?? "승인된 기준일 없음"],
    ["상태 분포", `확인 필요 ${statusCounts.needs_review}건 · 운영 중 ${statusCounts.current}건 · 종료 ${statusCounts.ended}건`],
    ["자원 유형", `학교 ${resourceCounts.school}건 · 대회 ${resourceCounts.event}건 · 시설 ${resourceCounts.facility}건 · 기타 ${resourceCounts.other}건`],
  ];
  for (const [label, value] of values) {
    const item = element("div");
    appendText(item, "dt", label);
    appendText(item, "dd", value);
    target.append(item);
  }
}

function renderTypology(axes, target) {
  for (const axis of axes ?? []) {
    const item = element("li", null, "axis");
    appendText(item, "h3", axis.axis);
    const pills = element("div", null, "pills");
    for (const value of axis.values ?? []) appendText(pills, "span", value, "pill");
    item.append(pills);
    appendText(item, "p", axis.rationale);
    target.append(item);
  }
}

function renderCoverage(coverage, target) {
  const highest = Math.max(1, ...(coverage ?? []).map((item) => Number(item.count) || 0));
  for (const item of coverage ?? []) {
    const row = element("li", null, "bar-row");
    appendText(row, "span", item.category, "bar-label");
    appendText(row, "span", `${item.count}건`, "bar-value");
    const track = element("div", null, "bar-track");
    const fill = element("div", null, "bar-fill");
    fill.style.width = `${Math.max(0, Math.min(100, (Number(item.count) / highest) * 100))}%`;
    track.append(fill);
    row.append(track);
    target.append(row);
  }
}

function renderRecords(records, regions, kind, target) {
  for (const record of records ?? []) {
    const item = element("li");
    const article = element("article", null, "record");
    const title = kind === "gap" ? record.gap : record.finding;
    appendText(article, "h3", `${regionName(regions, record.region_id)} · ${record.school_level ?? "미기록"}`);
    appendText(article, "p", title);
    if (kind === "gap") appendText(article, "p", `다음 확인: ${record.next_check ?? "미기록"}`);
    else appendText(article, "p", `검색 범위: ${record.query ?? "미기록"}`);
    appendText(article, "small", `접근일 ${record.date_accessed ?? "미기록"} · 신뢰도 ${record.confidence ?? "미기록"}`);
    item.append(article);
    target.append(item);
  }
}

function renderNotes(notes, target) {
  for (const note of notes ?? []) {
    const text = displayNote(note);
    if (!text) continue;
    const item = element("li");
    const article = element("article", null, "note-item");
    appendText(article, "p", text);
    if (typeof note === "object" && note.date_accessed) appendText(article, "small", `접근일 ${note.date_accessed}`);
    item.append(article);
    target.append(item);
  }
}

function renderSpatialMetadata(data, coordinate, license) {
  coordinate.textContent = data.meta.coord_source;
  const licenses = [...new Set(data.regions.map((region) => region.boundary_license).filter(Boolean))];
  const sources = [...new Set(data.regions.map((region) => region.boundary_source).filter(Boolean))];
  license.textContent = [sources.join("; "), licenses.join("; ")].filter(Boolean).join(" · ");
}

function requireInvariant(condition, message) {
  if (!condition) throw new TypeError(`Invalid research data: ${message}`);
}

function requireString(value, message) {
  requireInvariant(typeof value === "string" && value.trim() !== "", message);
}

function requireStringArray(value, message, { allowEmpty = false } = {}) {
  requireInvariant(
    Array.isArray(value)
      && (allowEmpty || value.length > 0)
      && value.every((item) => typeof item === "string" && item.trim() !== ""),
    message,
  );
}

const CONFIDENCE_VALUES = new Set(["high", "medium", "low"]);
const OPERATIONAL_STATUS_VALUES = new Set(["current", "ended", "needs_review"]);
const RESOURCE_TYPE_VALUES = new Set(["school", "event", "facility", "other"]);
const SOURCE_VERIFICATION_VALUES = new Set(["needs_review", "verified", "rejected"]);


export function validateResearchData(data) {
  requireInvariant(data && typeof data === "object" && !Array.isArray(data), "payload");
  requireInvariant(data.schema_version === EXPECTED_SCHEMA_VERSION, "schema_version");
  requireInvariant(Array.isArray(data.entries) && data.entries.length >= MINIMUM_ENTRY_COUNT, "entries");
  requireInvariant(Array.isArray(data.regions) && data.regions.length === EXPECTED_REGION_COUNT, "regions");
  requireInvariant(data.meta?.entry_count === data.entries?.length && data.meta.entry_count >= MINIMUM_ENTRY_COUNT && data.meta?.region_count === EXPECTED_REGION_COUNT, "meta counts");
  requireInvariant(
    Array.isArray(data.sources)
      && Array.isArray(data.coverage_by_category)
      && Array.isArray(data.typology_axes)
      && Array.isArray(data.negative_evidence)
      && Array.isArray(data.data_gaps)
      && Array.isArray(data.site_notes),
    "research collections",
  );

  const regionIds = new Set(data.regions.map((region) => region?.id));
  const sourceIds = new Set(data.sources.map((source) => source?.id));
  const entryIds = new Set();
  const sourceById = new Map(data.sources.map((source) => [source?.id, source]));
  const categoryCounts = new Map();
  for (const entry of data.entries) {
    requireString(entry?.id, "unique entry id");
    requireInvariant(!entryIds.has(entry.id), "unique entry id");
    entryIds.add(entry.id);
    requireInvariant(typeof entry.region_id === "string" && regionIds.has(entry.region_id), `region reference for ${entry.id}`);
    requireInvariant(RESOURCE_TYPE_VALUES.has(entry.resource_type), `resource_type for ${entry.id}`);
    requireStringArray(entry.source_ids, `source reference for ${entry.id}`);
    requireInvariant(new Set(entry.source_ids).size === entry.source_ids.length, `unique source reference for ${entry.id}`);
    for (const sourceId of entry.source_ids) {
      const source = sourceById.get(sourceId);
      requireInvariant(source && source.entry_id === entry.id, `source ownership for ${entry.id}`);
    }
    requireInvariant(OPERATIONAL_STATUS_VALUES.has(entry.operational_status), `operational_status for ${entry.id}`);
    requireInvariant(Object.hasOwn(entry, "confidence") && (entry.confidence === null || CONFIDENCE_VALUES.has(entry.confidence)), `confidence for ${entry.id}`);
    requireString(entry.public_note, `public_note for ${entry.id}`);
    requireString(entry.review.reason, `status review reason for ${entry.id}`);
    if (entry.operational_status === "needs_review") {
      requireInvariant(entry.status_checked_at === null && entry.status_provenance === null, `unverified status metadata for ${entry.id}`);
    } else {
      requireInvariant(typeof data.meta.validation_as_of === "string" && /^\d{4}-\d{2}-\d{2}$/.test(data.meta.validation_as_of), `validation_as_of for ${entry.id}`);
      requireInvariant(typeof entry.status_checked_at === "string" && /^\d{4}-\d{2}-\d{2}$/.test(entry.status_checked_at), `status_checked_at for ${entry.id}`);
      requireString(entry.status_provenance, `status_provenance for ${entry.id}`);
    }
    requireInvariant(entry.off_map === !(entry.scope === "regional" && Number.isFinite(entry.lat) && Number.isFinite(entry.lng)), `map eligibility for ${entry.id}`);
    categoryCounts.set(entry.category, (categoryCounts.get(entry.category) ?? 0) + 1);
  }
  requireInvariant(regionIds.size === EXPECTED_REGION_COUNT && [...regionIds].every((id) => typeof id === "string" && id), "unique region id");
  for (const source of data.sources) {
    requireString(source?.id, "source id");
    requireString(source?.entry_id, `source owner for ${source?.id}`);
    requireString(source.raw, `source raw evidence for ${source.id}`);
    requireInvariant(Array.isArray(source.urls) && new Set(source.urls).size === source.urls.length && source.urls.every((url) => typeof url === "string" && /^https?:\/\//.test(url)), `source URLs for ${source.id}`);
    requireInvariant(source.kind === "raw_source", `source kind for ${source.id}`);
    requireInvariant(SOURCE_VERIFICATION_VALUES.has(source.verification_status), `source verification for ${source.id}`);
    requireInvariant(entryIds.has(source.entry_id), `source owner for ${source.id}`);
    const owner = data.entries.find((entry) => entry.id === source.entry_id);
    requireInvariant(owner.source_ids.includes(source.id), `source reverse ownership for ${source.id}`);
  }
  requireInvariant(sourceIds.size === data.sources.length, "unique source id and entry reference");
  const coverageCategories = new Set();
  for (const item of data.coverage_by_category) {
    requireInvariant(typeof item?.category === "string" && !coverageCategories.has(item.category), "unique coverage category");
    coverageCategories.add(item.category);
    requireInvariant(Number.isInteger(item.count) && item.count >= 0 && categoryCounts.get(item.category) === item.count, `coverage count for ${item.category}`);
  }
  requireInvariant(coverageCategories.size === categoryCounts.size && [...categoryCounts.keys()].every((category) => coverageCategories.has(category)), "coverage categories");
  for (const axis of data.typology_axes) {
    requireString(axis?.axis, "typology axis");
    requireStringArray(axis?.values, `typology values for ${axis?.axis}`);
    requireString(axis?.rationale, `typology rationale for ${axis?.axis}`);
  }
  for (const record of data.negative_evidence) {
    requireString(record?.id, "negative evidence id");
    requireInvariant(regionIds.has(record.region_id), `negative evidence region for ${record?.id}`);
    for (const key of ["school_level", "query", "source", "finding", "date_accessed"]) requireString(record?.[key], `negative evidence ${key} for ${record?.id}`);
    requireInvariant(CONFIDENCE_VALUES.has(record.confidence), `negative evidence confidence for ${record?.id}`);
  }
  for (const record of data.data_gaps) {
    requireString(record?.id, "data gap id");
    requireInvariant(regionIds.has(record.region_id), `data gap region for ${record?.id}`);
    for (const key of ["category", "school_level", "gap", "next_check", "date_accessed"]) requireString(record?.[key], `data gap ${key} for ${record?.id}`);
    requireStringArray(record.evidence_ids, `data gap evidence for ${record?.id}`, { allowEmpty: true });
  }
  for (const note of data.site_notes) {
    if (typeof note === "string") requireString(note, "site note");
    else {
      requireString(note?.id, "site note id");
      requireString(note?.note, `site note text for ${note?.id}`);
    }
  }
  requireString(data.meta?.coord_source, "coordinate source");
  for (const region of data.regions) {
    requireString(region.short_name, `short region name for ${region.id}`);
    requireString(region.boundary_source, `boundary source for ${region.id}`);
    requireString(region.boundary_license, `boundary license for ${region.id}`);
  }
  return data;
}

export async function loadResearch(fetchImpl = globalThis.fetch) {
  if (typeof fetchImpl !== "function") throw new TypeError("fetchImpl is required");
  const response = await fetchImpl(dataUrl.href, { headers: { Accept: "application/json" } });
  if (!response?.ok) throw new Error(`Research data request failed (${response?.status ?? "network"})`);
  return validateResearchData(await response.json());
}

function renderTargets() {
  return Object.fromEntries(RENDER_TARGETS.map((selector) => {
    const target = document.querySelector(selector);
    if (!target) throw new Error(`Missing research render target: ${selector}`);
    return [selector, target];
  }));
}

export function renderResearch(data) {
  validateResearchData(data);
  const targets = renderTargets();
  const fragments = Object.fromEntries(RENDER_TARGETS.map((selector) => [selector, document.createDocumentFragment()]));
  renderFacts(data, fragments["#dataset-facts"]);
  renderTypology(data.typology_axes, fragments["#typology-axes"]);
  renderCoverage(data.coverage_by_category, fragments["#coverage-by-category"]);
  renderRecords(data.negative_evidence, data.regions, "negative", fragments["#negative-evidence"]);
  renderRecords(data.data_gaps, data.regions, "gap", fragments["#data-gaps"]);
  renderNotes(data.site_notes, fragments["#site-notes"]);
  renderSpatialMetadata(data, fragments["#coordinate-source"], fragments["#boundary-license"]);
  for (const selector of RENDER_TARGETS) targets[selector].replaceChildren(fragments[selector]);
}

function showFailure() {
  for (const selector of RENDER_TARGETS) document.querySelector(selector)?.replaceChildren();
  const alert = document.querySelector("#research-load-error");
  if (alert) alert.hidden = false;
}

async function boot() {
  try {
    renderResearch(await loadResearch());
    const alert = document.querySelector("#research-load-error");
    if (alert) alert.hidden = true;
  } catch (error) {
    console.error("Research data loading or rendering failed:", error);
    showFailure();
  }
}

if (typeof document !== "undefined") void boot();
