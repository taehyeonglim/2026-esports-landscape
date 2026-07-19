const FEATURED_IDS = Object.freeze([
  "busan-001",
  "elementary-jeju-2025-jejunam-esports-room",
  "national-completion-jeonbuk-esports-ordinance",
]);

const FEATURED_NOTES = Object.freeze({
  "busan-001": "교육청이 거점 공간과 운영 인력을 연결해 학생 대회를 만든 사례",
  "elementary-jeju-2025-jejunam-esports-room": "학교 안의 전용 공간을 수업과 활동의 출발점으로 삼은 사례",
  "national-completion-jeonbuk-esports-ordinance": "지역 차원의 제도적 지원 근거를 마련한 사례",
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
      title: "함께 모이는 장면이 가장 먼저 보입니다",
      body: "교육청과 지역 단위의 대회·사업이 공개자료에서 가장 넓게 확인됩니다.",
    },
    {
      count: typeCounts.get("school") ?? 0,
      label: "학교 기반",
      title: "학교 안의 작은 시작도 이어지고 있습니다",
      body: "동아리, 팀, 수업처럼 일상적인 학교 공간에서 시작된 기록을 모았습니다.",
    },
    {
      count: typeCounts.get("facility") ?? 0,
      label: "공간·시설",
      title: "활동을 지속할 장소가 만들어지고 있습니다",
      body: "상설경기장부터 교육 거점까지, 프로그램을 담는 지역 공간이 확인됩니다.",
    },
    {
      count: typeCounts.get("other") ?? 0,
      label: "정책·진로·미디어",
      title: "경기 밖의 생태계도 함께 자라고 있습니다",
      body: "정책, 조례, 대학 전공과 언론 기록이 학교 e스포츠의 외연을 보여 줍니다.",
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
