import { test, expect } from "@playwright/test";

/**
 * Smoke flow: Setup → Running → Results.
 *
 * Uses the deterministic in-process mock backend that ships with the build:
 * we point the SPA at a fake endpoint and intercept /v1/chat/completions
 * via Playwright's request routing. The point of the test is wiring, not
 * any specific accuracy.
 */
test("setup → run → results renders the matrix", async ({ page }) => {
  // Intercept the model's chat-completions route. We don't know the host the
  // user types, so we match any *.test/v1/chat/completions URL.
  await page.route(/\/v1\/chat\/completions$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "x",
        model: "fake-model",
        choices: [
          {
            index: 0,
            finish_reason: "stop",
            message: { role: "assistant", content: "B" },
          },
        ],
        usage: { prompt_tokens: 10, completion_tokens: 1, total_tokens: 11 },
      }),
    });
  });
  await page.route(/\/v1\/models$/, (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data: [{ id: "fake-model", owned_by: "test" }] }),
    });
  });

  await page.goto("/");

  // Setup: fill connection. The SPA's default base_url is OpenAI public — we
  // overwrite to a fake host so our request routes match.
  await page.getByPlaceholder("https://api.openai.com/v1").fill("https://fake.test/v1");
  await page.getByPlaceholder("gpt-4o-mini").fill("fake-model");

  // Test connection
  await page.getByRole("button", { name: /Test connection|연결 확인/ }).click();
  await expect(page.getByText(/Connected|연결됨/)).toBeVisible({ timeout: 15_000 });

  // Pick a benchmark — mmlu is checked by default in our store.
  // Force samples=2 so the run finishes quickly.
  const samplesInput = page.locator('input[type="number"]').first();
  await samplesInput.fill("2");

  // Run
  await page.getByRole("button", { name: /Run benchmarks|벤치마크 실행/ }).click();

  // We're on the Running page now. Wait for transition to Results.
  await expect(page.getByRole("button", { name: /New run|새 실행/ })).toBeVisible({
    timeout: 60_000,
  });

  // Results matrix shows the benchmark we ran.
  await expect(page.getByText(/^mmlu$/)).toBeVisible();
});
