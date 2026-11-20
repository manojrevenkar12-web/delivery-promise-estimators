import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

async function noViolations(page: Page) {
  const r = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
}

test("the promise view shows where every order ended up and every design", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Of every 1,000 orders");
  await expect(page.getByRole("img", { name: /^Platform: .* within 120 minutes/ }).first()).toBeVisible();
  await expect(page.locator("tbody tr")).toHaveCount(12);
  await expect(page.getByText(/Gate (passed|not passed)|Not run yet/).first()).toBeVisible();
  await noViolations(page);
});

test("one day switches metric and reads values on hover", async ({ page }) => {
  await page.goto("/#/day");
  await page.getByRole("button", { name: "Orders turned away" }).click();
  await expect(page.getByRole("button", { name: "Orders turned away" })).toHaveAttribute("aria-pressed", "true");
  const chart = page.getByRole("img", { name: /Orders turned away through the day/ });
  const box = (await chart.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.45, box.y + box.height * 0.5);
  await expect(page.locator("figcaption")).toContainText(/\d\d:\d\d/);
  await noViolations(page);
});

test("what to build ranks the options and shows the percentile table", async ({ page }) => {
  await page.goto("/#/decisions");
  await expect(page.getByRole("heading", { name: "What to build first" })).toBeVisible();
  expect(await page.locator("ol > li").count()).toBeGreaterThan(5);
  await expect(page.getByRole("table", { name: /Percentile pairs/ })).toBeVisible();
  await expect(page.getByText("· served")).toBeVisible();
  await noViolations(page);
});

test("warehouse compares picking designs", async ({ page }) => {
  await page.goto("/#/warehouse");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Picking:");
  await expect(page.locator("main li")).toHaveCount(6);
  await noViolations(page);
});

test("an API failure offers a retry", async ({ page }) => {
  await page.route("**/api/results", (r) => r.fulfill({ status: 503, body: JSON.stringify({ detail: "warming up" }) }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("warming up");
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
});
