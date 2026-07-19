const FEATURED_IDS = Object.freeze([
  "busan-001",
  "elementary-jeju-2025-jejunam-esports-room",
  "national-completion-jeonbuk-esports-ordinance",
]);

const FEATURED_NOTES = Object.freeze({
  "busan-001": "교육청 주관 학생 대회 및 거점 공간 운영 사례",
  "elementary-jeju-2025-jejunam-esports-room": "학교 내 e스포츠실을 수업과 학생 활동에 활용한 사례",
  "national-completion-jeonbuk-esports-ordinance": "지역 e스포츠 지원 근거를 규정한 조례",
});

function countBy(entries, key) {
  return entries.reduce((counts, entry) => {
    const value = entry[key];
    counts.set(value, (counts.get(value) ?? 0) + 1);
    return counts;
  }, new Map());
}

export function editorialModel(site) {
  if (!Array.isArray(site?.entries) || !Array.isArray(site?.regions)) throw new TypeError("Editorial data requires entries and regions.");
  const typeCounts = countBy(site.entries, "resource_type");
  const regionById = new Map(site.regions.map((region) => [region.id, region.name]));
  const entryById = new Map(site.entries.map((entry) => [entry.id, entry]));
  const insights = [
    {
      count: typeCounts.get("event") ?? 0,
      label: "대회·행사",
      title: "교육청·지역 대회 및 사업",
      body: "대회·행사 유형으로 분류된 공개자료입니다.",
    },
    {
      count: typeCounts.get("school") ?? 0,
      label: "학교 기반",
      title: "학교 동아리·팀·수업",
      body: "학교 기반 유형으로 분류된 공개자료입니다.",
    },
    {
      count: typeCounts.get("facility") ?? 0,
      label: "공간·시설",
      title: "경기장·교육 시설",
      body: "공간·시설 유형으로 분류된 공개자료입니다.",
    },
    {
      count: typeCounts.get("other") ?? 0,
      label: "정책·진로·미디어",
      title: "정책·조례·진로·미디어",
      body: "정책, 조례, 대학 전공, 언론 관련 공개자료입니다.",
    },
  ];
  const featured = FEATURED_IDS.map((id) => {
    const entry = entryById.get(id);
    if (!entry) throw new RangeError(`Missing featured editorial entry: ${id}`);
    return {
      id,
      name: entry.name,
      category: entry.category,
      year: entry.year || "연도 미기록",
      region: regionById.get(entry.region_id) || entry.region_id,
      operator: entry.operator,
      note: FEATURED_NOTES[id],
    };
  });
  return { insights, featured };
}

function appendText(parent, tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  parent.append(element);
  return element;
}

export function renderEditorial(insightsContainer, featuredContainer, model) {
  insightsContainer.replaceChildren(...model.insights.map((insight, index) => {
    const article = document.createElement("article");
    article.className = "signal-card";
    article.dataset.tone = String(index + 1);
    const metric = document.createElement("p");
    metric.className = "signal-metric";
    appendText(metric, "strong", "", String(insight.count));
    appendText(metric, "span", "", insight.label);
    article.append(metric);
    appendText(article, "h3", "", insight.title);
    appendText(article, "p", "signal-body", insight.body);
    return article;
  }));

  featuredContainer.replaceChildren(...model.featured.map((entry, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "featured-card";
    button.dataset.featureEntry = entry.id;
    button.setAttribute("aria-label", `${entry.name} 상세 사례 보기`);
    const top = document.createElement("span");
    top.className = "featured-topline";
    appendText(top, "span", "featured-number", `0${index + 1}`);
    appendText(top, "span", "featured-meta", `${entry.region} · ${entry.year}`);
    button.append(top);
    appendText(button, "span", "featured-category", entry.category);
    appendText(button, "strong", "featured-title", entry.name);
    appendText(button, "span", "featured-note", entry.note);
    appendText(button, "span", "featured-operator", entry.operator);
    appendText(button, "span", "featured-link", "근거와 상세 보기 →");
    return button;
  }));
}
