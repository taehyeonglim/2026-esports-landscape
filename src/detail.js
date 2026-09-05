import { reviewState, REVIEW_LABELS } from "./review-status.js";
import { CONFIDENCE_LABELS, OPERATIONAL_STATUS_LABELS, SCOPE_LABELS, SOURCE_LABELS, TYPE_LABELS } from "./cards.js";
const SOURCE_VERIFICATION_LABELS = Object.freeze({ needs_review: "확인 필요", verified: "검증됨", rejected: "제외됨" });

function value(item, fallback = "미확인") {
  if (Array.isArray(item)) return item.length ? item.join(", ") : fallback;
  return item == null || item === "" ? fallback : String(item);
}

function safeHttpUrl(raw) {
  try {
    const url = new URL(String(raw));
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function field(label, item) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const description = document.createElement("dd");
  description.textContent = value(item);
  wrapper.append(term, description);
  return wrapper;
}

export function renderDetail(container, entry, sources = []) {
  const heading = document.createElement("h2");
  heading.id = "detail-heading";
  heading.tabIndex = -1;
  heading.textContent = value(entry.name);
  const summary = document.createElement("p");
  summary.className = "detail-summary";
  summary.textContent = [entry.region_name, entry.category, entry.year].filter(Boolean).join(" · ");
  const status = document.createElement("div");
  status.className = "detail-status";
  [
    `상태 ${OPERATIONAL_STATUS_LABELS[entry.operational_status]}`,
    `신뢰도 ${entry.confidence == null ? "미확인" : CONFIDENCE_LABELS[entry.confidence]}`,
    `범위 ${SCOPE_LABELS[entry.scope]}`,
  ].forEach((label) => {
    const badge = document.createElement("span");
    badge.textContent = label;
    status.append(badge);
  });
  const notes = document.createElement("p");
  notes.className = "detail-notes";
  notes.textContent = entry.public_note;
  const reviewFacts = document.createElement("dl");
  reviewFacts.className = "detail-facts";
  [["세부 유형", entry.subtype], ["유형 설명", entry.subtype_note], ["사례별 근거·한계", entry.notes], ["근거 검토", REVIEW_LABELS[reviewState(entry)]], ["최근 검토 시도", entry.operational_review?.checked_at], ["다음 검토일", entry.operational_review?.next_review_at], ["판정 이유", entry.review?.reason]].forEach(([label, item]) => reviewFacts.append(field(label,item)));
  const sourceHeading = document.createElement("h3");
  sourceHeading.textContent = "원문 출처";
  const list = document.createElement("ul");
  list.className = "source-list";
  if (sources.length === 0) {
    const item = document.createElement("li");
    item.textContent = "등록된 출처가 없습니다.";
    list.append(item);
  } else {
    for (const source of sources) {
      const item = document.createElement("li");
      const article = document.createElement("article");
      const identity = document.createElement("h4");
      identity.textContent = `${SOURCE_LABELS[source.kind]} · ${source.id}`;
      const metadata = document.createElement("p");
      metadata.textContent = `검증 상태: ${SOURCE_VERIFICATION_LABELS[source.verification_status]} · 최근 확인일: ${source.checked_at || "미확인"}`;
      const raw = document.createElement("p");
      raw.textContent = source.raw;
      const links = document.createElement("ul");
      links.className = "source-links";
      const safeUrls = source.urls.map(safeHttpUrl).filter(Boolean);
      if (safeUrls.length === 0) {
        const noLink = document.createElement("li");
        noLink.textContent = "안전한 웹 출처 링크가 등록되지 않았습니다.";
        links.append(noLink);
      } else {
        for (const url of safeUrls) {
          const linkItem = document.createElement("li");
          const link = document.createElement("a");
          link.href = url;
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = `${new URL(url).hostname}에서 원문 보기 ↗`;
          linkItem.append(link);
          links.append(linkItem);
        }
      }
      article.append(identity, metadata, raw, links);
      item.append(article);
      list.append(item);
    }
  }

  const metadataDetails = document.createElement("details");
  metadataDetails.className = "detail-metadata";
  const metadataSummary = document.createElement("summary");
  metadataSummary.textContent = "전체 메타데이터 보기";
  const facts = document.createElement("dl");
  facts.className = "detail-facts";
  const checked = entry.status_checked_at || "최근 확인일 미확인";
  [
    ["지역", entry.region_name], ["유형", TYPE_LABELS[entry.resource_type]], ["분류", entry.category], ["범위", SCOPE_LABELS[entry.scope]],
    ["운영 기관", entry.operator], ["학교급", entry.school_level], ["행정구역", entry.district],
    ["주소", entry.address], ["연도", entry.year], ["종목", entry.games], ["신뢰도", entry.confidence == null ? "미확인" : CONFIDENCE_LABELS[entry.confidence]],
    ["상태", OPERATIONAL_STATUS_LABELS[entry.operational_status]], ["최근 확인일", checked], ["출처 유형", SOURCE_LABELS[entry.source_kind]],
    ["상태 근거", entry.status_provenance || "독립 검증 근거 미확인"], ["상태 검토 사유", entry.review?.reason],
  ].forEach(([label, item]) => facts.append(field(label, item)));
  metadataDetails.append(metadataSummary, facts);
  container.replaceChildren(heading, summary, status, notes, reviewFacts, sourceHeading, list, metadataDetails);
  return heading;
}
