import { caseSite } from "../src/record-scope.js";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const fixture = JSON.parse(await readFile(new URL("./fixtures/ac01-tasks.v1.json", import.meta.url), "utf8"));
const published = JSON.parse(await readFile(new URL("../data/site.v3.json", import.meta.url), "utf8"));
const cases = caseSite(published);
const publicCount = cases.entries.length;
const statusCount = status => cases.entries.filter(e=>e.operational_status===status).length;
const typeCount = type => cases.entries.filter(e=>e.resource_type===type).length;
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

async function openFilterPanel(page) {
  const trigger = page.locator("#mobile-filter-trigger");
  if (await trigger.isVisible()) await trigger.click();
}

async function showList(page) {
  if (await page.locator("#show-list").isVisible()) await page.locator("#show-list").click();
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
      expect((await firstSource.boundingBox()).y).toBeLessThan(page.viewportSize().height);
      await expect(page.locator("#detail-content h4").first()).toContainText("공개 자료");
      await expect(page.locator("#detail-content dt").filter({ hasText: "출처 ID" }).locator("+ dd")).toContainText("source-");
      await expect(page.locator("#detail-content dt").filter({ hasText: "상태 검토 사유" }).locator("+ dd")).not.toBeEmpty();
      expect(Date.now() - started).toBeLessThan(30_000);
    });
  }
});

test("콜드 홈은 검색과 지도를 우선 제공하고 목록 전환과 비교 지연 렌더링을 유지한다", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect(page.locator("#result-visible")).toHaveText("12개 표시");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(12);
  await expect(page.locator("#national-map .national-region")).toHaveCount(17);
  await expect(page.locator("#map-context")).toBeVisible();
  await expect(page.locator("#compare-matrix")).toBeEmpty();
  await showList(page);
  await expect(page.locator("#load-more")).toBeVisible();
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
  await openFilterPanel(page);
  await page.locator('[data-category-chip="교육청대회·사업"]').click();
  await openAdvancedFilters(page);
  await page.locator("#scope-filter").selectOption("regional");
  await page.locator("#filter-panel-result").click();
  await expect(page.locator("#active-filters .active-filter")).toHaveCount(3);
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({
    region: "busan",
    category: "교육청대회·사업",
    scope: "regional",
  });
  await expect(page.locator("#mobile-filter-count")).toHaveText("2");
  await openFilterPanel(page);
  await page.locator("#reset-filters").click();
  await page.locator("#filter-panel-result").click();
  await expect(page.locator("#active-filters")).toBeEmpty();
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect.poll(() => page.evaluate(() => location.search)).toBe("");
});

test("필터 시트는 미리보기 후 적용하며 취소하면 기존 결과와 포커스를 보존한다", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/index.html");
  await page.locator("#mobile-filter-trigger").click();
  await expect(page.locator("#filter-panel")).toBeVisible();
  expect(await page.locator("#filter-panel").evaluate((dialog) => dialog.matches(":modal"))).toBe(true);
  await page.locator('[data-category-chip="지자체정책·조례"]').click();
  await expect(page.locator("#filter-panel-result")).toHaveText(`${cases.entries.filter(entry => entry.category === "지자체정책·조례").length}건 결과 보기`);
  await page.keyboard.press("Escape");
  await expect(page.locator("#filter-panel")).toBeHidden();
  await expect(page.locator("#mobile-filter-trigger")).toBeFocused();
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect(page.locator("#results-surface")).toBeHidden();
  expect(new URL(page.url()).search).toBe("");
  await openFilterPanel(page);
  await expect(page.locator('[data-category-chip="지자체정책·조례"]')).toHaveAttribute("aria-pressed", "false");
  await page.locator('[data-category-chip="지자체정책·조례"]').click();
  await page.locator("#filter-panel-result").click();
  await expect(page.locator("#result-count")).toHaveText(`${cases.entries.filter(entry => entry.category === "지자체정책·조례").length}건`);
  await expect(page.locator("#results-heading")).toBeFocused();
});

test("지역 비교 탭은 공식 시도 순서를 사용하고 선택을 필터된 목록으로 연결한다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator("#compare-tab").click();
  await expect.poll(() => page.evaluate(() => Object.fromEntries(new URLSearchParams(location.search)))).toEqual({ view: "compare" });
  await expect(page.locator(".matrix-chart-row")).toHaveCount(17);
  await expect(page.locator(".matrix-chart-row").first()).toHaveAttribute("data-region", "seoul");
  await expect(page.locator("[data-matrix-sort]")).toHaveCount(0);
  await expect(page.locator(".matrix-chart-summary")).toHaveText(`${publicCount}건 · 17개 시·도 · ${new Set(cases.entries.map(entry => entry.category)).size}개 유형`);
  const matrix = page.locator("#compare-matrix table");
  await expect(matrix.locator("tbody tr")).toHaveCount(17);
  await expect(matrix.locator("tfoot td").last()).toHaveText(String(publicCount));
  await expect(page.locator(".matrix-caveat")).toContainText("실제 활동 규모나 순위를 나타내지 않습니다");
  await page.locator('#compare-matrix .matrix-legend button[data-category="지자체정책·조례"]').click();
  await expect(page.locator("#browse-tab")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#result-count")).toHaveText(`${cases.entries.filter(entry => entry.category === "지자체정책·조례").length}건`);
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
  const isMobile = await page.evaluate(() => innerWidth <= 1023);
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
  await showList(page);
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

test("점진 노출로 초기 길이를 제한하면서 집계 대상 사례 전부 도달할 수 있다", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator("#result-list .entry-card")).toHaveCount(12);
  await showList(page);
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

test("desktop and compact layouts expose usable maps, result lists and 44px alternatives without overflow", async ({ page }) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }, { width: 1023, height: 768 }, { width: 720, height: 844 }, { width: 390, height: 664 }, { width: 320, height: 664 }]) {
    await page.setViewportSize(viewport);
    await page.goto("/index.html");
    await expect(page.locator(".national-region")).toHaveCount(17);
    await expect(page.locator("#map-context")).toBeVisible();
    const layout = await page.evaluate(async () => {
      await document.fonts.ready;
      const map = document.querySelector("#national-map").getBoundingClientRect();
      const stage = document.querySelector(".national-map-stage").getBoundingClientRect();
      const controls = [...document.querySelectorAll("button,input,select,summary")].filter(e => e.getClientRects().length);
      return {
        overflow: document.documentElement.scrollWidth - innerWidth,
        mapInView: map.top < innerHeight - 120,
        mapContained: map.bottom <= stage.bottom + 1,
        searchInView: document.querySelector("#entry-search").getBoundingClientRect().bottom < innerHeight,
        minControl: Math.min(...controls.map(e => e.getBoundingClientRect().height)),
      };
    });
    expect(layout).toMatchObject({ overflow: 0, mapInView: true, mapContained: true, searchInView: true });
    expect(layout.minControl).toBeGreaterThanOrEqual(44);
    await showList(page);
    await expect(page.locator(".entry-card").first()).toBeVisible();
    expect((await page.locator(".entry-card").first().boundingBox()).y).toBeLessThan(viewport.height);
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
  await showList(page);
  await page.locator(".entry-card").first().click();
  results = await new AxeBuilder({ page }).include("#detail-panel").analyze();
  expect(seriousOrCritical(results.violations)).toEqual([]);

  await page.goto("/research/");
  await expect(page.locator("#dataset-facts dd")).toContainText([
    "v3",
    `${publicCount}건`,
    `${published.entries.length}개 레코드 · 보조 참고 ${published.entries.length-publicCount}개는 사례 집계 제외`,
    "17개 시·도",
    `${cases.sources.length}개 source ref`,
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
  await openFilterPanel(page);
  await openAdvancedFilters(page);
  await page.locator("#review-state-filter").selectOption("confirmed");
  await expect(page.locator("#result-count")).toHaveText("0건");
  await page.locator("#reset-filters").click();
  await page.locator("#filter-panel-result").click();
  await expect(page.locator("#review-state-filter")).toHaveValue("");
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect.poll(() => page.evaluate(() => location.search)).toBe("");
  await page.goto("/index.html?entry=busan-016");
  const entry = published.entries.find(item => item.id === "busan-016");
  await page.locator(".detail-limits summary").click();
  await expect(page.locator("#detail-content dt").filter({ hasText: "사례별 근거·한계" }).locator("+ dd")).toHaveText(entry.notes);
  await page.goto("/research/");
  const categories = page.locator("#typology-axes .axis").filter({ has: page.locator("h3", { hasText: "national category coverage" }) });
  for (const item of cases.coverage_by_category) await expect(categories).toContainText(`${item.category} ${item.count}건`);
});

test("지역 보조 참고 자료는 사례 검색과 집계에서 제외하고 연구 부록에 보존한다", async ({ page }) => {
  await page.goto("/index.html");
  await page.locator("#entry-search").fill("대구광역시 학교 이스포츠 클럽 강사 지원 참여 거점");
  await expect(page.locator("#result-count")).toHaveText("0건");
  await page.goto("/research/");
  await expect(page.locator("#reference-records > li")).toHaveCount(published.entries.length - publicCount);
  await expect(page.locator("#case-scope-summary")).toContainText(`${publicCount}개 사례만`);
  await expect(page.locator("#reference-records")).toContainText("동일 행사 사례: national-audit-jeonbuk-gunsan-amateur-esports-2026");
  await expect(page.locator("#typology-axes")).toContainText(`지도 적격 ${cases.entries.filter(entry => !entry.off_map).length}건`);
  await expect(page.locator("#typology-axes")).toContainText(`좌표 미확인 ${cases.entries.filter(entry => entry.scope === "regional" && entry.off_map).length}건`);
});

test("map filters use every condition except region and preserve the scale and selected region", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/index.html?region=busan");
  const legend = await page.locator("#map-legend").textContent();
  await openFilterPanel(page);
  await page.locator('[data-category-chip="교육청대회·사업"]').click();
  await page.locator("#filter-panel-result").click();
  for (const region of cases.regions) {
    const count = cases.entries.filter(e => e.region_id === region.id && e.category === "교육청대회·사업").length;
    await expect(page.locator(`#national-map [data-region="${region.id}"]`)).toHaveAttribute("aria-label", `${region.name}, 현재 조건의 공개자료 ${count}건`);
    await expect(page.locator(`[data-region-shortcut="${region.id}"]`)).toContainText(String(count));
    if (count === 0) await expect(page.locator(`#national-map [data-region="${region.id}"]`)).toHaveAttribute("data-density", "0");
  }
  await expect(page.locator("#map-legend")).toHaveText(legend);
  await expect(page.locator('#national-map [data-region="busan"]')).toHaveAttribute("aria-pressed", "true");
  const selectedPaintMatchesLegend = () => page.locator('#national-map [data-region="busan"]').evaluate((region) => {
    const paint = getComputedStyle(region);
    const swatch = document.querySelector(`#map-legend [data-density="${region.dataset.density}"]`);
    return paint.fill === getComputedStyle(swatch).backgroundColor && paint.strokeDasharray !== "none";
  });
  // Selection must remain visible without replacing the data's density color.
  await expect.poll(selectedPaintMatchesLegend).toBe(true);
  const expected = cases.entries.filter(e => e.region_id === "busan" && e.category === "교육청대회·사업").length;
  await expect(page.locator("#result-count")).toHaveText(`${expected}건`);
  await page.locator("#entry-search").fill("unmatched-query");
  await expect(page.locator('#national-map [data-region="busan"]')).toHaveAttribute("data-density", "0");
  await expect.poll(selectedPaintMatchesLegend).toBe(true);
  await expect(page.locator("#map-readout")).toContainText("현재 조건에 맞는 공개자료 없음");
  await page.locator('[data-empty-clear="query"]').click();
  await expect(page.locator("#result-count")).toHaveText(`${expected}건`);
  await openFilterPanel(page);
  await page.locator('[data-category-chip="교육청대회·사업"]').click();
  await page.locator("#filter-panel-result").click();
  await expect(page.locator("#result-count")).toHaveText("27건");
});

test("compact map to list to detail takes two activations before the original source link", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 664 });
  await page.goto("/index.html");
  await page.locator('#national-map [data-region-label-target="busan"]').click();
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-pane", "list");
  await expect(page.locator("#results-heading")).toBeFocused();
  await page.locator(".entry-card").first().click();
  await expect(page.locator(".source-links a").first()).toHaveAttribute("href", fixture.tasks[0].expected_source_url);
  await page.locator("#detail-back").click();
  await expect(page.locator(".entry-card").first()).toBeFocused();
  await page.locator("#show-map").click();
  await expect(page.locator('#national-map [data-region="busan"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#national-map-heading")).toBeFocused();
  await page.reload();
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-pane", "list");
  await page.locator("#show-map").click();
  await expect(page.locator("[data-region-label]")).toHaveCount(17);
  await page.goto("/index.html");
  await page.locator('#national-map [data-region="seoul"]').click();
  await expect(page).toHaveURL(/region=seoul/);
  await page.goBack();
  await expect(page).not.toHaveURL(/region=/);
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-pane", "map");
  await page.goForward();
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-pane", "list");
});

test("desktop details retain map and restore a later result's scroll and focus", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/index.html?region=busan");
  await page.locator("#load-more").click();
  const card = page.locator("#result-list .entry-card").nth(16);
  await card.focus();
  const before = await page.locator("#browse-panel").evaluate(el => el.scrollTop);
  await card.click();
  await expect(page.locator("#map-context")).toBeVisible();
  await expect(page.locator("#browse-panel")).toBeHidden();
  await page.locator("#detail-back").click();
  await expect(card).toBeFocused();
  await expect.poll(() => page.locator("#browse-panel").evaluate(el => el.scrollTop)).toBe(before);
  await card.click();
  await page.goBack();
  await expect(card).toBeFocused();
  await expect(page.locator("#result-list .entry-card")).toHaveCount(24);
});

test("map and public-data failures offer usable recovery in compact view", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 664 });
  await page.route("**/data/national-map.v1.json", route => route.abort());
  await page.goto("/index.html");
  await expect(page.locator("#map-error")).toBeVisible();
  await page.locator('[data-region-shortcut="jeju"]').click();
  await expect(page.locator("#results-heading")).toHaveText("제주특별자치도 사례");
  await page.route(dataUrl, route => route.abort());
  await page.reload();
  await expect(page.locator(".data-error")).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 불러오기" })).toBeVisible();
  await page.unroute(dataUrl);
  await page.getByRole("button", { name: "다시 불러오기" }).click();
  await expect(page.locator("#result-count")).toHaveText(`${cases.entries.filter(entry => entry.region_id === "jeju").length}건`);
});

test("keyboard map selection and rapid search plus region selection preserve both filters", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/index.html");
  const seoul = page.locator('#national-map [data-region="seoul"]');
  await seoul.focus();
  await page.keyboard.press("Enter");
  await expect(seoul).toHaveAttribute("aria-pressed", "true");
  await page.locator("#entry-search").fill("부산");
  await page.locator("#region-select").selectOption("busan");
  await expect(page.locator("#entry-search")).toHaveValue("부산");
  await expect.poll(() => page.evaluate(() => new URLSearchParams(location.search).get("q"))).toBe("부산");
});

test("clearing a query cancels a pending search rather than reviving it", async ({ page }) => {
  await page.goto("/index.html?q=부산");
  await expect(page.locator('[data-clear-filter="query"]')).toBeVisible();
  await page.clock.install();
  await page.clock.pauseAt(new Date(Date.now() + 1000));
  await page.locator("#entry-search").fill("서울");
  await page.locator('[data-clear-filter="query"]').click();
  await page.clock.runFor(300);
  await expect(page.locator("#entry-search")).toHaveValue("");
  await expect(page.locator("#result-count")).toHaveText(`${publicCount}건`);
  await expect.poll(() => page.evaluate(() => new URLSearchParams(location.search).has("q"))).toBe(false);
});


test("fullscreen canvas fits all map geometry and labels before and after the desktop drawer opens", async ({ page }, testInfo) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1024, height: 768 }]) {
    await page.setViewportSize(viewport);
    await page.goto("/index.html");
    await expect(page.locator(".national-region")).toHaveCount(17);
    await expect(page.locator("#results-surface")).toBeHidden();
    const originalWidth = (await page.locator(".national-map-stage").boundingBox()).width;
    for (const open of [false, true]) {
      if (open) await page.locator('[data-region-label-target="busan"]').click();
      const geometry = await page.evaluate(async () => {
        await document.fonts.ready;
        const workspace = document.querySelector("#workspace").getBoundingClientRect();
        const header = document.querySelector(".site-shell-header").getBoundingClientRect();
        const map = document.querySelector("#national-map");
        const stage = map.getBoundingClientRect();
        const labelsAndRegions = [...map.querySelectorAll("path,text,line,rect")].map(el => el.getBoundingClientRect());
        return {
          fillsViewport: Math.abs(workspace.bottom - innerHeight) <= 2 && Math.abs(workspace.top - header.bottom) <= 2,
          allContained: labelsAndRegions.every(rect => rect.left >= stage.left - 1 && rect.right <= stage.right + 1 && rect.top >= stage.top - 1 && rect.bottom <= stage.bottom + 1),
          overflow: document.documentElement.scrollWidth - innerWidth,
        };
      });
      expect(geometry).toEqual({ fillsViewport: true, allContained: true, overflow: 0 });
    }
    expect((await page.locator(".national-map-stage").boundingBox()).width).toBeLessThan(originalWidth - 390);
    expect((await page.locator("#results-surface").boundingBox()).width).toBe(400);
    await page.screenshot({ path: testInfo.outputPath(`desktop-drawer-${viewport.width}.png`) });
    await page.locator("#show-map").click();
    await expect(page.locator("#results-surface")).toBeHidden();
    await expect(page).toHaveURL(/region=busan/);
    await expect(page.locator("#region-select")).toHaveValue("busan");
    await expect(page.locator("#national-map-heading")).toBeFocused();
    await page.reload();
    await expect(page.locator("#results-surface")).toBeVisible();
  }
});

test("mobile sheet keeps the map interactive, expands, restores detail position and survives rotation", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 664 });
  await page.goto("/index.html");
  await expect(page.locator(".national-region")).toHaveCount(17);
  await page.screenshot({ path: testInfo.outputPath("mobile-map.png") });
  await page.locator('[data-region-label-target="busan"]').click();
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-panel", "list");
  await expect(page.locator("#map-context")).toBeVisible();
  const panel = await page.locator("#results-surface").boundingBox();
  expect(panel.height).toBeGreaterThan(290);
  expect(panel.y + panel.height).toBeLessThanOrEqual(664);
  expect((await page.locator(".entry-card").first().boundingBox()).y).toBeLessThan(panel.y + panel.height - 60);
  await page.screenshot({ path: testInfo.outputPath("mobile-sheet.png") });
  await page.locator('[data-region-label-target="seoul"]').click();
  await expect(page.locator("#region-select")).toHaveValue("seoul");
  await page.locator("#expand-results").click();
  await expect(page.locator("#map-context")).toBeHidden();
  await expect(page.locator("#expand-results")).toHaveAttribute("aria-expanded", "true");
  const card = page.locator(".entry-card").first();
  await card.click();
  await page.locator("#detail-back").click();
  await expect(card).toBeFocused();
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-panel", "expanded");
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.locator("#map-context")).toBeVisible();
  await expect(page.locator("#region-select")).toHaveValue("seoul");
  await page.setViewportSize({ width: 390, height: 664 });
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-panel", "expanded");
  await page.locator("#expand-results").click();
  await expect(page.locator("#map-context")).toBeVisible();
  await page.setViewportSize({ width: 720, height: 390 });
  await expect(page.locator("#explorer-layout")).toHaveAttribute("data-panel", "expanded");
  await page.locator("#expand-results").click();
  await expect(page.locator("#map-context")).toBeVisible();
  await expect(page.locator("#results-surface")).toBeHidden();
});

test("desktop filters are transactional and page summaries stay reachable outside the scrollable drawer", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/index.html?region=busan");
  await openFilterPanel(page);
  await page.locator("#reset-filters").click();
  await page.locator("#filter-panel-cancel").click();
  await expect(page.locator("#region-select")).toHaveValue("busan");
  await expect(page).toHaveURL(/region=busan/);
  await page.locator("#load-more").click();
  const pageBefore = await page.evaluate(() => scrollY);
  await page.locator(".entry-card").nth(20).focus();
  expect(await page.evaluate(() => scrollY)).toBe(pageBefore);
  expect(await page.locator("#browse-panel").evaluate(el => el.scrollTop)).toBeGreaterThan(0);
  await page.locator('.map-footer a[href="#snapshot"]').click();
  await expect(page.locator("#snapshot-heading")).toBeInViewport();
  await page.locator("[data-feature-entry]").first().click();
  await expect(page.locator("#detail-panel")).toBeInViewport();
  await expect(page.locator("#detail-heading")).toBeFocused();
  await page.locator("#show-map").click();
  await expect(page.locator("#results-surface")).toBeHidden();
  await expect(page).not.toHaveURL(/entry=/);
});
