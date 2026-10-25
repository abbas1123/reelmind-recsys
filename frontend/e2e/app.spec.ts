import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

// These tests check real user flows through the UI. They are NOT evidence that the ML is
// correct — that is verified separately by the backend pytest suite (unit + real_data).

const API = "http://127.0.0.1:8010/api";
const unique = (p: string) => `${p} ${Date.now().toString(36)}`;

async function createProfile(request: APIRequestContext, name: string): Promise<number> {
  const res = await request.post(`${API}/users`, { data: { display_name: name } });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).id;
}

async function useProfile(page: Page, id: number) {
  await page.addInitScript((pid) => localStorage.setItem("reelmind.profileId", String(pid)), id);
}

test("new user: onboarding -> cold start -> ratings change recommendations", async ({ page }) => {
  const name = unique("E2E Aysel");
  await page.goto("/");
  await page.getByTestId("new-profile-name").fill(name);
  await page.getByTestId("create-profile").click();
  await expect(page).toHaveURL(/\/onboarding$/);

  for (const g of ["Animation", "Children's", "Comedy"]) await page.getByTestId(`genre-${g}`).click();
  await page.getByTestId("genres-continue").click();

  const items = page.getByTestId("onboarding-item");
  await expect(items.first()).toBeVisible();
  for (let i = 0; i < 3; i++) {
    await items.nth(i).getByRole("radio", { name: "5 stars" }).click();
  }
  await expect(page.getByTestId("rated-count")).toHaveText("3 rated");
  await page.getByTestId("onboarding-finish").click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByTestId("current-profile")).toHaveText(name);
  await expect(page.getByTestId("bucket")).toContainText("light");
  await expect(page.getByTestId("bucket")).toContainText("History: 3 ratings");
  const top = page.getByTestId("section-top_picks").getByTestId("movie-card");
  await expect(top).toHaveCount(20);
  await expect(page.getByTestId("section-because_you_liked")).toBeVisible();

  // Back on the profile picker the new profile and its ratings are listed (the list used to come from the cache).
  await page.getByRole("button", { name: /Switch profile/ }).click();
  await expect(page.getByTestId("profile-tile").filter({ hasText: name })).toContainText("3 rated");
});

test("search, open a movie, rate and favorite it, see it in My list", async ({ page, request }) => {
  const id = await createProfile(request, unique("E2E search"));
  await useProfile(page, id);
  await page.goto("/me"); // cache the empty lists first: they must refresh after client-side navigation
  await page.getByRole("link", { name: "Discover", exact: true }).click();
  await page.getByTestId("search-input").fill("toy story");
  await expect(page.getByTestId("search-summary")).toContainText("matches");
  const first = page.getByTestId("movie-card").first();
  await expect(first).toContainText("Toy Story");
  await first.getByRole("link").first().click();

  await expect(page.getByTestId("movie-title")).toHaveText(/Toy Story/);
  await page.getByRole("radiogroup", { name: "Your rating" }).getByRole("radio", { name: "4 stars" }).click();
  await expect(page.getByRole("radio", { name: "4 stars" })).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("favorite-button").click();
  await expect(page.getByTestId("favorite-button")).toContainText("In your list");
  await expect(page.getByTestId("similar-row").getByTestId("movie-card").first()).toBeVisible();

  await page.getByRole("link", { name: "My list", exact: true }).click();
  await expect(page.getByTestId("favorites-grid")).toContainText("Toy Story");
  await page.getByRole("tab", { name: /Ratings/ }).click();
  await expect(page.getByRole("radiogroup", { name: /Your rating for Toy Story/ })).toBeVisible();
  await page.getByRole("tab", { name: /History/ }).click();
  await expect(page.getByRole("tabpanel")).toContainText("rate 4★");

  // One visit to the film page is one "view" in the history (React StrictMode used to log it twice).
  const history = await (await request.get(`${API}/users/${id}/history`)).json();
  expect(history.filter((h: { kind: string }) => h.kind === "view")).toHaveLength(1);
});

test("explore as a real MovieLens user gets warm recommendations", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("ml-user-id").fill("42");
  await page.getByTestId("open-ml-user").click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByTestId("bucket")).toContainText("warm");
  await expect(page.getByTestId("section-top_picks").getByTestId("movie-card")).toHaveCount(20);
  await expect(page.getByTestId("section-top_picks").getByTestId("rec-reason").first()).toBeVisible();
});

test("model dashboard shows the measured numbers from the report", async ({ page, request }) => {
  const report = await (await request.get(`${API}/model/evaluation`)).json();
  const selected: string = report.selection.selected;
  const metric: string = report.protocol.primary_metric;
  const testValue: number = report.models[selected].test.metrics[metric];

  await page.goto("/models");
  await expect(page.getByTestId("stat-tiles")).toContainText(selected);
  await expect(page.getByTestId(`test-${selected}`)).toHaveText(testValue.toFixed(4));
  await expect(page.getByTestId("metrics-table").locator("tbody tr")).toHaveCount(report.selection.ranking.length);
  await expect(page.getByTestId("ndcg-chart").locator(".recharts-bar-rectangle").first()).toBeVisible();
});

test("semantic search uses the local embedding model", async ({ page, request }) => {
  const health = await (await request.get(`${API}/health`)).json();
  test.skip(!health.semantic_search, "embedding model not cached");
  await page.goto("/discover");
  await page.getByTestId("mode-semantic").click();
  await page.getByTestId("search-input").fill("animated toys come to life");
  await expect(page.getByTestId("search-summary")).toContainText("semantic");
  await expect(page.getByTestId("movie-card").filter({ hasText: "Toy Story" }).first()).toBeVisible();
});
