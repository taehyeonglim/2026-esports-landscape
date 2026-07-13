# 벤치마킹 홈 리디자인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 홈을 17개 시·도 × 8개 카테고리 비교 매트릭스 히어로로 재구성하고, 카테고리를 1급 필터로 승격하며, 결과 게이트를 제거해 230건 전체(특히 매몰된 'other' 66건)를 UI에서 도달 가능하게 만든다.

**Architecture:** 신규 `src/matrix.js`가 순수 카운트 모델(`matrixModel`)과 DOM 렌더러(`renderMatrix`)를 제공한다. `app.js`는 게이트를 제거하고 매트릭스 셀 선택을 기존 `HYDRATE` 액션 하나로 처리한다. `state.js`/`url-codec.js`/`search.js`는 무수정(빈 필터 전체 통과가 이미 구현돼 있음). 계약 테스트(AC01 픽스처·browser.e2e·e2e-contract)는 UI와 같은 태스크에서 함께 이동해 스위트를 항상 green으로 유지한다.

**Tech Stack:** 순수 ES 모듈, node --test, Playwright + axe, 기존 다크 토큰(tokens.css).

**Spec:** `docs/superpowers/specs/2026-07-14-benchmarking-home-redesign-design.md`

## Global Constraints

- `src/state.js`, `src/url-codec.js`, `src/search.js`, `tests/unit.test.mjs`, `tests/stat-ribbon.test.mjs`, Python 테스트, 데이터 파일, `pages.yml` 등 워크플로 — **무수정**.
- AC01 픽스처는 **파일명 유지(`tests/fixtures/ac01-tasks.v1.json`) + 내용 개정(revision 2)**. `human_approval.status`는 `pending`으로 되돌린다(사용자 검수 후 사용자가 직접 승인 기록).
- DOM 계약 유지: `#result-list`가 `#region-map`보다 앞, `#results-heading → #entry-search → #result-list → .map-panel` 문서 순서, 지도 SVG 비대화형.
- 모든 인터랙티브 컨트롤(button/input/select) 높이 ≥ 44.5px 플로어(서브픽셀 스냅 가드 — main.css 주석 참조).
- axe serious/critical 0건. `prefers-reduced-motion` 아래 smooth 스크롤 0회(스크롤 코드는 matchMedia 분기 필수).
- 페이지 본문 가로 오버플로 금지 — 매트릭스 가로 스크롤은 `.matrix-scroll` 내부에서만.
- 매트릭스 윤리 가드레일: 정렬·순위 UI 없음, 시·도 순서는 `regions` 배열 순서 고정, 표 직상단 캐비앗 문구 필수: "공개자료에서 확인한 사례 수이며, 지역의 실제 활동 규모나 순위를 나타내지 않습니다."
- 카테고리 정식 순서(단일 상수 `CATEGORY_ORDER`, matrix.js가 export, 매트릭스 열과 칩이 공유): 교육청대회·사업 → 지자체정책·조례 → 협회사업 → 학교동아리·팀 → 특성화고학과·과정 → 대학학과·전공·동아리 → 경기장·인프라 → 언론보도.
- 커밋은 태스크마다 1회, 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

## 코드베이스 핵심 사실 (구현자가 알아야 할 것)

- `filterEntries`(src/search.js)는 null/빈 필터를 전부 통과시킨다 — "230건 전체 표시"는 app.js의 `readyToBrowse` 게이트만 제거하면 된다.
- `actions.hydrate(overrides)` → `createAppState(overrides)`: 지정하지 않은 필드는 전부 기본값으로 리셋된다 — 매트릭스 셀 클릭의 "region/category만 남기고 초기화"에 정확히 부합. 단 `dispatch()`는 `SET_REGION`일 때만 지도를 스케줄하므로 hydrate 후 `scheduleMap(state.region)`을 명시 호출해야 한다.
- `TYPE_LABELS`(src/cards.js)에 `other: "기타"`가 이미 있다. `allowed().type`에도 `"other"`가 이미 있다(URL 코덱 무수정 근거).
- 픽스처 5건의 검증된 값: busan-001=교육청대회·사업(부산 셀 3), seoul club instructor=학교동아리·팀, gyeonggi game agency=경기장·인프라, sejong 2022=교육청대회·사업(세종 셀 4), busan-013=특성화고학과·과정(부산 셀 2).

---

### Task 1: 매트릭스 모델 (TDD)

**Files:**
- Create: `src/matrix.js` (모델 부분만 — 렌더러는 Task 2)
- Create: `tests/matrix.test.mjs`
- Modify: `package.json` (test:unit 등록)

**Interfaces:**
- Produces: `CATEGORY_ORDER: readonly string[]`, `categoryColumns(entries) -> string[]`, `matrixModel(entries, regions) -> { categories, rows: [{ regionId, regionName, cells: [{ category, count }], total }], columnTotals: [{ category, count }], grandTotal }`. Task 2의 renderMatrix·카테고리 칩이 사용.

- [ ] **Step 1: 실패하는 테스트 작성 — tests/matrix.test.mjs**

```js
import assert from "node:assert/strict";
import test from "node:test";
import { readFile } from "node:fs/promises";
import { CATEGORY_ORDER, categoryColumns, matrixModel } from "../src/matrix.js";

const site = JSON.parse(await readFile(new URL("../data/site.v3.json", import.meta.url), "utf8"));

test("matrix model is an exact 230-entry partition across 17 regions", () => {
  const model = matrixModel(site.entries, site.regions);
  assert.equal(model.grandTotal, 230);
  assert.equal(model.rows.length, 17);
  assert.equal(model.rows.reduce((sum, row) => sum + row.total, 0), 230);
  assert.equal(model.columnTotals.reduce((sum, column) => sum + column.count, 0), 230);
  assert.deepEqual(model.rows.map((row) => row.regionId), site.regions.map((region) => region.id));
  const busan = model.rows.find((row) => row.regionId === "busan");
  assert.equal(busan.cells.find((cell) => cell.category === "교육청대회·사업").count, 3);
  assert.equal(busan.cells.find((cell) => cell.category === "특성화고학과·과정").count, 2);
});

test("category columns keep canonical order and append unknown categories alphabetically", () => {
  const entries = [
    { region_id: "a", category: "언론보도" },
    { region_id: "a", category: "새유형B" },
    { region_id: "b", category: "교육청대회·사업" },
    { region_id: "b", category: "새유형A" },
  ];
  assert.deepEqual(categoryColumns(entries), ["교육청대회·사업", "언론보도", "새유형A", "새유형B"]);
  assert.equal(CATEGORY_ORDER.length, 8);
  const model = matrixModel(entries, [{ id: "a", name: "A" }, { id: "b", name: "B" }]);
  assert.deepEqual(model.rows.map((row) => row.total), [2, 2]);
  assert.equal(model.grandTotal, 4);
});

test("matrix model fails closed on malformed input and uncovered regions", () => {
  assert.throws(() => matrixModel(null, []), /array/);
  assert.throws(() => matrixModel([{ region_id: "ghost", category: "x" }], [{ id: "a", name: "A" }]), /exactly once/);
});
```

- [ ] **Step 2: package.json 등록**

`"test:unit"` 값을 다음으로 교체:

```json
    "test:unit": "node --test tests/unit.test.mjs tests/stat-ribbon.test.mjs tests/matrix.test.mjs",
```

- [ ] **Step 3: 실패 확인**

Run: `npm run test:unit`
Expected: FAIL — `Cannot find module '../src/matrix.js'` (기존 18개는 PASS 유지).

- [ ] **Step 4: src/matrix.js 구현 (모델)**

```js
export const CATEGORY_ORDER = Object.freeze([
  "교육청대회·사업",
  "지자체정책·조례",
  "협회사업",
  "학교동아리·팀",
  "특성화고학과·과정",
  "대학학과·전공·동아리",
  "경기장·인프라",
  "언론보도",
]);

function requireArray(value, label) {
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  return value;
}

/** 알려진 정식 순서를 우선하고, 데이터에만 있는 카테고리는 뒤에 가나다순으로 붙인다. */
export function categoryColumns(entries) {
  const present = new Set(requireArray(entries, "entries").map((entry) => String(entry.category)));
  const known = CATEGORY_ORDER.filter((category) => present.has(category));
  const unknown = [...present].filter((category) => !CATEGORY_ORDER.includes(category))
    .sort((left, right) => left.localeCompare(right, "ko"));
  return [...known, ...unknown];
}

export function matrixModel(entries, regions) {
  requireArray(entries, "entries");
  requireArray(regions, "regions");
  const categories = categoryColumns(entries);
  const counts = new Map();
  for (const entry of entries) {
    const key = `${entry.region_id} ${entry.category}`;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const rows = regions.map((region) => {
    const cells = categories.map((category) => ({
      category,
      count: counts.get(`${region.id} ${category}`) ?? 0,
    }));
    return {
      regionId: region.id,
      regionName: region.name,
      cells,
      total: cells.reduce((sum, cell) => sum + cell.count, 0),
    };
  });
  const columnTotals = categories.map((category, index) => ({
    category,
    count: rows.reduce((sum, row) => sum + row.cells[index].count, 0),
  }));
  const grandTotal = rows.reduce((sum, row) => sum + row.total, 0);
  if (grandTotal !== entries.length) throw new RangeError("Matrix totals must cover every entry exactly once.");
  return { categories, rows, columnTotals, grandTotal };
}
```

- [ ] **Step 5: 통과 확인**

Run: `npm run test:unit`
Expected: PASS (18 + 3 = 21개).

- [ ] **Step 6: Commit**

```bash
git add src/matrix.js tests/matrix.test.mjs package.json
git commit -m "Add region-by-category matrix model

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 벤치마킹 홈 전환 (UI + 계약 동시 이동)

UI와 그 계약 테스트는 한 몸으로 움직여야 스위트가 태스크 종료 시점에 green이다. 이 태스크는 크지만 모든 코드가 아래에 완전히 제공된다 — 순서대로 전사하라.

**Files:**
- Modify: `tests/fixtures/ac01-tasks.v1.json` (전체 교체)
- Modify: `index.html` (전체 교체)
- Modify: `src/matrix.js` (renderMatrix 추가)
- Modify: `src/app.js` (헝크 6곳)
- Modify: `src/cards.js` (메타 라인 1곳)
- Modify: `styles/main.css` (블록 교체/추가)
- Modify: `tests/browser.e2e.mjs` (전체 교체)
- Modify: `tests/e2e-contract.test.mjs` (헝크 1곳)

**Interfaces:**
- Consumes: Task 1의 `matrixModel`/`categoryColumns`/`CATEGORY_ORDER`.
- Produces: `renderMatrix(container, model, onSelect)` — onSelect는 `{ regionId?: string, category?: string }`를 받는다. 셀 버튼은 `td button[data-region][data-category]`, 열 헤더 버튼은 `thead button[data-category]`, 행 헤더 버튼은 `tbody th button[data-region]`. 카테고리 칩은 `[data-category-chip="<카테고리>"]`.

- [ ] **Step 1: AC01 픽스처 개정 — tests/fixtures/ac01-tasks.v1.json 전체를 다음으로 교체**

```json
{
  "fixture_version": "ac01-tasks.v1",
  "revision": 2,
  "human_approval": {
    "status": "pending",
    "approved_by": null,
    "approved_at": null,
    "note": "벤치마킹 홈 동선(매트릭스 셀 → 카드 → 상세 → 출처)으로 재정의됨. 저장소 소유자의 검수·승인 대기."
  },
  "tasks": [
    {
      "id": "U1",
      "target_name": "부산광역시교육청 e스포츠 챌린지 대회 (SW·AI교육거점센터)",
      "region": "busan",
      "category": "교육청대회·사업",
      "entry_id": "busan-001",
      "expected_source_url_sha256": "be3e18c76d42d7cb731cdb42ee5e1456aee5fb72420994328b59003f8c7edad8",
      "expected_source_url": "https://school.busanedu.net/common/nttFileDownload.do?fileKey=eec2298c5a7f2cb0646d6b54eabba136"
    },
    {
      "id": "U2",
      "target_name": "서울특별시 학교 이스포츠 클럽 강사 지원 참여 거점",
      "region": "seoul",
      "category": "학교동아리·팀",
      "entry_id": "visible-regional-seoul-school-club-instructor",
      "expected_source_url_sha256": "4ae1f260c2dc20f6f5ce7b43bb72c392b2d565e855e083779b6248f3f8339f8e",
      "expected_source_url": "https://school.e-sports.or.kr/"
    },
    {
      "id": "U3",
      "target_name": "경기콘텐츠진흥원·경기e스포츠협회 e스포츠 사업 거점",
      "region": "gyeonggi",
      "category": "경기장·인프라",
      "entry_id": "visible-regional-gyeonggi-regional-game-agency",
      "expected_source_url_sha256": "5f1bdeb196ebc8d013ae6b7e0c566e8e3fea2e587ec798da325f3b96ba022992",
      "expected_source_url": "https://www.gcon.or.kr/gcon/main/contents.do?menuNo=200032"
    },
    {
      "id": "U4",
      "target_name": "2022 세종 특수교육 e페스티벌 e스포츠대회 초등 대표 선발",
      "region": "sejong",
      "category": "교육청대회·사업",
      "entry_id": "elementary-sejong-2022-special-efestival",
      "expected_source_url_sha256": "edc766782c1b1738f78b81bbe137b037e746e5034bbeeca612c8dc74f207c33a",
      "expected_source_url": "https://www.sje.go.kr/special/na/ntt/selectNttInfo.do?mi=50641&nttSn=3005270"
    },
    {
      "id": "U5",
      "target_name": "부산컴퓨터과학고등학교 e스포츠게임과(e스포츠 계열)",
      "region": "busan",
      "category": "특성화고학과·과정",
      "entry_id": "busan-013",
      "expected_source_url_sha256": "05289d0cacec5231f1f6c01a2f95518005bf82c07b9e971e622c529bad62d741",
      "expected_source_url": "https://school.busanedu.net/pcs-h/cm/cntnts/cntntsView.do?mi=1046698&cntntsId=15558"
    }
  ]
}
```

- [ ] **Step 2: index.html 전체를 다음으로 교체**

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="17개 시·도의 학교 e스포츠 대회·정책·시설·동아리 사례를 근거 자료와 함께 비교하는 벤치마킹 인덱스">
  <meta name="theme-color" content="#0a1220">
  <title>전국 학교 e스포츠 인덱스</title>
  <link rel="preload" href="styles/fonts/Rajdhani-SemiBold.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="styles/fonts/Rajdhani-Bold.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="styles/tokens.css">
  <link rel="stylesheet" href="styles/main.css">
</head>
<body>
  <a class="skip-link" href="#results-heading">검색 결과로 건너뛰기</a>
  <header class="site-header">
    <p class="eyebrow">SCHOLASTIC ESPORTS LANDSCAPE</p>
    <h1>전국 학교 e스포츠 인덱스</h1>
    <p class="stat-ribbon" id="stat-ribbon" hidden></p>
    <p class="trust-note">교육청·지자체·학교 담당자가 다른 지역의 학교 e스포츠 대회·정책·시설·동아리 사례를 근거 자료와 함께 확인할 수 있습니다.</p>
  </header>

  <main class="page-shell">
    <section class="matrix-panel" aria-labelledby="matrix-heading">
      <div class="matrix-heading"><h2 id="matrix-heading">전국 비교 매트릭스</h2><p class="matrix-caveat">공개자료에서 확인한 사례 수이며, 지역의 실제 활동 규모나 순위를 나타내지 않습니다. <a href="research/">연구 방법과 한계</a></p></div>
      <div class="matrix-scroll" id="compare-matrix"></div>
    </section>

    <section class="browse-panel" aria-labelledby="results-heading">
      <div class="results-heading"><h2 id="results-heading" tabindex="-1">탐색 결과</h2><p id="result-count"></p></div>
      <div class="filter-row">
        <label for="region-select">지역</label>
        <select id="region-select"><option value="">전체 지역</option></select>
        <div class="category-actions" role="group" aria-label="카테고리 필터"></div>
      </div>
      <div class="search-row">
        <label for="entry-search">항목 검색</label>
        <input id="entry-search" type="search" autocomplete="off" placeholder="이름, 기관, 주소, 종목, 출처 검색">
      </div>
      <details class="advanced-filters">
        <summary>고급 필터</summary>
        <div class="filter-grid">
          <label>유형 <select id="type-filter"><option value="">전체</option></select></label>
          <label>학교급 <select id="school-level-filter"><option value="">전체</option></select></label>
          <label>상태 <select id="status-filter"><option value="">전체</option></select></label>
          <label>범위 <select id="scope-filter"><option value="">전체</option></select></label>
          <label>정렬 <select id="sort-filter"><option value="">기본순</option></select></label>
          <button id="reset-filters" type="button">필터 초기화</button>
        </div>
      </details>
      <p id="live-status" class="sr-only" aria-live="polite"></p>
      <div id="result-list" class="result-list"></div>
    </section>

    <section id="detail-panel" class="detail-panel" aria-labelledby="detail-heading" hidden>
      <button id="detail-back" type="button">결과로 돌아가기</button>
      <div id="detail-content"></div>
    </section>

    <section class="map-panel" aria-labelledby="map-heading">
      <div class="map-heading"><h2 id="map-heading">지역 경계 참고 지도</h2><p id="map-status" aria-live="polite">지역을 선택하면 경계를 불러옵니다.</p></div>
      <svg id="region-map" viewBox="0 0 860 680" role="img" aria-label="선택한 지역의 행정 경계 참고 지도" aria-describedby="region-map-description">
        <desc id="region-map-description">선택한 지역의 행정 경계를 표시하는 비대화형 참고도입니다.</desc>
        <g id="region-map-geometry"></g>
      </svg>
      <p class="map-note">지도는 참고용 보조 시각입니다. 항목 탐색과 상세 정보는 지도 없이도 사용할 수 있습니다.</p>
    </section>
  </main>
  <footer>자료의 범위와 수집 시점은 변동될 수 있습니다. <a href="research/">연구 방법과 범위 보기</a></footer>
  <script type="module" src="src/app.js"></script>
</body>
</html>
```

주의: 기존 파일과의 차이는 (1) meta description·trust-note 문구, (2) starter-controls 제거, (3) matrix-panel 신설, (4) browse-panel에 filter-row 신설, (5) 고급 필터의 `분류(#category-filter)` → `유형(#type-filter)` 교체뿐이다. 나머지 ID·구조는 그대로다.

- [ ] **Step 3: src/matrix.js 끝에 renderMatrix 추가**

```js
export function renderMatrix(container, model, onSelect) {
  const table = document.createElement("table");
  table.className = "compare-matrix";
  const caption = document.createElement("caption");
  caption.className = "sr-only";
  caption.textContent = "시·도별, 카테고리별 공개자료 확인 사례 수";
  table.append(caption);

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const corner = document.createElement("th");
  corner.scope = "col";
  corner.textContent = "시·도";
  headRow.append(corner);
  for (const category of model.categories) {
    const th = document.createElement("th");
    th.scope = "col";
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.category = category;
    button.textContent = category;
    button.setAttribute("aria-label", `전 지역 ${category} 사례 보기`);
    button.addEventListener("click", () => onSelect({ category }));
    th.append(button);
    headRow.append(th);
  }
  const totalHead = document.createElement("th");
  totalHead.scope = "col";
  totalHead.textContent = "합계";
  headRow.append(totalHead);
  thead.append(headRow);
  table.append(thead);

  const tbody = document.createElement("tbody");
  for (const row of model.rows) {
    const tr = document.createElement("tr");
    const rowHead = document.createElement("th");
    rowHead.scope = "row";
    const regionButton = document.createElement("button");
    regionButton.type = "button";
    regionButton.dataset.region = row.regionId;
    regionButton.textContent = row.regionName;
    regionButton.setAttribute("aria-label", `${row.regionName} 전체 사례 보기`);
    regionButton.addEventListener("click", () => onSelect({ regionId: row.regionId }));
    rowHead.append(regionButton);
    tr.append(rowHead);
    for (const cell of row.cells) {
      const td = document.createElement("td");
      if (cell.count > 0) {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.region = row.regionId;
        button.dataset.category = cell.category;
        button.textContent = String(cell.count);
        button.setAttribute("aria-label", `${row.regionName} ${cell.category} ${cell.count}건 보기`);
        button.addEventListener("click", () => onSelect({ regionId: row.regionId, category: cell.category }));
        td.append(button);
      } else {
        td.textContent = "·";
        td.className = "matrix-empty";
      }
      tr.append(td);
    }
    const rowTotal = document.createElement("td");
    rowTotal.className = "matrix-total";
    rowTotal.textContent = String(row.total);
    tr.append(rowTotal);
    tbody.append(tr);
  }
  table.append(tbody);

  const tfoot = document.createElement("tfoot");
  const footRow = document.createElement("tr");
  const footHead = document.createElement("th");
  footHead.scope = "row";
  footHead.textContent = "합계";
  footRow.append(footHead);
  for (const column of model.columnTotals) {
    const td = document.createElement("td");
    td.className = "matrix-total";
    td.textContent = String(column.count);
    footRow.append(td);
  }
  const grand = document.createElement("td");
  grand.className = "matrix-total";
  grand.textContent = String(model.grandTotal);
  footRow.append(grand);
  tfoot.append(footRow);
  table.append(tfoot);

  container.replaceChildren(table);
}
```

- [ ] **Step 4: src/app.js 헝크 편집 (6곳, 정확히 아래 old→new)**

**4a. import 추가** — `import { renderStatRibbon } from "./stat-ribbon.js";` 바로 아래에:

```js
import { matrixModel, renderMatrix } from "./matrix.js";
```

**4b. elements 확장** — 기존:

```js
  cards: byId("result-list"), count: byId("result-count"), detail: byId("detail-panel"), detailContent: byId("detail-content"),
```

을 다음으로 교체:

```js
  cards: byId("result-list"), count: byId("result-count"), detail: byId("detail-panel"), detailContent: byId("detail-content"),
  matrix: byId("compare-matrix"), typeFilter: byId("type-filter"), categoryActions: document.querySelector(".category-actions"),
```

그리고 elements 객체의 첫 줄(`region: byId("region-select"), search: byId("entry-search"), category: byId("category-filter"),`)에서 `category: byId("category-filter"),` 항목만 **삭제**한다 — `#category-filter`는 HTML에서 사라졌다.

**4c. populateStaticSelects에 유형 옵션 추가** — 함수 본문을 다음으로 교체:

```js
function populateStaticSelects() {
  populateSelect(elements.typeFilter, Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label })));
  populateSelect(elements.scope, Object.entries(SCOPE_LABELS).map(([value, label]) => ({ value, label })));
  populateSelect(elements.sort, Object.entries(SORT_LABELS).map(([value, label]) => ({ value, label })));
}
```

**4d. render() 게이트 제거** — 기존 render() 전체를 다음으로 교체:

```js
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
  renderCards(elements.cards, filtered, state.entry);
  elements.count.textContent = `${filtered.length}개 항목`;
  elements.live.textContent = `검색 결과 ${filtered.length}개`;
  const entry = entryById.get(state.entry);
  elements.detail.hidden = !entry;
  if (entry) renderDetail(elements.detailContent, entry, sourcesByEntry.get(entry.id) || []);
}
```

**4e. bindEvents 재배선** — 기존:

```js
  elements.category.addEventListener("change", (event) => dispatch(actions.setFilter("category", event.target.value ? [event.target.value] : []), "replace"));
```

을 다음으로 교체:

```js
  elements.typeFilter.addEventListener("change", (event) => dispatch(actions.setType(event.target.value || null), "replace"));
  elements.categoryActions.addEventListener("click", (event) => {
    const chip = event.target.closest("[data-category-chip]");
    if (!chip) return;
    const value = chip.dataset.categoryChip;
    dispatch(actions.setFilter("category", state.category[0] === value ? [] : [value]));
  });
```

그리고 기존 `.type-actions` 리스너 블록:

```js
  document.querySelector(".type-actions").addEventListener("click", (event) => {
    const button = event.target.closest("[data-type]"); if (button) dispatch(actions.setType(state.type === button.dataset.type ? null : button.dataset.type));
  });
```

을 **삭제**한다. render()의 `document.querySelectorAll("[data-type]")...` 줄은 4d에서 이미 사라졌다.

**4f. start()에 매트릭스·칩 연결** — 기존:

```js
    if (elements.statRibbon) renderStatRibbon(elements.statRibbon, data);
```

바로 아래에 추가:

```js
    const model = matrixModel(data.entries, data.regions);
    elements.categoryActions.replaceChildren(...model.categories.map((category) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.dataset.categoryChip = category;
      chip.setAttribute("aria-pressed", "false");
      chip.textContent = category;
      return chip;
    }));
    renderMatrix(elements.matrix, model, ({ regionId = null, category = null }) => {
      dispatch(actions.hydrate({ region: regionId, category: category ? [category] : [] }));
      scheduleMap(state.region);
      const heading = byId("results-heading");
      const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      heading?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
      heading?.focus({ preventScroll: true });
    });
```

그리고 start() 안의 기존 `populateSelect(elements.category, optionValues("category").map((value) => ({ value, label: value })));` 줄을 **삭제**한다.

- [ ] **Step 5: src/cards.js 메타 라인에 연도 추가**

기존:

```js
  meta.textContent = [entry.region_name, TYPE_LABELS[entry.resource_type], entry.category].join(" · ");
```

을 다음으로 교체:

```js
  meta.textContent = [entry.region_name, TYPE_LABELS[entry.resource_type], entry.category, entry.year].filter(Boolean).join(" · ");
```

- [ ] **Step 6: styles/main.css 편집**

**6a. 제거**: `.starter-controls { ... }`, `.starter-controls label`, `.starter-controls select`, `.type-actions`, `.type-actions button` 규칙 전부와, 모바일 미디어쿼리 안의 `.starter-controls { grid-template-columns: 1fr; }`, `.starter-controls select { grid-column: auto; }`, `.type-actions button { min-height: 44.5px; }` 제거.

**6b. 추가** — `.trust-note` 규칙 바로 아래에:

```css
/* ── 전국 비교 매트릭스 ──────────────────────────────────── */
.matrix-panel { grid-column: 1 / -1; }
.matrix-heading { position: relative; padding-bottom: .7rem; margin: 0 0 1rem; }
.matrix-heading::after {
  content: ""; position: absolute; left: 0; bottom: 0; width: 100%; height: 5px;
  background:
    linear-gradient(90deg, var(--gold) 0 3.2rem, transparent calc(3.2rem + 1px)) top / 100% 3px no-repeat,
    linear-gradient(90deg, var(--line) 0 100%) bottom / 100% 1px no-repeat;
}
.matrix-heading h2 { font-size: 1.15rem; margin: 0; }
.matrix-caveat { color: var(--muted); margin: .3rem 0 0; font-size: .9rem; }
.matrix-caveat a { color: var(--blue); }
.matrix-scroll { overflow-x: auto; }
.compare-matrix { border-collapse: collapse; width: 100%; min-width: 780px; font-size: .88rem; }
.compare-matrix th, .compare-matrix td { border: 1px solid var(--line); padding: .2rem; text-align: center; }
.compare-matrix thead th:first-child, .compare-matrix tbody th, .compare-matrix tfoot th {
  position: sticky; left: 0; background: var(--bg-1); text-align: left; z-index: 1; padding: .35rem .5rem;
}
.compare-matrix th button, .compare-matrix td button {
  width: 100%; min-height: 44.5px; padding: .3rem .4rem;
  background-color: transparent; background-image: none; border-color: transparent;
}
.compare-matrix th button:hover, .compare-matrix td button:hover { background-color: var(--bg-3); border-color: var(--gold); }
.compare-matrix td button { font-family: var(--font-display); font-weight: 700; font-size: 1.05rem; color: var(--gold); }
.compare-matrix .matrix-empty { color: var(--muted); }
.compare-matrix .matrix-total { color: var(--muted); font-family: var(--font-display); font-weight: 600; font-size: 1rem; }
.compare-matrix tfoot th, .compare-matrix tfoot td { border-top: 2px solid var(--line-strong); }

/* ── 필터 행 (지역 + 카테고리 칩) ────────────────────────── */
.filter-row { display: grid; grid-template-columns: auto minmax(10rem, 16rem); gap: .5rem .75rem; align-items: center; margin-bottom: .8rem; }
.filter-row label { font-weight: 700; }
.category-actions { grid-column: 1 / -1; display: flex; gap: .5rem; flex-wrap: wrap; }
.category-actions button { min-height: 44.5px; font-size: .88rem; }
```

**6c. 모바일 미디어쿼리에 추가** (`@media (max-width: 700px)` 블록 안, 6a에서 제거한 줄들 자리에):

```css
  .filter-row { grid-template-columns: 1fr; }
  .compare-matrix { font-size: .82rem; }
```

- [ ] **Step 7: tests/browser.e2e.mjs 전체를 다음으로 교체**

```js
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const fixture = JSON.parse(await readFile(new URL("./fixtures/ac01-tasks.v1.json", import.meta.url), "utf8"));
const dataUrl = "**/data/site.v3.json";
const expectedTaskIds = ["U1", "U2", "U3", "U4", "U5"];
const taskIds = fixture.tasks?.map((task) => task.id) ?? [];
if (
  fixture.tasks?.length !== expectedTaskIds.length
  || new Set(taskIds).size !== expectedTaskIds.length
  || expectedTaskIds.some((id) => !taskIds.includes(id))
  || fixture.tasks.some((task) => !task.target_name || !task.region || typeof task.category !== "string" || task.category.trim() === "" || !task.entry_id || !/^https:\/\//.test(task.expected_source_url) || !/^[a-f0-9]{64}$/.test(task.expected_source_url_sha256))
) {
  throw new Error("AC01 fixture must contain the exact complete U1-U5 contract.");
}
for (const task of fixture.tasks) {
  if (createHash("sha256").update(task.expected_source_url).digest("hex") !== task.expected_source_url_sha256) throw new Error(`AC01 source hash mismatch: ${task.id}`);
}

async function openTask(page, task) {
  await page.goto("/index.html");
  await page.locator(`#compare-matrix td button[data-region="${task.region}"][data-category="${task.category}"]`).click();
  const card = page.locator(`[data-entry-id="${task.entry_id}"]`);
  await expect(card).toBeVisible();
  await card.click();
  await expect(page.locator("#detail-panel")).toBeVisible();
  return card;
}

function seriousOrCritical(violations) {
  return violations.filter(({ impact }) => impact === "serious" || impact === "critical");
}

test.describe("AC01 browser activation contract", () => {
  for (const task of fixture.tasks) {
    test(`${task.id}: cold root matrix cell and card open the verified detail`, async ({ page }) => {
      const started = Date.now();
      await openTask(page, task);
      await expect(page.locator("#detail-heading")).toHaveText(task.target_name);
      const firstSource = page.locator("#detail-content h3 + ul a").first();
      await expect(firstSource).toHaveAttribute("href", task.expected_source_url);
      expect(createHash("sha256").update(await firstSource.getAttribute("href")).digest("hex"))
        .toBe(task.expected_source_url_sha256);
      await expect(page.locator("#detail-content h4").first()).toContainText("source-");
      await expect(page.locator("#detail-content dt").filter({ hasText: "상태 검토 사유" }).locator("+ dd")).not.toBeEmpty();
      expect(Date.now() - started).toBeLessThan(30_000);
    });
  }
});

test("콜드 홈은 230건 전체와 17개 시·도 매트릭스를 보여준다", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#result-count")).toHaveText("230개 항목");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(230);
  const matrix = page.locator("#compare-matrix table");
  await expect(matrix.locator("tbody tr")).toHaveCount(17);
  await expect(matrix.locator("tfoot td").last()).toHaveText("230");
  await expect(page.locator(".matrix-caveat")).toContainText("실제 활동 규모나 순위를 나타내지 않습니다");
});

test("매트릭스 열 헤더는 전 지역 카테고리 필터로, 행 헤더는 지역 필터로 이동한다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator('#compare-matrix thead button[data-category="지자체정책·조례"]').click();
  await expect(page.locator("#result-list .entry-card")).toHaveCount(23);
  await expect(page.locator("#results-heading")).toBeFocused();
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ category: "지자체정책·조례" });
  await page.locator('#compare-matrix tbody th button[data-region="busan"]').click();
  await expect(page.locator("#result-list .entry-card")).toHaveCount(27);
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ region: "busan" });
});

test("유형 '기타' 66건이 고급 필터로 도달 가능하다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator(".advanced-filters summary").click();
  await page.locator("#type-filter").selectOption("other");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(66);
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ type: "other" });
});

test("고급 필터는 접힌 상태로 시작하며 유형·범위·정렬·검색을 replaceState로 반영한다", async ({ page }) => {
  await page.goto("/index.html");
  const advanced = page.locator(".advanced-filters");
  await expect(advanced).not.toHaveAttribute("open", "");
  await expect(page.locator("#type-filter option")).toHaveText(["전체", "학교", "대회", "시설", "기타"]);
  await expect(page.locator("#scope-filter option")).toHaveText(["전체", "지역", "전국", "인접 지역", "범위 미확인"]);
  await expect(page.locator("#sort-filter option")).toHaveText(["기본순", "이름 오름차순", "이름 내림차순", "연도 오름차순", "연도 내림차순"]);

  await page.locator("#region-select").selectOption("busan");
  await page.locator('[data-category-chip="교육청대회·사업"]').click();
  await expect(page.locator('[data-category-chip="교육청대회·사업"]')).toHaveAttribute("aria-pressed", "true");
  const historyLength = await page.evaluate(() => history.length);
  await advanced.locator("summary").click();
  await page.locator("#scope-filter").selectOption("regional");
  await page.locator("#sort-filter").selectOption("name-asc");
  await page.locator("#entry-search").fill("zz-not-found");
  await expect(page.locator("#result-list .empty-state")).toBeVisible();
  await expect.poll(() => page.evaluate(() => ({ params: Object.fromEntries(new URLSearchParams(location.search)), length: history.length }))).toEqual({
    params: { region: "busan", category: "교육청대회·사업", q: "zz-not-found", scope: "regional", sort: "name-asc" },
    length: historyLength,
  });

  await page.locator("#entry-search").fill("");
  await expect(page.locator("#result-list .entry-card").first()).toBeVisible();
  await expect(page.locator("#result-list .entry-card").first()).toContainText("범위 지역");
  await page.locator("#result-list .entry-card").first().click();
  await expect(page.locator("#detail-content dt").filter({ hasText: "범위" }).locator("+ dd")).toHaveText("지역");
});

test("map is an inert reference and cannot change navigation state", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator("#region-select").selectOption("busan");
  await expect(page.locator("#map-status")).toContainText("표시했습니다");
  const map = page.locator("#region-map");
  await expect(map).toHaveAttribute("role", "img");
  await expect(map.locator("path")).not.toHaveCount(0);
  await expect(page.locator("#region-map-description")).toContainText("비대화형 참고도");
  const before = await page.evaluate(() => ({ href: location.href, length: history.length, state: history.state, resultCount: document.querySelector("#result-count").textContent, detailHidden: document.querySelector("#detail-panel").hidden, mapStatus: document.querySelector("#map-status").textContent }));
  await expect(map.locator("a,button,input,select,textarea,[tabindex],[role=button],[role=link]")).toHaveCount(0);
  await expect(map).not.toHaveAttribute("tabindex");
  const path = map.locator("path").first();
  await path.click({ force: true });
  await path.dispatchEvent("keydown", { key: "Enter" });
  await path.dispatchEvent("keydown", { key: " " });
  await expect.poll(() => page.evaluate(() => ({ href: location.href, length: history.length, state: history.state, resultCount: document.querySelector("#result-count").textContent, detailHidden: document.querySelector("#detail-panel").hidden, mapStatus: document.querySelector("#map-status").textContent }))).toEqual(before);
  await expect(page.locator("#region-map-description")).toContainText("비대화형 참고도");
});

test("detail back and browser history preserve the card-oriented navigation path", async ({ page }) => {
  const task = fixture.tasks[0];
  await openTask(page, task);
  await page.locator("#detail-back").click();
  await expect(page.locator("#detail-panel")).toBeHidden();
  await expect(page.locator(`[data-entry-id="${task.entry_id}"]`)).toBeFocused();

  await page.locator(`[data-entry-id="${task.entry_id}"]`).click();
  await page.goBack();
  await expect(page.locator("#detail-panel")).toBeHidden();
  await expect(page.locator(`[data-entry-id="${task.entry_id}"]`)).toBeFocused();
});

test("a pending then failed map request never blocks card activation", async ({ page }) => {
  let releaseRequest;
  let markRequested;
  const requested = new Promise((resolve) => { markRequested = resolve; });
  const release = new Promise((resolve) => { releaseRequest = resolve; });
  await page.route("**/geo/regions/busan.geojson", async (route) => {
    markRequested();
    await release;
    await route.abort();
  });
  await page.goto("/index.html");
  await page.locator("#region-select").selectOption("busan");
  await requested;
  const card = page.locator('[data-entry-id="busan-001"]');
  await expect(card).toBeVisible();
  await card.click();
  await expect(page.locator("#detail-heading")).toHaveText(fixture.tasks[0].target_name);
  releaseRequest();
  await expect(page.locator("#map-status")).toContainText("카드 탐색은 계속 사용할 수 있습니다");
});

test("malformed 229-entry public data fails closed", async ({ page }) => {
  await page.route(dataUrl, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.entries.pop();
    await route.fulfill({ response, contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.goto("/index.html");
  await expect(page.locator(".data-error")).toContainText("무결성 검증에 실패");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(0);
  await expect(page.locator("#compare-matrix table")).toHaveCount(0);
  await expect(page.locator("#result-count")).toHaveText("데이터를 표시할 수 없습니다.");
});

test("duplicate or cross-owned source references fail closed", async ({ page }) => {
  await page.route(dataUrl, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.entries[0].source_ids.push(payload.entries[0].source_ids[0]);
    await route.fulfill({ response, contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.goto("/index.html");
  await expect(page.locator(".data-error")).toContainText("무결성 검증에 실패");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(0);
});

test("current status without complete verification metadata fails closed", async ({ page }) => {
  await page.route(dataUrl, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.entries[0].operational_status = "current";
    await route.fulfill({ response, contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.goto("/index.html");
  await expect(page.locator(".data-error")).toContainText("무결성 검증에 실패");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(0);
});

test("desktop and narrow layouts keep browse before map without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/index.html");
  await expect(page.locator(".entry-card").first()).toBeVisible();
  const desktop = await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const rect = (selector) => document.querySelector(selector).getBoundingClientRect();
    const heading = document.querySelector("#results-heading");
    const search = document.querySelector("#entry-search");
    const cards = document.querySelector("#result-list");
    const map = document.querySelector(".map-panel");
    const matrix = document.querySelector(".matrix-panel");
    const browse = rect(".browse-panel");
    const mapRect = map.getBoundingClientRect();
    const domOrdered = Boolean(
      matrix.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING
      && heading.compareDocumentPosition(search) & Node.DOCUMENT_POSITION_FOLLOWING
      && search.compareDocumentPosition(cards) & Node.DOCUMENT_POSITION_FOLLOWING
      && cards.compareDocumentPosition(map) & Node.DOCUMENT_POSITION_FOLLOWING
    );
    return { ordered: domOrdered && browse.top <= mapRect.top, browse: browse.width, map: mapRect.width };
  });
  expect(desktop.ordered).toBe(true);
  expect(desktop.browse / (desktop.browse + desktop.map)).toBeGreaterThanOrEqual(0.6);
  expect(desktop.map / (desktop.browse + desktop.map)).toBeLessThanOrEqual(0.4);

  for (const width of [390, 320, 720]) {
    await page.setViewportSize({ width, height: 844 });
    const layout = await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const browse = document.querySelector(".browse-panel").getBoundingClientRect();
      const map = document.querySelector(".map-panel").getBoundingClientRect();
      const scroller = document.querySelector(".matrix-scroll");
      const controls = [...document.querySelectorAll("button,input,select")]
        .filter((element) => element.getClientRects().length > 0 && !element.hidden);
      return {
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        browseBeforeMap: browse.top <= map.top,
        controlCount: controls.length,
        minControl: Math.min(...controls.map((element) => element.getBoundingClientRect().height)),
        matrixScrolls: scroller.scrollWidth >= scroller.clientWidth,
      };
    });
    expect(layout.overflow).toBeLessThanOrEqual(0);
    expect(layout.controlCount).toBeGreaterThan(0);
    expect(layout.browseBeforeMap).toBe(true);
    expect(layout.minControl).toBeGreaterThanOrEqual(44);
    expect(layout.matrixScrolls).toBe(true);
  }
});

test("reduced motion removes all timing and matrix cell selection never smooth-scrolls", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.addInitScript(() => {
    window.__smoothScrollCalls = 0;
    const original = Element.prototype.scrollIntoView;
    Element.prototype.scrollIntoView = function scrollIntoView(options) {
      if (options?.behavior === "smooth") window.__smoothScrollCalls += 1;
      return original.call(this, options);
    };
  });
  await page.goto("/index.html");
  await page.locator('#compare-matrix td button[data-region="busan"][data-category="교육청대회·사업"]').click();
  await expect(page.locator(".entry-card").first()).toBeVisible();
  await expect(page.locator("#results-heading")).toBeFocused();
  const motion = await page.evaluate(() => {
    const timed = [...document.querySelectorAll("*")].filter((element) => {
      const style = getComputedStyle(element);
      const values = [style.transitionDuration, style.transitionDelay, style.animationDuration, style.animationDelay];
      return values.some((value) => value.split(",").some((part) => Number.parseFloat(part) !== 0));
    });
    return { timed: timed.length, scroll: getComputedStyle(document.documentElement).scrollBehavior, smoothCalls: window.__smoothScrollCalls };
  });
  expect(motion).toEqual({ timed: 0, scroll: "auto", smoothCalls: 0 });
});

test("root, matrix, results, detail, and research have no serious or critical axe violations", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator('#region-select option[value="busan"]')).toHaveCount(1);
  for (const selector of ["body", "#compare-matrix", "#result-list"]) {
    const results = await new AxeBuilder({ page }).include(selector).analyze();
    expect(seriousOrCritical(results.violations)).toEqual([]);
  }
  await openTask(page, fixture.tasks[0]);
  const detailResults = await new AxeBuilder({ page }).include("#detail-panel").analyze();
  expect(seriousOrCritical(detailResults.violations)).toEqual([]);

  await page.goto("/research/");
  await expect(page.locator("#dataset-facts dd")).toContainText([
    "v3",
    "230건",
    "17개 시·도",
    "230개 source ref",
    "승인된 기준일 없음",
    "확인 필요 230건 · 운영 중 0건 · 종료 0건",
    "학교 43건 · 대회 97건 · 시설 24건 · 기타 66건",
  ]);
  await expect(page.locator("#research-load-error")).toBeHidden();
  await expect(page.locator("#coverage-by-category > li")).toHaveCount(8);
  await expect(page.locator("#coordinate-source")).not.toContainText("불러오는 중");
  await expect(page.locator("#coordinate-source")).not.toBeEmpty();
  await expect(page.locator("#boundary-license")).not.toContainText("불러오는 중");
  await expect(page.locator("#boundary-license")).not.toBeEmpty();
  await expect(page.locator(".back-link")).toHaveCSS("min-height", "44px");
  for (const selector of ["#typology-axes", "#negative-evidence", "#data-gaps", "#site-notes"]) {
    await expect(page.locator(`${selector} > *`).first()).toBeVisible();
  }
  const researchResults = await new AxeBuilder({ page }).include("body").analyze();
  expect(seriousOrCritical(researchResults.violations)).toEqual([]);
});

test("malformed research data fails closed without partial rendering", async ({ page }) => {
  const errors = [];
  page.on("console", async (message) => {
    if (message.type() !== "error") return;
    const values = await Promise.all(message.args().map((argument) => argument.evaluate((value) => value instanceof Error ? `${value.name}: ${value.message}` : String(value))));
    errors.push(values.join(" "));
  });
  await page.route(dataUrl, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    delete payload.entries[0].confidence;
    await route.fulfill({ response, contentType: "application/json", body: JSON.stringify(payload) });
  });

  await page.goto("/research/");
  await expect(page.locator("#research-load-error")).toBeVisible();
  for (const selector of ["#dataset-facts", "#typology-axes", "#coverage-by-category", "#negative-evidence", "#data-gaps", "#site-notes", "#coordinate-source", "#boundary-license"]) {
    await expect(page.locator(selector)).toBeEmpty();
  }
  await expect.poll(() => errors.some((message) => message.includes(`Invalid research data: confidence for busan-001`))).toBe(true);
});
```

- [ ] **Step 8: tests/e2e-contract.test.mjs 헝크 1곳**

기존 (두 번째 테스트 안):

```js
  assert.match(html, /data-type/);
```

을 다음으로 교체:

```js
  assert.match(html, /id="compare-matrix"/);
  assert.match(html, /class="category-actions"/);
  assert.match(html, /id="type-filter"/);
```

- [ ] **Step 9: 전체 검증**

```bash
npm run build && npm run test:unit && npm run test:e2e && npx playwright test
```

Expected: unit 21개, e2e 4개, Playwright 전부 PASS (5개 프로젝트). axe 위반이 나오면 위반 조합의 전경색 명도만 조정하고 보고서에 기록.

- [ ] **Step 10: Commit**

```bash
git add tests/fixtures/ac01-tasks.v1.json index.html src/matrix.js src/app.js src/cards.js styles/main.css tests/browser.e2e.mjs tests/e2e-contract.test.mjs
git commit -m "Rebuild home around the national comparison matrix

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 전체 검증 + 스크린샷 + 도달성 확인

**Files:**
- Create: `artifacts/redesign-preview/matrix-*.png` (gitignore 대상 — 커밋 안 함)

**Interfaces:**
- Consumes: Task 1-2 산출물 전부.

- [ ] **Step 1: 릴리스 게이트 + Python 회귀**

```bash
npm run verify:release
PYTHONPATH=src python3 -m unittest discover -s tests/python -p "test_*.py" 2>&1 | tail -3
```

Expected: verify:release 마지막 JSON에 `"passed": true`; Python `Ran 114 tests ... OK`.

- [ ] **Step 2: 스크린샷**

```bash
mkdir -p artifacts/redesign-preview
python3 -m http.server 4177 --directory dist &
SERVER_PID=$!
sleep 1
npx playwright screenshot --viewport-size=1440,1400 --wait-for-timeout=1500 "http://127.0.0.1:4177/index.html" artifacts/redesign-preview/matrix-desktop.png
npx playwright screenshot --viewport-size=390,1600  --wait-for-timeout=1500 "http://127.0.0.1:4177/index.html" artifacts/redesign-preview/matrix-mobile.png
kill $SERVER_PID
```

- [ ] **Step 3: 스크린샷 육안 검수 (Read 도구로 직접 보기)**

체크: (1) 매트릭스 17행×8카테고리+합계가 히어로로 보임, (2) 캐비앗 문구 표시, (3) 카테고리 칩 행 표시, (4) 카드 230건 기본 표시(첫 카드들 보임), (5) 모바일에서 매트릭스가 내부 가로 스크롤로 수용됨.

- [ ] **Step 4: 도달성 스모크 (3클릭 계약)**

```bash
python3 -m http.server 4177 --directory dist &
SERVER_PID=$!
sleep 1
node -e '
const { chromium } = require("@playwright/test");
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("http://127.0.0.1:4177/index.html");
  // 1클릭: 매트릭스 셀 (busan × 지자체정책·조례)
  await page.locator("#compare-matrix td button[data-region=\"busan\"][data-category=\"지자체정책·조례\"]").click();
  // 2클릭: 첫 카드
  await page.locator("#result-list .entry-card").first().click();
  // 3클릭 대상 확인: 상세의 첫 출처 링크가 존재
  const href = await page.locator("#detail-content h3 + ul a").first().getAttribute("href");
  console.log(JSON.stringify({ threeClickTarget: href, ok: /^https?:\/\//.test(href) }));
  await browser.close();
})();'
kill $SERVER_PID
```

Expected: `"ok": true`.

- [ ] **Step 5: 보고**

커밋 없음(검증 전용). 결과를 보고서에 기록하고, **AC01 `human_approval`이 `pending`이므로 사용자 검수·승인 및 배포는 컨트롤러/사용자 몫**임을 명시한다.

---

## 실행 순서와 의존성

Task 1 → 2 → 3 순차. Task 2는 UI와 계약을 한 커밋으로 이동시키는 대형 태스크지만 모든 코드가 본 계획에 완결 제공된다.
