import { caseSite, isReferenceRecord } from "./record-scope.js";
const dataUrl = new URL("../data/site.v3.json", import.meta.url);

const EXPECTED_SCHEMA_VERSION = 3;
const MINIMUM_ENTRY_COUNT = 230;
const EXPECTED_REGION_COUNT = 17;
const RENDER_TARGETS = [
  "#dataset-facts",
  "#reference-records",
  "#case-scope-summary",
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
    ["사례 집계", `${data.meta.entry_count}건`],
    ["보존 원본", `${data.archival_count}개 레코드 · 보조 참고 ${data.reference_count}개는 사례 집계 제외`],
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

export function currentTypology(data) {
  data = caseSite(data);
  const count = (entries, key) => {
    const counts = new Map();
    for (const entry of entries) {
      const label = entry[key] || "미기록";
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return [...counts].sort(([a], [b]) => a.localeCompare(b, "ko"))
      .map(([label, total]) => `${label} ${total}건`);
  };
  const represented = new Set(data.entries.map(entry => entry.region_id));
  const scope = value => data.entries.filter(entry => entry.scope === value).length;
  const busan = data.entries.filter(entry => entry.region_id === "busan");
  return data.typology_axes.map(axis => {
    let values;
    let rationale = axis.rationale;
    if (axis.axis.includes("national regional coverage")) values = [
      `등록 지역 ${data.regions.length}개 시·도`, `positive entry 보유 ${represented.size}개 시·도`,
      `positive entry 미보유 ${data.regions.filter(region => !represented.has(region.id)).length}개 시·도`,
    ];
    else if (axis.axis.includes("national category coverage")) values = count(data.entries, "category");
    else if (axis.axis.includes("school_level")) values = count(data.entries, "school_level");
    else if (axis.axis.includes("geographic scope")) values = [
      `지도 적격 ${data.entries.filter(entry => !entry.off_map).length}건`,
      `지역 범위 ${scope("regional")}건 중 좌표 미확인 ${data.entries.filter(entry => entry.scope === "regional" && entry.off_map).length}건`, `전국 사업 off-map ${scope("nationwide")}건`,
      `인접 지역 off-map ${scope("adjacent")}건`, `위치 미상 off-map ${scope("unknown")}건`,
    ];
    else if (axis.axis.includes("Busan-only pattern")) {
      values = [...count(busan, "category"), `부산 regional ${busan.filter(entry => entry.scope === "regional").length}건`,
        `부산 off-map ${busan.filter(entry => entry.scope !== "regional").length}건`];
      rationale = "부산은 원 파일럿 지역이다. 현재 등록 사례의 부산 내부 분포이며 전국 결론으로 일반화하지 않는다.";
    }
    if (axis.axis.includes("geographic scope")) rationale = "좌표가 있는 regional 사례만 위치 표시 적격이다. 좌표 미확인 사례는 off-map으로 보존한다. 현재 전국 지도는 지역별 자료 수를 요약한다.";
    return { ...axis, values: values ?? axis.values, rationale };
  });
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
  const references = data.entries.filter(isReferenceRecord);
  data = caseSite(data);
  const targets = renderTargets();
  const fragments = Object.fromEntries(RENDER_TARGETS.map((selector) => [selector, document.createDocumentFragment()]));
  renderFacts(data, fragments["#dataset-facts"]);
  fragments["#case-scope-summary"].append(document.createTextNode(`원본 ${data.archival_count}개 레코드는 계보 보존용입니다. 지역별 지도 보조 표시로 만든 참고 자료 ${data.reference_count}개를 제외한 ${data.entries.length}개 사례만 검색·비교·지도에 집계합니다. 이는 현재 운영이나 지역 참여를 독립 검증했다는 뜻이 아닙니다.`));
  for (const record of references) {
    const item = element("li");
    appendText(item, "p", `기존 표기(지역 참여 확인 아님): ${record.name}`);
    appendText(item, "small", record.id);
    appendText(item, "p", "지역별 지도 보조 표시로 작성된 참고 자료입니다. 독립 사례·지역 참여·정확한 장소의 근거로 사용하지 않으며 검색·지도·비교 집계에서 제외합니다.");
    if (record.id === "visible-regional-jeonbuk-local-esports-event") appendText(item, "p", "동일 행사 사례: national-audit-jeonbuk-gunsan-amateur-esports-2026. 이 보조 표시는 중복 집계하지 않습니다.");
    fragments["#reference-records"].append(item);
  }
  renderTypology(currentTypology(data), fragments["#typology-axes"]);
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
