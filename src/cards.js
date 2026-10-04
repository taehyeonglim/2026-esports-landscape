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
  card.dataset.status = entry.operational_status;
  if (selected) card.setAttribute("aria-current", "true");

  const title = document.createElement("strong");
  title.textContent = text(entry.name);
  const meta = document.createElement("span");
  meta.className = "card-line";
  [entry.region_name, entry.category, entry.year].filter(Boolean).forEach((value, index) => {
    if (index) meta.append(" · ");
    const item = document.createElement("span");
    item.className = index === 0 ? "card-region" : "card-meta";
    item.textContent = String(value);
    meta.append(item);
  });
  const status = document.createElement("span");
  status.className = "card-status";
  status.textContent = `상태 ${OPERATIONAL_STATUS_LABELS[entry.operational_status]}`;
  const link = document.createElement("span");
  link.className = "card-link";
  link.textContent = "상세·원문 보기 →";
  card.append(meta, title, status, link);
  return card;
}

export function renderCards(container, entries, selectedId, state = {}) {
  container.replaceChildren();
  if (entries.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const message = document.createElement("p");
    message.textContent = "현재 조건에 맞는 공개자료가 없습니다. 검색어나 필터를 조정해 보세요.";
    const actions = document.createElement("div");
    actions.className = "empty-actions";
    for (const [key, label, show] of [["query", "검색어 제거", state.query], ["region", "지역 해제", state.region], ["all", "전체 초기화", true]]) {
      if (!show) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.emptyClear = key;
      button.textContent = label;
      actions.append(button);
    }
    empty.append(message, actions);
    container.append(empty);
    return;
  }
  container.append(...entries.map((entry) => createEntryCard(entry, { selected: entry.id === selectedId })));
}
