# 리그 방송 그래픽 리디자인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전국 학교 e스포츠 인덱스(메인 + research)의 시각 디자인을 딥네이비 + 골드/일렉트릭 블루의 "리그 방송 그래픽" 다크 테마로 전면 교체한다.

**Architecture:** 공유 디자인 토큰 파일(`styles/tokens.css`)에 색·타이포·모션 변수와 자기 호스팅 `@font-face`를 정의하고, `main.css`/`research.css`를 토큰 기반으로 재작성한다. HTML은 기존 ID/구조를 유지한 채 `<link>`·통계 리본만 추가한다. 빌드 파이프라인(`build.mjs`, `hash-dist.mjs`)에 woff2/txt 자산을 등록한다.

**Tech Stack:** 순수 CSS(빌드 도구 없음), ES 모듈, node --test, Playwright + axe, 기존 `scripts/build.mjs` 스테이징 빌드.

**Spec:** `docs/superpowers/specs/2026-07-13-esports-broadcast-redesign-design.md`

## Global Constraints

- e2e 계약 테스트가 참조하는 DOM 셀렉터 불변: `#region-select`, `#entry-search`, `#detail-panel`, `#detail-back`, `#map-status`, `#live-status`, `#result-list`, `#region-map`, `#detail-heading`, `#detail-content`, `[data-type]`, `[data-entry-id]`. `id="result-list"`는 DOM에서 `id="region-map"`보다 앞에 있어야 한다.
- 기존 테스트 파일 수정 금지 (`tests/unit.test.mjs`, `tests/e2e-contract.test.mjs`, `tests/browser.e2e.mjs`, `tests/python/*`). 신규 테스트 파일 추가만 허용.
- JS 수정 한정: `src/app.js`(리본 연결), 신규 `src/stat-ribbon.js`, `src/cards.js`(dataset 1줄). 다른 src 모듈 수정 금지.
- 외부 CDN 런타임 의존 금지. 폰트는 `styles/fonts/`에 자기 호스팅하고 OFL 라이선스 텍스트를 동봉한다.
- 모든 텍스트/배경 조합 WCAG AA(일반 4.5:1) 이상. 최종 판정은 `npm run test:browser`의 axe serious/critical 0건.
- `@media (prefers-reduced-motion: reduce)`에서 transition/animation 전부 비활성.
- 색상 팔레트·타이포·질감은 스펙 §1(디자인 시스템) 값을 사용한다.
- 커밋은 태스크마다 1회. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: 웹폰트 자산 다운로드·검증·커밋

**Files:**
- Create: `styles/fonts/PretendardStdVariable.woff2`
- Create: `styles/fonts/Rajdhani-SemiBold.woff2`
- Create: `styles/fonts/Rajdhani-Bold.woff2`
- Create: `styles/fonts/LICENSE-pretendard.txt`
- Create: `styles/fonts/LICENSE-rajdhani.txt`
- Create: `styles/fonts/SOURCES.txt`

**Interfaces:**
- Produces: 위 6개 파일 경로. Task 2가 게시 대상으로 등록하고 Task 3의 `@font-face`가 `fonts/<파일명>`으로 참조한다.

- [ ] **Step 1: 디렉토리 생성 및 Pretendard Std Variable 다운로드**

```bash
mkdir -p styles/fonts
curl -fL -o styles/fonts/PretendardStdVariable.woff2 \
  "https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/packages/pretendard-std/dist/web/variable/woff2/PretendardStdVariable.woff2"
curl -fL -o styles/fonts/LICENSE-pretendard.txt \
  "https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9/LICENSE"
```

404가 나면 `curl -s "https://data.jsdelivr.com/v1/packages/gh/orioncactus/pretendard@v1.3.9?structure=flat" | grep -o '"[^"]*PretendardStdVariable.woff2"'`로 실제 경로를 찾아 대체한다.

- [ ] **Step 2: Rajdhani latin 서브셋 woff2 다운로드**

Google Fonts css2 API에서 latin 서브셋 URL을 추출해 받는다:

```bash
curl -s -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
  "https://fonts.googleapis.com/css2?family=Rajdhani:wght@600;700&display=swap" -o /tmp/rajdhani-css2.css
node -e '
const css = require("fs").readFileSync("/tmp/rajdhani-css2.css", "utf8");
for (const block of css.split("@font-face").slice(1)) {
  if (!block.includes("U+0000-00FF")) continue;   // latin 서브셋 블록만
  const weight = block.match(/font-weight:\s*(\d+)/)[1];
  const url = block.match(/url\((https:[^)]+\.woff2)\)/)[1];
  console.log(weight, url);
}'
# 출력된 두 URL로:
curl -fL -o styles/fonts/Rajdhani-SemiBold.woff2 "<600 URL>"
curl -fL -o styles/fonts/Rajdhani-Bold.woff2 "<700 URL>"
curl -fL -o styles/fonts/LICENSE-rajdhani.txt \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/rajdhani/OFL.txt"
```

- [ ] **Step 3: 파일 형식·크기 검증**

```bash
file styles/fonts/*.woff2
ls -l styles/fonts/
```

Expected: 세 woff2 모두 `Web Open Font Format (Version 2)`. PretendardStdVariable > 500KB, Rajdhani 각각 10–40KB. LICENSE 두 파일에 `SIL OPEN FONT LICENSE` 문자열 존재(`grep -l "SIL OPEN FONT LICENSE" styles/fonts/LICENSE-*.txt` → 2개).

- [ ] **Step 4: 출처·체크섬 기록 (SOURCES.txt)**

```bash
cd styles/fonts && shasum -a 256 *.woff2 > SOURCES.txt && cd ../..
cat >> styles/fonts/SOURCES.txt <<'EOF'

origins:
- PretendardStdVariable.woff2: https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/... (SIL OFL 1.1, LICENSE-pretendard.txt)
- Rajdhani-SemiBold.woff2 / Rajdhani-Bold.woff2: Google Fonts css2 API latin subset, family=Rajdhani wght 600/700 (SIL OFL 1.1, LICENSE-rajdhani.txt)
EOF
```

(Step 2에서 실제 사용한 URL로 `...` 부분을 채운다.)

- [ ] **Step 5: Commit**

```bash
git add styles/fonts
git commit -m "Add self-hosted Pretendard Std and Rajdhani webfonts

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 빌드 파이프라인에 폰트 자산 등록

**Files:**
- Modify: `scripts/build.mjs:82` (publicFiles의 styles 필터)
- Modify: `scripts/hash-dist.mjs:13-19` (mimeTypes 맵)

**Interfaces:**
- Consumes: Task 1의 `styles/fonts/*` 파일.
- Produces: `dist/styles/fonts/*`가 게시되고 release-manifest에 `font/woff2` / `text/plain` MIME으로 해시 등재됨. Task 3의 HTML preload 링크가 이 산출물에 의존한다.

- [ ] **Step 1: build.mjs의 styles 게시 필터 확장**

`scripts/build.mjs` 82행:

```js
  ...(await sourceFiles(join(ROOT, 'styles'), 'styles')).filter(path => path.endsWith('.css')),
```

를 다음으로 교체:

```js
  ...(await sourceFiles(join(ROOT, 'styles'), 'styles')).filter(path => /\.(?:css|woff2|txt)$/.test(path)),
```

- [ ] **Step 2: hash-dist.mjs MIME 맵 확장**

`scripts/hash-dist.mjs`의 `mimeTypes` 객체(13행)에 두 항목 추가:

```js
const mimeTypes = Object.freeze({
  '.css': 'text/css; charset=utf-8',
  '.geojson': 'application/geo+json; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.txt': 'text/plain; charset=utf-8',
  '.woff2': 'font/woff2',
});
```

- [ ] **Step 3: 빌드 후 산출물 확인**

```bash
npm run build
ls dist/styles/fonts/
node -e "const m=require('./dist/release-manifest.json'); console.log(m.assets.filter(a=>a.path.startsWith('styles/fonts/')).map(a=>a.path+' '+a.mime));"
```

Expected: woff2 3개 + txt 3개가 나열되고, MIME이 각각 `font/woff2`, `text/plain; charset=utf-8`.

- [ ] **Step 4: e2e 계약 테스트로 매니페스트 무결성 확인**

```bash
npm run test:e2e
```

Expected: PASS (매니페스트가 배포 파일 전체를 정확히 1회씩 커버).

- [ ] **Step 5: Commit**

```bash
git add scripts/build.mjs scripts/hash-dist.mjs
git commit -m "Publish webfont and license assets through the release pipeline

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 디자인 토큰 파일 + HTML link/preload 연결

**Files:**
- Create: `styles/tokens.css`
- Modify: `index.html` (head에 preload·link·theme-color 추가)
- Modify: `research/index.html` (head에 link·theme-color 추가)

**Interfaces:**
- Consumes: Task 1 폰트 파일 경로(`fonts/…`는 tokens.css 위치 기준 상대경로).
- Produces: CSS 커스텀 프로퍼티 `--bg-0/1/2/3, --line, --line-strong, --ink, --muted, --gold, --gold-soft, --blue, --focus, --status-current, --status-needs-review, --status-ended, --danger, --font-body, --font-display, --cut, --speed-fast, --speed-slow, --stripe`. Task 4·5·6의 CSS가 이 이름을 그대로 사용한다.

- [ ] **Step 1: styles/tokens.css 작성 (전체 내용)**

```css
/* Design tokens — league broadcast night theme. main.css/research.css 공용. */
@font-face {
  font-family: "Pretendard Std Variable";
  src: url("fonts/PretendardStdVariable.woff2") format("woff2-variations");
  font-weight: 45 920;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "Rajdhani";
  src: url("fonts/Rajdhani-SemiBold.woff2") format("woff2");
  font-weight: 600;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "Rajdhani";
  src: url("fonts/Rajdhani-Bold.woff2") format("woff2");
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}
:root {
  --bg-0: #0a1220;
  --bg-1: #0e1a2e;
  --bg-2: #14243c;
  --bg-3: #1c3050;
  --line: #26415f;
  --line-strong: #3a5c85;
  --ink: #e8eef7;
  --muted: #9fb2c8;
  --gold: #e3b341;
  --gold-soft: #f2cf7e;
  --blue: #4da3ff;
  --focus: #6cb8ff;
  --status-current: #35d6a7;
  --status-needs-review: #f0a35e;
  --status-ended: #9fb2c8;
  --danger: #ff9d8f;
  --font-body: "Pretendard Std Variable", system-ui, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
  --font-display: "Rajdhani", "Pretendard Std Variable", system-ui, sans-serif;
  --cut: 12px;
  --speed-fast: 150ms;
  --speed-slow: 240ms;
  --stripe: repeating-linear-gradient(-55deg, transparent 0 22px, rgba(77, 163, 255, 0.05) 22px 24px, transparent 24px 60px, rgba(227, 179, 65, 0.05) 60px 62px);
}
@media (prefers-reduced-motion: reduce) {
  :root { --speed-fast: 0ms; --speed-slow: 0ms; }
  *, *::before, *::after { transition: none !important; animation: none !important; scroll-behavior: auto !important; }
}
```

- [ ] **Step 2: index.html head 수정**

기존:

```html
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="공개 근거로 확인된 전국 학교 e스포츠 사례를 지역별로 탐색하는 인덱스">
  <title>전국 학교 e스포츠 인덱스</title>
  <link rel="stylesheet" href="styles/main.css">
```

를 다음으로 교체:

```html
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="공개 근거로 확인된 전국 학교 e스포츠 사례를 지역별로 탐색하는 인덱스">
  <meta name="theme-color" content="#0a1220">
  <title>전국 학교 e스포츠 인덱스</title>
  <link rel="preload" href="styles/fonts/Rajdhani-SemiBold.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="styles/fonts/Rajdhani-Bold.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="styles/tokens.css">
  <link rel="stylesheet" href="styles/main.css">
```

- [ ] **Step 3: research/index.html head 수정**

기존:

```html
  <link rel="stylesheet" href="../styles/research.css">
```

를 다음으로 교체:

```html
  <meta name="theme-color" content="#0a1220">
  <link rel="stylesheet" href="../styles/tokens.css">
  <link rel="stylesheet" href="../styles/research.css">
```

- [ ] **Step 4: 빌드 + e2e로 링크 무결성 확인**

```bash
npm run build && npm run test:e2e
```

Expected: PASS. (e2e가 두 HTML의 모든 로컬 href/src가 dist에 실재하는지 검사 — preload한 폰트 파일 포함.)

- [ ] **Step 5: Commit**

```bash
git add styles/tokens.css index.html research/index.html
git commit -m "Add broadcast design tokens and self-hosted font wiring

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: main.css 전면 재작성 (다크 방송 테마)

**Files:**
- Modify: `styles/main.css` (전체 교체)
- Modify: `src/cards.js:17` (dataset 1줄 추가)

**Interfaces:**
- Consumes: Task 3의 토큰 변수 전부.
- Produces: `.stat-ribbon .stat / .stat-value / .stat-label` 클래스 스타일(Task 5의 DOM이 사용), `.entry-card[data-status="…"]` 상태 바 규칙(cards.js dataset이 공급).

- [ ] **Step 1: cards.js에 상태 dataset 추가**

`src/cards.js`의 `createEntryCard`에서 `card.dataset.entryId = entry.id;` 바로 다음 줄에 추가:

```js
  card.dataset.status = entry.operational_status;
```

- [ ] **Step 2: styles/main.css 전체를 다음 내용으로 교체**

```css
/* 전국 학교 e스포츠 인덱스 — 리그 방송 나이트 테마. styles/tokens.css 선행 로드 필요. */
* { box-sizing: border-box; }
html { background: var(--bg-0); }
body {
  margin: 0;
  color: var(--ink);
  font: 16px/1.6 var(--font-body);
  background:
    var(--stripe),
    radial-gradient(120% 90% at 85% -10%, #16294a 0%, var(--bg-0) 55%);
  background-attachment: fixed;
}

.skip-link { position: absolute; left: 1rem; top: -5rem; background: var(--gold); color: var(--bg-0); font-weight: 800; padding: .65rem 1rem; z-index: 2; }
.skip-link:focus { top: 1rem; }

/* ── 방송 헤더 ─────────────────────────────────────────── */
.site-header {
  position: relative;
  color: var(--ink);
  padding: clamp(1.5rem, 5vw, 4rem) max(1rem, calc((100% - 1180px) / 2)) clamp(2rem, 5vw, 4.5rem);
  background:
    linear-gradient(115deg, rgba(227, 179, 65, .08) 0%, transparent 38%),
    linear-gradient(180deg, #101f3a 0%, var(--bg-0) 100%);
  border-bottom: 1px solid var(--line);
  overflow: hidden;
}
.site-header::before { content: ""; position: absolute; inset: 0; background: var(--stripe); pointer-events: none; }
.site-header::after {
  /* 골드+블루 더블 라인 — 방송 로워서드 모티프 */
  content: "";
  position: absolute; left: 0; right: 0; bottom: 0; height: 7px;
  background:
    linear-gradient(90deg, var(--gold) 0 34%, transparent calc(34% + 1px)) top / 100% 4px no-repeat,
    linear-gradient(90deg, var(--blue) 0 100%) bottom / 100% 2px no-repeat;
}
.site-header > * { position: relative; }
.eyebrow {
  margin: 0;
  color: var(--gold);
  font-family: var(--font-display);
  font-size: .95rem;
  font-weight: 700;
  letter-spacing: .35em;
  text-transform: uppercase;
}
.eyebrow::before { content: "// "; color: var(--blue); letter-spacing: 0; }
.site-header h1 {
  font-size: clamp(2.1rem, 5vw, 4.2rem);
  font-weight: 900;
  line-height: 1.06;
  letter-spacing: -.02em;
  margin: .35rem 0 1.1rem;
}

/* 통계 리본 — 방송 스코어보드 (JS가 채우기 전까지 hidden) */
.stat-ribbon { display: flex; flex-wrap: wrap; gap: .6rem 2.2rem; margin: 0 0 1.6rem; }
.stat-ribbon .stat { display: inline-flex; align-items: baseline; gap: .5rem; }
.stat-ribbon .stat-value { font-family: var(--font-display); font-weight: 700; font-size: 1.9rem; line-height: 1; color: var(--gold); }
.stat-ribbon .stat-label { font-family: var(--font-display); font-weight: 600; font-size: .85rem; letter-spacing: .22em; text-transform: uppercase; color: var(--muted); }

.starter-controls { display: grid; grid-template-columns: minmax(12rem, 18rem) 1fr; gap: .65rem; align-items: end; max-width: 760px; }
.starter-controls label { font-weight: 700; }
.starter-controls select { grid-column: 1; }
.type-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
.type-actions button { min-height: 44px; flex: 1 1 6rem; }
.trust-note { max-width: 48rem; margin: 1.5rem 0 0; color: var(--muted); }

/* ── 레이아웃 셸과 패널 ─────────────────────────────────── */
.page-shell {
  max-width: 1180px; margin: auto; padding: clamp(1rem, 3vw, 2rem);
  display: grid; grid-template-columns: minmax(0, 1.85fr) minmax(18rem, 1fr);
  gap: 1.25rem; align-items: start;
}
.browse-panel, .detail-panel, .map-panel {
  background: linear-gradient(180deg, var(--bg-1) 0%, rgba(14, 26, 46, .92) 100%);
  border: 1px solid var(--line);
  border-top: 2px solid var(--line-strong);
  /* 사선 컷 — 패널은 포커스를 받지 않으므로 clip-path 사용 가능 */
  clip-path: polygon(0 0, calc(100% - var(--cut)) 0, 100% var(--cut), 100% 100%, 0 100%);
  padding: clamp(1rem, 2.5vw, 1.5rem);
  animation: panel-rise var(--speed-slow) ease-out;
}
@keyframes panel-rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.browse-panel { grid-column: 1; }
.detail-panel { grid-column: 1; }
.map-panel { grid-column: 2; grid-row: 1 / span 2; }

/* 패널 제목 밑 골드+라인 이중선 */
.results-heading, .map-heading { position: relative; padding-bottom: .7rem; margin: 0 0 1rem; }
.results-heading::after, .map-heading::after {
  content: ""; position: absolute; left: 0; bottom: 0; width: 100%; height: 5px;
  background:
    linear-gradient(90deg, var(--gold) 0 3.2rem, transparent calc(3.2rem + 1px)) top / 100% 3px no-repeat,
    linear-gradient(90deg, var(--line) 0 100%) bottom / 100% 1px no-repeat;
}
.results-heading { display: flex; justify-content: space-between; gap: 1rem; align-items: baseline; }
.results-heading h2, .map-heading h2 { font-size: 1.15rem; margin: 0; }
.results-heading p, .map-heading p { color: var(--muted); margin: .2rem 0; }

/* ── 입력 컨트롤 ────────────────────────────────────────── */
input, select, button { font: inherit; }
input, select {
  width: 100%; height: max(44px, 2.75em); min-height: 44px;
  border: 1px solid var(--line-strong); border-radius: 2px;
  padding: .65rem; background: var(--bg-0); color: var(--ink);
}
select option { background: var(--bg-0); color: var(--ink); }
input::placeholder { color: var(--muted); opacity: .8; }
button {
  border: 1px solid var(--line-strong); border-radius: 2px;
  background-color: var(--bg-2);
  /* 코너 노치 — clip-path는 포커스 아웃라인까지 잘라내므로 그라디언트로 흉내 */
  background-image: linear-gradient(225deg, var(--bg-1) 0 9px, transparent calc(9px + .5px));
  color: var(--ink); font-weight: 700; padding: .6rem .95rem; cursor: pointer;
  transition: background-color var(--speed-fast) ease, color var(--speed-fast) ease, border-color var(--speed-fast) ease;
}
button:hover { background-color: var(--bg-3); }
button[aria-pressed="true"] { background-color: var(--gold); color: var(--bg-0); font-weight: 800; border-color: var(--gold); }
button[aria-pressed="true"]:hover { background-color: var(--gold-soft); }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }

.advanced-filters { margin-top: 1rem; border-top: 1px solid var(--line); padding-top: .75rem; }
.advanced-filters summary { cursor: pointer; min-height: 44px; padding: .45rem 0; font-weight: 700; }
.search-row { display: grid; gap: .4rem; }
.search-row label { font-weight: 700; }
.filter-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; }
.filter-grid label { font-size: .9rem; font-weight: 700; }
.filter-grid button { align-self: end; min-height: 44px; }

/* ── 결과 카드 ──────────────────────────────────────────── */
.result-list { display: grid; gap: .7rem; }
.entry-card {
  width: 100%; text-align: left;
  background-color: var(--bg-2);
  background-image: linear-gradient(225deg, var(--bg-1) 0 10px, transparent calc(10px + .5px));
  color: var(--ink);
  border: 1px solid var(--line);
  border-left: 4px solid var(--line-strong);
  border-radius: 2px;
  padding: 1rem; min-height: 44px;
  transition: border-color var(--speed-fast) ease, background-color var(--speed-fast) ease, transform var(--speed-fast) ease;
}
.entry-card[data-status="current"] { border-left-color: var(--status-current); }
.entry-card[data-status="ended"] { border-left-color: var(--status-ended); }
.entry-card[data-status="needs_review"] { border-left-color: var(--status-needs-review); }
.entry-card:hover { border-color: var(--gold); background-color: var(--bg-3); transform: translateY(-2px); }
.entry-card[aria-current="true"] { border-color: var(--gold); border-left-color: var(--gold); background-color: var(--bg-3); }
.entry-card strong { display: block; font-size: 1.06rem; font-weight: 800; }
.entry-card .card-line { display: block; margin: .3rem 0 0; color: var(--muted); font-size: .88rem; }
.entry-card .card-badges { color: var(--gold-soft); font-weight: 700; font-size: .84rem; }

.empty-state { padding: 1rem; background: var(--bg-2); color: var(--muted); border: 1px dashed var(--line); }
.data-error { border: 1px solid #b42318; border-left: 4px solid #ff6b5e; background: rgba(180, 35, 24, .14); color: var(--danger); }

/* ── 상세 패널 (로워서드) ───────────────────────────────── */
.detail-panel h2 {
  margin: .8rem 0 0; font-size: clamp(1.4rem, 3vw, 2rem); font-weight: 900; line-height: 1.22;
  padding-left: .8rem; border-left: 5px solid var(--gold);
}
.detail-summary { color: var(--muted); }
.detail-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .65rem; margin: 1rem 0; }
.detail-facts > div { background: var(--bg-2); border: 1px solid var(--line); border-top: 2px solid var(--line-strong); padding: .7rem; }
.detail-facts dt { font-family: var(--font-display); font-weight: 600; font-size: .78rem; letter-spacing: .14em; text-transform: uppercase; color: var(--muted); }
.detail-facts dd { margin: .2rem 0 0; overflow-wrap: anywhere; }
.detail-notes { white-space: pre-wrap; overflow-wrap: anywhere; }
.detail-panel h3 { margin: 1.2rem 0 .4rem; font-size: 1rem; }
.detail-panel h4 { font-family: var(--font-display); letter-spacing: .08em; color: var(--muted); }
.detail-panel a, footer a { color: var(--blue); text-underline-offset: 3px; }
.detail-panel a:hover, footer a:hover { color: var(--focus); }

/* ── 지도 패널 ──────────────────────────────────────────── */
.map-heading { margin-bottom: .75rem; }
.map-panel svg { width: 100%; height: auto; min-height: 12rem; background: linear-gradient(180deg, var(--bg-0) 0%, #0d1c33 100%); border: 1px solid var(--line); }
.boundary { fill: rgba(77, 163, 255, .14); stroke: var(--gold); stroke-width: 1.4; filter: drop-shadow(0 0 6px rgba(77, 163, 255, .55)); }
.map-note { font-size: .88rem; color: var(--muted); }

footer { max-width: 1180px; margin: auto; padding: 1rem 2rem 3rem; color: var(--muted); font-size: .9rem; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }

@media (max-width: 700px) {
  .site-header { padding: 1.5rem 1rem 2rem; }
  .starter-controls { grid-template-columns: 1fr; }
  .starter-controls select { grid-column: auto; }
  .page-shell { display: flex; flex-direction: column; padding: 1rem; gap: 1rem; }
  .browse-panel, .detail-panel, .map-panel { width: 100%; }
  .map-panel { order: 3; }
  .filter-grid { grid-template-columns: 1fr; }
  .type-actions button { min-height: 44px; }
  .detail-facts { grid-template-columns: 1fr; }
  .stat-ribbon { gap: .5rem 1.4rem; }
  .stat-ribbon .stat-value { font-size: 1.5rem; }
}
```

- [ ] **Step 3: 빌드 + 브라우저 테스트 (axe 대비 검증)**

```bash
npm run build && npm run test:unit && npx playwright test
```

Expected: 전부 PASS. axe 대비 위반이 나오면 위반 조합의 전경색 명도를 올려 재실행 (팔레트 사전 계산상 muted/gold/blue 모두 6:1 이상이지만 axe가 최종 판정자).

- [ ] **Step 4: Commit**

```bash
git add styles/main.css src/cards.js
git commit -m "Restyle index as league broadcast night theme

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 통계 리본 (TDD)

**Files:**
- Create: `src/stat-ribbon.js`
- Create: `tests/stat-ribbon.test.mjs`
- Modify: `index.html` (h1 뒤에 리본 요소)
- Modify: `src/app.js` (import 1줄, elements 1줄, start() 1줄)
- Modify: `package.json` (test:unit에 신규 테스트 파일 등록)

**Interfaces:**
- Consumes: 검증 완료된 site 데이터 객체 `{ entries: [...230], regions: [...17], sources: [...230] }` (app.js `start()`의 `data`), Task 4의 `.stat-ribbon` CSS.
- Produces: `statRibbonModel(site) -> [{ value: number, label: string }]` (ENTRIES, REGIONS, SOURCES 순), `renderStatRibbon(container: HTMLElement, site) -> void` (컨테이너를 채우고 `hidden`을 해제).

- [ ] **Step 1: 실패하는 테스트 작성 — tests/stat-ribbon.test.mjs**

```js
import assert from "node:assert/strict";
import test from "node:test";
import { statRibbonModel } from "../src/stat-ribbon.js";

test("stat ribbon model mirrors loaded public data counts exactly", () => {
  const site = { entries: Array(3).fill({}), regions: Array(2).fill({}), sources: Array(5).fill({}) };
  assert.deepEqual(statRibbonModel(site), [
    { value: 3, label: "ENTRIES" },
    { value: 2, label: "REGIONS" },
    { value: 5, label: "SOURCES" },
  ]);
});

test("stat ribbon model fails closed on malformed collections", () => {
  assert.throws(() => statRibbonModel({ entries: [], regions: null, sources: [] }), /array/);
});
```

- [ ] **Step 2: package.json의 test:unit에 등록**

```json
    "test:unit": "node --test tests/unit.test.mjs tests/stat-ribbon.test.mjs",
```

- [ ] **Step 3: 실패 확인**

```bash
npm run test:unit
```

Expected: FAIL — `Cannot find module '../src/stat-ribbon.js'`. (기존 unit.test.mjs 16개는 계속 PASS.)

- [ ] **Step 4: src/stat-ribbon.js 구현**

```js
function requireArray(value, label) {
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  return value;
}

export function statRibbonModel(site) {
  return [
    { value: requireArray(site?.entries, "entries").length, label: "ENTRIES" },
    { value: requireArray(site?.regions, "regions").length, label: "REGIONS" },
    { value: requireArray(site?.sources, "sources").length, label: "SOURCES" },
  ];
}

export function renderStatRibbon(container, site) {
  container.replaceChildren(...statRibbonModel(site).map(({ value, label }) => {
    const item = document.createElement("span");
    item.className = "stat";
    const number = document.createElement("strong");
    number.className = "stat-value";
    number.textContent = String(value);
    const name = document.createElement("span");
    name.className = "stat-label";
    name.textContent = label;
    item.append(number, name);
    return item;
  }));
  container.hidden = false;
}
```

- [ ] **Step 5: 통과 확인**

```bash
npm run test:unit
```

Expected: PASS (16 + 2 = 18개).

- [ ] **Step 6: index.html에 리본 요소 추가**

`<h1>전국 학교 e스포츠 인덱스</h1>` 바로 다음 줄에:

```html
    <p class="stat-ribbon" id="stat-ribbon" hidden></p>
```

- [ ] **Step 7: app.js 연결 (3줄)**

7행 `import { renderDetail } ...` 아래에:

```js
import { renderStatRibbon } from "./stat-ribbon.js";
```

`elements` 객체의 `live: byId("live-status"),` 뒤에:

```js
  statRibbon: byId("stat-ribbon"),
```

`start()`에서 `sourcesByEntry = new Map(...)` 줄 다음에:

```js
    if (elements.statRibbon) renderStatRibbon(elements.statRibbon, data);
```

(데이터 로드/검증 실패 시 `start()`의 catch로 빠지므로 리본은 hidden 유지 — 스펙 요구.)

- [ ] **Step 8: 전체 확인**

```bash
npm run build && npm run test:unit && npm run test:e2e && npx playwright test
```

Expected: 전부 PASS.

- [ ] **Step 9: Commit**

```bash
git add src/stat-ribbon.js tests/stat-ribbon.test.mjs index.html src/app.js package.json
git commit -m "Add data-driven broadcast stat ribbon to the header

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: research.css 재작성

**Files:**
- Modify: `styles/research.css` (전체 교체)

**Interfaces:**
- Consumes: Task 3의 토큰 변수 전부. research/index.html의 기존 클래스(notice, fact-grid, panel, pills, bar-* 등).

- [ ] **Step 1: styles/research.css 전체를 다음 내용으로 교체**

```css
/* 연구 방법 페이지 — 리그 방송 나이트 테마. styles/tokens.css 선행 로드 필요. */
* { box-sizing: border-box; }
html { background: var(--bg-0); }
body {
  margin: 0; color: var(--ink);
  font: 16px/1.6 var(--font-body);
  background: var(--stripe), radial-gradient(120% 90% at 85% -10%, #16294a 0%, var(--bg-0) 55%);
  background-attachment: fixed;
}
a { color: var(--blue); text-underline-offset: 3px; }
a:hover { color: var(--focus); }
a:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }

.site-header { position: relative; border-bottom: 1px solid var(--line); background: linear-gradient(180deg, #101f3a 0%, var(--bg-0) 100%); }
.site-header::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 6px;
  background:
    linear-gradient(90deg, var(--gold) 0 34%, transparent calc(34% + 1px)) top / 100% 3px no-repeat,
    linear-gradient(90deg, var(--blue) 0 100%) bottom / 100% 2px no-repeat;
}
.header-inner, .research-shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; }
.header-inner { padding: 34px 0 30px; }
.eyebrow { margin: 0 0 3px; color: var(--gold); font-family: var(--font-display); font-size: 14px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; }
h1, h2, h3 { color: var(--ink); line-height: 1.28; }
h1 { margin: 0; font-size: clamp(28px, 4vw, 40px); font-weight: 900; letter-spacing: -.02em; }
h2 { margin: 0 0 14px; font-size: 21px; }
h3 { margin: 0 0 6px; font-size: 16px; }
.lede { max-width: 720px; margin: 7px 0 14px; color: var(--muted); }
.back-link {
  display: inline-flex; align-items: center; min-height: 44px; min-width: 44px;
  padding: 7px 12px; border: 1px solid var(--line-strong); background: var(--bg-2);
  color: var(--ink); font-weight: 700; text-decoration: none;
  transition: border-color var(--speed-fast) ease, background-color var(--speed-fast) ease;
}
.back-link:hover { border-color: var(--gold); background: var(--bg-3); color: var(--ink); }

.research-shell { display: grid; gap: 18px; padding: 26px 0 48px; }
.notice, .panel, .overview {
  border: 1px solid var(--line); border-top: 2px solid var(--line-strong);
  background: linear-gradient(180deg, var(--bg-1) 0%, rgba(14, 26, 46, .92) 100%);
  clip-path: polygon(0 0, calc(100% - var(--cut)) 0, 100% var(--cut), 100% 100%, 0 100%);
}
.notice { padding: 18px 20px; border-color: var(--gold); border-top-color: var(--gold); background: linear-gradient(180deg, rgba(227, 179, 65, .1) 0%, var(--bg-1) 70%); }
.notice h2 { color: var(--gold-soft); }
.notice p { margin: 0; color: var(--ink); }
.research-load-error { margin: 0; padding: 14px 18px; border: 2px solid #ff6b5e; background: rgba(180, 35, 24, .14); color: var(--danger); font-weight: 700; }
.overview, .panel { padding: 20px; }

.fact-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 0; }
.fact-grid div { min-height: 76px; padding: 12px; border: 1px solid var(--line); background: var(--bg-2); }
dt { color: var(--muted); font-family: var(--font-display); font-size: 12px; font-weight: 600; letter-spacing: .16em; text-transform: uppercase; }
dd { margin: 4px 0 0; color: var(--gold); font-family: var(--font-display); font-size: 24px; font-weight: 700; overflow-wrap: anywhere; }

.grid-section { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.stack, .record-list, .notes-list, .bar-list { display: grid; gap: 10px; margin: 0; padding: 0; list-style: none; }
.axis, .record, .note-item { padding: 12px; border: 1px solid var(--line); border-left: 3px solid var(--line-strong); background: var(--bg-2); }
.axis p, .record p, .note-item p { margin: 6px 0 0; overflow-wrap: anywhere; }
.pills { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.pill { padding: 3px 8px; border: 1px solid var(--line-strong); background: var(--bg-1); color: var(--muted); font-size: 13px; }
.bar-row { display: grid; grid-template-columns: minmax(120px, 1fr) 42px; gap: 10px; align-items: center; }
.bar-label { font-size: 14px; overflow-wrap: anywhere; }
.bar-value { color: var(--gold); font-family: var(--font-display); font-weight: 700; text-align: right; }
.bar-track { grid-column: 1 / -1; height: 8px; overflow: hidden; background: var(--bg-0); border: 1px solid var(--line); }
.bar-fill { height: 100%; background: linear-gradient(90deg, var(--blue), var(--gold)); }
.method-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.method-grid p, .section-note { margin: 0; color: var(--muted); }
.section-note { margin: -5px 0 13px; font-size: 14px; }
.record small { display: block; margin-top: 7px; color: var(--muted); }
.record strong { color: var(--ink); }
.provenance p { margin-top: 0; }
.provenance ul { margin-bottom: 0; padding-left: 20px; }

@media (max-width: 720px) {
  .header-inner, .research-shell { width: min(100% - 20px, 1120px); }
  .header-inner { padding: 20px 0; }
  .research-shell { padding-top: 12px; gap: 12px; }
  .overview, .panel, .notice { padding: 15px; }
  .fact-grid, .grid-section, .method-grid { grid-template-columns: 1fr; }
  .fact-grid div { min-height: auto; }
}
```

- [ ] **Step 2: 빌드 + 테스트**

```bash
npm run build && npm run test:e2e && npx playwright test
```

Expected: 전부 PASS (browser.e2e에 research 페이지 axe 스캔 포함).

- [ ] **Step 3: Commit**

```bash
git add styles/research.css
git commit -m "Restyle research page with shared broadcast tokens

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 전체 검증 + 비주얼 확인

**Files:**
- Create: `artifacts/redesign-preview/*.png` (gitignore 대상 — 커밋 안 함)

**Interfaces:**
- Consumes: Task 1–6의 모든 산출물.

- [ ] **Step 1: 전체 테스트 스위트**

```bash
npm run extract && npm run validate && npm run test:unit && npm run test:e2e && npm run test:browser
PYTHONPATH=src python3 -m unittest discover -s tests/python -p "test_*.py" 2>&1 | tail -3
```

Expected: JS 유닛 18개 / e2e 4개 / Playwright 5개 프로젝트 전부 PASS, Python `Ran 114 tests ... OK`.

- [ ] **Step 2: 데스크톱·모바일 스크린샷**

```bash
mkdir -p artifacts/redesign-preview
python3 -m http.server 4177 --directory dist &
SERVER_PID=$!
sleep 1
npx playwright screenshot --viewport-size=1440,900 --wait-for-timeout=1500 "http://127.0.0.1:4177/index.html" artifacts/redesign-preview/index-desktop.png
npx playwright screenshot --viewport-size=390,844  --wait-for-timeout=1500 "http://127.0.0.1:4177/index.html" artifacts/redesign-preview/index-mobile.png
npx playwright screenshot --viewport-size=1440,900 --wait-for-timeout=1500 "http://127.0.0.1:4177/research/index.html" artifacts/redesign-preview/research-desktop.png
kill $SERVER_PID
```

- [ ] **Step 3: 스크린샷 육안 검수**

스크린샷 3장을 열어 확인: (1) 다크 네이비 배경 + 골드/블루 더블 라인, (2) 통계 리본 `230 / 17 / 230` 표시, (3) 사선 컷 패널, (4) 모바일 1열 레이아웃. 리본이 비어 있으면 app.js 연결(Task 5 Step 7)을 재점검한다.

- [ ] **Step 4: 사용자 검수 요청**

로컬 서버(`python3 -m http.server 4177 --directory dist`)를 띄워 사용자가 직접 탐색(지역 선택 → 카드 → 상세 → 지도)하도록 안내하고, 피드백을 받아 반영한다.

---

## 실행 순서와 의존성

Task 1 → 2 → 3 → 4 → 5 → 6 → 7 순차 실행. (2는 1의 파일에, 3은 2의 게시에, 4·5·6은 3의 토큰에 의존. 5의 리본 CSS는 4에 포함되어 있음.)
