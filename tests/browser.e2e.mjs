import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const fixture = JSON.parse(await readFile(new URL("./fixtures/ac01-tasks.v1.json", import.meta.url), "utf8"));
const published = JSON.parse(await readFile(new URL("../data/site.v3.json", import.meta.url), "utf8"));
const publicCount = published.entries.length;
const statusCount = status => published.entries.filter(e=>e.operational_status===status).length;
const typeCount = type => published.entries.filter(e=>e.resource_type===type).length;
const dataUrl = "**/data/site.v3.json";
const expectedTaskIds = ["U1", "U2", "U3", "U4", "U5"];
const taskIds = fixture.tasks?.map((task) => task.id) ?? [];
if (
  fixture.revision !== 4
  || fixture.tasks?.length !== expectedTaskIds.length
  || new Set(taskIds).size !== expectedTaskIds.length
  || expectedTaskIds.some((id) => !taskIds.includes(id))
  || fixture.tasks.some((task) => !task.target_name || !task.region || typeof task.category !== "string" || task.category.trim() === "" || !task.entry_id || !/^https:\/\//.test(task.expected_source_url) || !/^[a-f0-9]{64}$/.test(task.expected_source_url_sha256))
) {
  throw new Error("AC01 revision 4 fixture must contain the exact complete U1-U5 contract.");
}
for (const task of fixture.tasks) {
  if (createHash("sha256").update(task.expected_source_url).digest("hex") !== task.expected_source_url_sha256) throw new Error(`AC01 source hash mismatch: ${task.id}`);
}

async function openTask(page, task) {
  await page.goto("/index.html");
  await page.locator("#entry-search").fill(task.target_name);
  const card = page.locator(`[data-entry-id="${task.entry_id}"]`);
  await expect(card).toBeVisible();
  await card.click();
  await expect(page.locator("#detail-panel")).toBeVisible();
  return card;
}

async function openFilterPanelWhenCompact(page) {
  const trigger = page.locator("#mobile-filter-trigger");
  if (await trigger.isVisible()) await trigger.click();
}

async function openAdvancedFilters(page) {
  const advanced = page.locator(".advanced-filters");
  if (await advanced.getAttribute("open") === null) await advanced.locator("summary").click();
}

function seriousOrCritical(violations) {
  return violations.filter(({ impact }) => impact === "serious" || impact === "critical");
}

test.describe("AC01 search-first activation contract", () => {
  for (const task of fixture.tasks) {
    test(`${task.id}: search, compact card, detail panel, and source link preserve verified evidence`, async ({ page }) => {
      const started = Date.now();
      await openTask(page, task);
      await expect(page.locator("#detail-heading")).toHaveText(task.target_name);
      const firstSource = page.locator(".source-links a").first();
      await expect(firstSource).toHaveAttribute("href", task.expected_source_url);
      expect(createHash("sha256").update(await firstSource.getAttribute("href")).digest("hex"))
        .toBe(task.expected_source_url_sha256);
      await expect(page.locator("#detail-content h4").first()).toContainText("source-");
      await expect(page.locator("#detail-content dt").filter({ hasText: "상태 검토 사유" }).locator("+ dd")).not.toBeEmpty();
      expect(Date.now() - started).toBeLessThan(30_000);
    });
  }
});

test("콜드 홈은 첫 화면에서 검색과 첫 결과를 제공하고 비교 차트는 지연 렌더링한다", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect(page.locator("#result-visible")).toHaveText("12개 표시");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(12);
  await expect(page.locator("#national-map .national-region")).toHaveCount(17);
  await expect(page.locator("#load-more")).toBeVisible();
  await expect(page.locator("#compare-matrix")).toBeEmpty();
  const viewport = page.viewportSize();
  const [search, card] = await Promise.all([page.locator("#entry-search").boundingBox(), page.locator(".entry-card").first().boundingBox()]);
  expect(search.y).toBeLessThan(viewport.height);
  expect(card.y).toBeLessThan(viewport.height);
});

test("공유 브랜드 셸과 제작자 링크가 실제 자산으로 노출된다", async ({ page }) => {
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

test("빠른 필터, 활성 조건 칩, 고급 필터와 전체 초기화가 URL과 결과를 동기화한다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator("#region-select").selectOption("busan");
  await openFilterPanelWhenCompact(page);
  await page.locator('[data-category-chip="교육청대회·사업"]').click();
  await openAdvancedFilters(page);
  await page.locator("#scope-filter").selectOption("regional");
  await expect(page.locator("#active-filters .active-filter")).toHaveCount(3);
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({
    region: "busan",
    category: "교육청대회·사업",
    scope: "regional",
  });
  await expect(page.locator("#mobile-filter-count")).toHaveText("2");
  await page.locator("#reset-filters").click();
  await expect(page.locator("#active-filters")).toBeEmpty();
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect.poll(() => page.evaluate(() => location.search)).toBe("");
});

test("모바일 필터는 모달 시트로 열리고 현재 결과 수와 포커스를 보존한다", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/index.html");
  await page.locator("#mobile-filter-trigger").click();
  await expect(page.locator("#filter-panel")).toBeVisible();
  expect(await page.locator("#filter-panel").evaluate((dialog) => dialog.matches(":modal"))).toBe(true);
  await page.locator('[data-category-chip="지자체정책·조례"]').click();
  await expect(page.locator("#filter-panel-result")).toHaveText("28건 결과 보기");
  await page.keyboard.press("Escape");
  await expect(page.locator("#filter-panel")).toBeHidden();
  await expect(page.locator("#mobile-filter-trigger")).toBeFocused();
  await expect(page.locator("#result-count")).toHaveText("28건");
});

test("지역 비교 탭은 공식 시도 순서를 사용하고 선택을 필터된 목록으로 연결한다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator("#compare-tab").click();
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({ view: "compare" });
  await expect(page.locator(".matrix-chart-row")).toHaveCount(17);
  await expect(page.locator(".matrix-chart-row").first()).toHaveAttribute("data-region", "seoul");
  await expect(page.locator("[data-matrix-sort]")).toHaveCount(0);
  await expect(page.locator(".matrix-chart-summary")).toHaveText(`${publicCount}건 · 17개 시·도 · 8개 유형`);
  const matrix = page.locator("#compare-matrix table");
  await expect(matrix.locator("tbody tr")).toHaveCount(17);
  await expect(matrix.locator("tfoot td").last()).toHaveText(String(publicCount));
  await expect(page.locator(".matrix-caveat")).toContainText("실제 활동 규모나 순위를 나타내지 않습니다");
  await page.locator('#compare-matrix .matrix-legend button[data-category="지자체정책·조례"]').click();
  await expect(page.locator("#browse-tab")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#result-count")).toHaveText("28건");
  await expect(page.locator("#results-heading")).toBeFocused();
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({ category: "지자체정책·조례" });
});

test("전국 지도는 지역 필터를 갱신하고 지도 실패 시 17개 지역 버튼으로 대체된다", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/index.html");
  await page.locator('#national-map [data-region="seoul"]').click();
  await expect(page.locator('#national-map [data-region="seoul"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#active-filters")).toContainText("서울특별시");
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({ region: "seoul" });

  await page.route("**/data/national-map.v1.json", (route) => route.abort());
  await page.goto("/index.html");
  await expect(page.locator("#national-map")).toBeHidden();
  await expect(page.locator("#region-shortcuts button")).toHaveCount(17);
  await page.locator('[data-region-shortcut="busan"]').click();
  await expect(page.locator("#active-filters")).toContainText("부산광역시");
});

test("상세 패널은 목록 맥락, URL, 닫기와 브라우저 뒤로가기 포커스를 보존한다", async ({ page }) => {
  const task = fixture.tasks[0];
  const card = await openTask(page, task);
  const isMobile = await page.evaluate(() => innerWidth <= 767);
  expect(await page.locator("#detail-panel").evaluate((dialog) => dialog.matches(":modal"))).toBe(isMobile);
  await page.locator("#detail-back").click();
  await expect(page.locator("#detail-panel")).toBeHidden();
  await expect(card).toBeFocused();
  expect(await page.evaluate(() => new URLSearchParams(location.search).has("entry"))).toBe(false);

  await card.click();
  await page.goBack();
  await expect(page.locator("#detail-panel")).toBeHidden();
  await expect(card).toBeFocused();
});

test("직접 상세 URL은 탐색 보기로 열리고 닫을 때 공유 가능한 필터 상태를 유지한다", async ({ page }) => {
  await page.goto("/index.html?view=compare&region=busan&entry=busan-001");
  await expect(page.locator("#detail-heading")).toContainText("부산광역시교육청 e스포츠 챌린지 대회");
  await expect(page.locator("#browse-tab")).toHaveAttribute("aria-selected", "true");
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({ region: "busan", entry: "busan-001" });
  await page.locator("#detail-back").click();
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({ region: "busan" });
});

test("결과 카드는 핵심 정보만 표시하고 상세에서 원문과 전체 메타데이터를 계층화한다", async ({ page }) => {
  await page.goto("/index.html");
  const card = page.locator(".entry-card").first();
  await expect(card).toContainText("상태");
  await expect(card).toContainText("상세·원문 보기");
  await expect(card).not.toContainText("최근 확인일");
  await card.click();
  await expect(page.locator(".source-links a").first()).toContainText("원문 보기");
  await expect(page.locator(".detail-metadata")).not.toHaveAttribute("open", "");
  await page.locator(".detail-metadata summary").click();
  await expect(page.locator(".detail-metadata .detail-facts")).toBeVisible();
  await expect(page.locator("#detail-content")).toContainText("다음 검토일");
});

test("점진 노출로 초기 길이를 제한하면서 235건 전부 도달할 수 있다", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(12);
  let guard = 0;
  while (await page.locator("#load-more").isVisible()) {
    await page.locator("#load-more").click();
    guard += 1;
    if (guard > 25) throw new Error("load more did not terminate");
  }
  await expect(page.locator("#result-list .entry-card")).toHaveCount(publicCount);
  await expect(page.locator("#result-visible")).toHaveText(`${publicCount}개 표시`);
});

test("malformed 229-entry public data fails closed", async ({ page }) => {
  await page.route(dataUrl, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.entries = payload.entries.slice(0, 229);
    payload.meta.entry_count = 229;
    await route.fulfill({ response, contentType: "application/json", body: JSON.stringify(payload) });
  });
  await page.goto("/index.html");
  await expect(page.locator(".data-error")).toContainText("무결성 검증에 실패");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(0);
  await expect(page.locator("#compare-matrix")).toBeEmpty();
  await expect(page.locator("#result-count")).toHaveText("데이터를 표시할 수 없습니다.");
});

test("duplicate or cross-owned source references fail closed", async ({ page }) => {
  await page.route(dataUrl, async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.entries[0].source_ids = [payload.entries[1].source_ids[0]];
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

test("desktop and narrow layouts preserve DOM order, first-view utility, touch targets, and horizontal containment", async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 720, height: 844 }, { width: 390, height: 844 }, { width: 320, height: 844 }]) {
    await page.setViewportSize(viewport);
    await page.goto("/index.html");
    await expect(page.locator(".entry-card").first()).toBeVisible();
    const layout = await page.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      const search = document.querySelector("#entry-search").getBoundingClientRect();
      const card = document.querySelector(".entry-card").getBoundingClientRect();
      const cards = document.querySelector("#result-list");
      const map = document.querySelector("#national-map");
      const controls = [...document.querySelectorAll("button,input,select,summary")]
        .filter((element) => element.getClientRects().length > 0 && !element.hidden);
      return {
        overflow: document.documentElement.scrollWidth - innerWidth,
        searchInView: search.top < innerHeight,
        cardInView: card.top < innerHeight,
        minControl: Math.min(...controls.map((element) => element.getBoundingClientRect().height)),
        resultBeforeMap: Boolean(cards.compareDocumentPosition(map) & Node.DOCUMENT_POSITION_FOLLOWING),
      };
    });
    expect(layout.overflow).toBeLessThanOrEqual(0);
    expect(layout.searchInView).toBe(true);
    expect(layout.cardInView).toBe(true);
    expect(layout.minControl).toBeGreaterThanOrEqual(44);
    expect(layout.resultBeforeMap).toBe(true);
  }
});

test("reduced motion removes all timing and comparison selection never smooth-scrolls", async ({ page }) => {
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
  await page.locator("#compare-tab").click();
  await page.locator('#compare-matrix .matrix-segment[data-region="busan"][data-category="교육청대회·사업"]').click();
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

test("home, comparison, responsive detail, filter dialog, and research have no serious or critical axe violations", async ({ page }) => {
  await page.goto("/index.html");
  let results = await new AxeBuilder({ page }).include("body").analyze();
  expect(seriousOrCritical(results.violations)).toEqual([]);

  await page.locator("#compare-tab").click();
  results = await new AxeBuilder({ page }).include("#compare-view").analyze();
  expect(seriousOrCritical(results.violations)).toEqual([]);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/index.html");
  await page.locator("#mobile-filter-trigger").click();
  results = await new AxeBuilder({ page }).include("#filter-panel").analyze();
  expect(seriousOrCritical(results.violations)).toEqual([]);
  await page.keyboard.press("Escape");
  await page.locator(".entry-card").first().click();
  results = await new AxeBuilder({ page }).include("#detail-panel").analyze();
  expect(seriousOrCritical(results.violations)).toEqual([]);

  await page.goto("/research/");
  await expect(page.locator("#dataset-facts dd")).toContainText([
    "v3",
    `${publicCount}건`,
    "17개 시·도",
    `${published.sources.length}개 source ref`,
    published.meta.data_updated_at,
    published.meta.validation_as_of ?? "승인된 기준일 없음",
    `확인 필요 ${statusCount('needs_review')}건 · 운영 중 ${statusCount('current')}건 · 종료 ${statusCount('ended')}건`,
    `학교 ${typeCount('school')}건 · 대회 ${typeCount('event')}건 · 시설 ${typeCount('facility')}건 · 기타 ${typeCount('other')}건`,
  ]);
  await expect(page.locator(".wordmark")).toContainText("학교 e스포츠 지형도");
  await expect(page.locator(".back-link")).toHaveCSS("min-height", "44px");
  results = await new AxeBuilder({ page }).include("body").analyze();
  expect(seriousOrCritical(results.violations)).toEqual([]);
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
  await expect.poll(() => errors.some((message) => message.includes("Invalid research data: confidence for busan-001"))).toBe(true);
});

test("근거 검토 필터 초기화와 사례별 한계 및 현재 연구 집계가 일치한다", async ({ page }) => {
  await page.goto("/index.html?reviewState=confirmed");
  await openFilterPanelWhenCompact(page);
  await openAdvancedFilters(page);
  await page.locator("#review-state-filter").selectOption("confirmed");
  await expect(page.locator("#result-count")).toHaveText("0건");
  await page.locator("#reset-filters").click();
  await expect(page.locator("#review-state-filter")).toHaveValue("");
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect.poll(() => page.evaluate(() => location.search)).toBe("");
  await page.goto("/index.html?entry=busan-016");
  const entry = published.entries.find(item => item.id === "busan-016");
  await expect(page.locator("#detail-content dt").filter({ hasText: "사례별 근거·한계" }).locator("+ dd")).toHaveText(entry.notes);
  await page.goto("/research/");
  const categories = page.locator("#typology-axes .axis").filter({ has: page.locator("h3", { hasText: "national category coverage" }) });
  for (const item of published.coverage_by_category) await expect(categories).toContainText(`${item.category} ${item.count}건`);
});
