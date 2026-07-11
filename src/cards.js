function text(value, fallback = "미확인") {
  return value == null || value === "" ? fallback : String(value);
}

export const TYPE_LABELS = Object.freeze({ school: "학교", event: "대회", facility: "시설", other: "기타" });
export const CONFIDENCE_LABELS = Object.freeze({ high: "높음", medium: "보통", low: "낮음" });
export const OPERATIONAL_STATUS_LABELS = Object.freeze({ current: "운영 중", ended: "종료", needs_review: "확인 필요" });
export const SOURCE_LABELS = Object.freeze({ raw_source: "공개 자료" });
export const SCOPE_LABELS = Object.freeze({ regional: "지역", nationwide: "전국", adjacent: "인접 지역", unknown: "범위 미확인" });
export const SORT_LABELS = Object.freeze({ "name-asc": "이름 오름차순", "name-desc": "이름 내림차순", "year-asc": "연도 오름차순", "year-desc": "연도 내림차순" });


export function createEntryCard(entry, { selected = false } = {}) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "entry-card";
  card.dataset.entryId = entry.id;
  if (selected) card.setAttribute("aria-current", "true");

  const title = document.createElement("strong");
  title.textContent = text(entry.name);
  const meta = document.createElement("span");
  meta.className = "card-line";
  meta.textContent = [entry.region_name, TYPE_LABELS[entry.resource_type], entry.category].join(" · ");
  const facts = document.createElement("span");
  facts.className = "card-line";
  const checked = entry.status_checked_at;
  const sourceLabel = SOURCE_LABELS[entry.source_kind];
  facts.textContent = `최근 확인일: ${checked || "미확인"} · 출처 유형: ${sourceLabel}`;
  const badges = document.createElement("span");
  badges.className = "card-line card-badges";
  const confidence = entry.confidence == null ? "미확인" : CONFIDENCE_LABELS[entry.confidence];
  badges.textContent = `신뢰도 ${confidence} · 상태 ${OPERATIONAL_STATUS_LABELS[entry.operational_status]} · 범위 ${SCOPE_LABELS[entry.scope]}`;
  card.append(title, meta, facts, badges);
  return card;
}

export function renderCards(container, entries, selectedId) {
  container.replaceChildren();
  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "조건에 맞는 항목이 없습니다. 검색어나 필터를 조정해 보세요.";
    container.append(empty);
    return;
  }
  container.append(...entries.map((entry) => createEntryCard(entry, { selected: entry.id === selectedId })));
}
