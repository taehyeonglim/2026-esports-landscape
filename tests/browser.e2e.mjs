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
  await page.locator(`#national-map [data-region="${task.region}"]`).focus();
  await page.locator(`#national-map [data-region="${task.region}"]`).press("Enter");
  await expect(page.locator("#region-lens h2")).toContainText(task.region === "busan" ? "부산" : task.region === "seoul" ? "서울" : task.region === "gyeonggi" ? "경기" : task.region === "sejong" ? "세종" : "");
  await page.locator(`#region-lens [data-category="${task.category}"]`).click();
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
    test(`${task.id}: national map, regional signal, and card open the verified detail`, async ({ page }) => {
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

test("콜드 홈은 17개 시·도 지형도와 230건 중 첫 12건을 보여준다", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#result-count")).toHaveText("230개 중 12개 표시");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(12);
  await expect(page.locator("#national-map .national-region")).toHaveCount(17);
  await expect(page.locator("#load-more")).toBeVisible();
  const matrix = page.locator("#compare-matrix table");
  await expect(matrix.locator("tbody tr")).toHaveCount(17);
  await expect(matrix.locator("tfoot td").last()).toHaveText("230");
  await expect(page.locator(".matrix-caveat")).toContainText("실제 활동 규모나 순위를 나타내지 않습니다");
});

test("전용 브랜드 마크와 제작자 GitHub 링크가 실제 자산으로 노출된다", async ({ page }) => {
  await page.goto("/index.html");
  const logo = page.locator(".wordmark-mark img");
  await expect(logo).toBeVisible();
  await expect.poll(() => logo.evaluate((image) => image.complete && image.naturalWidth > 0)).toBe(true);
  await expect(page.locator('link[rel="icon"][sizes="32x32"]')).toHaveAttribute("href", "assets/favicon-32.png");
  const creator = page.locator(".footer-credit .creator-name");
  await expect(creator).toHaveText("Taehyeong Lim");
  await expect(creator).toHaveAttribute("href", "https://github.com/taehyeonglim");
  await expect(creator).toHaveAttribute("rel", /\bme\b/);
  await expect(page.locator(".creator-github")).toContainText("@taehyeonglim");
});

test("전국 지형도와 대표 사례가 데이터 탐색으로 이어진다", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#editorial-insights .signal-card")).toHaveCount(4);
  await expect(page.locator("#featured-stories .featured-card")).toHaveCount(3);

  await page.locator('#national-map [data-region="seoul"]').click();
  await expect(page.locator('#national-map [data-region="seoul"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#region-lens h2")).toContainText("서울");
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ region: "seoul" });

  await page.goto("/index.html");
  await page.locator('[data-feature-entry="busan-001"]').click();
  await expect(page.locator("#detail-panel")).toBeVisible();
  await expect(page.locator("#detail-heading")).toContainText("부산광역시교육청 e스포츠 챌린지 대회");
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ entry: "busan-001" });
});

test("매트릭스 열 헤더는 전 지역 카테고리 필터로, 행 헤더는 지역 필터로 이동한다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator("#explore > summary").click();
  await page.locator('#compare-matrix thead button[data-category="지자체정책·조례"]').click();
  await expect(page.locator("#result-count")).toHaveText("23개 중 12개 표시");
  await expect(page.locator("#results-heading")).toBeFocused();
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ category: "지자체정책·조례" });
  await page.locator('#compare-matrix tbody th button[data-region="busan"]').click();
  await expect(page.locator("#result-count")).toHaveText("27개 중 12개 표시");
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ region: "busan" });
});

test("유형 '기타' 66건이 고급 필터로 도달 가능하다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator(".advanced-filters summary").click();
  await page.locator("#type-filter").selectOption("other");
  await expect(page.locator("#result-count")).toHaveText("66개 중 12개 표시");
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

test("점진 노출로 기본 페이지 길이를 제한하면서 230건 전부 도달할 수 있다", async ({ page }) => {
  await page.goto("/index.html");
  const initialHeight = await page.evaluate(() => document.documentElement.scrollHeight / innerHeight);
  const compactViewport = await page.evaluate(() => innerWidth < 600);
  expect(initialHeight).toBeLessThan(compactViewport ? 16 : 10);
  for (let index = 0; index < 19; index += 1) {
    if (await page.locator("#load-more").isHidden()) break;
    await page.locator("#load-more").click();
  }
  await expect(page.locator("#result-list .entry-card")).toHaveCount(230);
  await expect(page.locator("#load-more")).toBeHidden();
});

test("전국 지도 자산 실패 시 지역 버튼으로 같은 탐색을 계속한다", async ({ page }) => {
  await page.route("**/data/national-map.v1.json", (route) => route.abort());
  await page.goto("/index.html");
  await expect(page.locator("#national-map")).toBeHidden();
  await expect(page.locator("#region-shortcuts button")).toHaveCount(17);
  await page.locator('[data-region-shortcut="busan"]').click();
  await expect(page.locator("#region-lens h2")).toContainText("부산");
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search))))
    .toEqual({ region: "busan" });
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
  await page.locator("#explore > summary").click();
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
  await page.locator("#explore > summary").click();
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
  await page.locator("#explore > summary").click();
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
