import { test, expect } from "@playwright/test";

/**
 * Smoke flow: Setup → Running → Results.
 *
 * The FastAPI server only serves the built SPA here. Browser-side /api/*
 * calls are mocked so the flow is deterministic and never reaches a real
 * model gateway.
 */
test("setup → run → results renders the matrix", async ({ page }) => {
  const result = {
    schema_version: 1,
    run_id: "evalbox-e2e",
    started_at: "2026-05-03T00:00:00Z",
    finished_at: "2026-05-03T00:00:01Z",
    seed: 42,
    provider: { adapter: "chat_completions", base_url: "https://fake.test/v1", model: "fake-model" },
    sampling: { concurrency: 2 },
    thinking: { mode: "off", used: false },
    capability: {},
    strict_deterministic: false,
    strict_failures: false,
    benchmarks: [{
      name: "mmlu",
      samples: 2,
      accuracy: 0.5,
      accuracy_ci95: [0.1, 0.9],
      latency_ms: { p50: 100, p95: 120 },
      tokens: { prompt: 20, completion: 2, reasoning: 0, cached_prompt: 0 },
      cost_usd_estimated: 0.001,
      thinking_used: false,
      denominator_policy: "lenient",
      cache_hits: 0,
    }],
    totals: {
      accuracy_macro: 0.5,
      tokens: { prompt: 20, completion: 2, reasoning: 0, cached_prompt: 0 },
      cost_usd_estimated: 0.001,
    },
    messages: [
      {
        role: "system",
        content: "run started · model=fake-model-alt · 1 benchmark(s)",
        created_at: "2026-05-03T00:00:00Z",
        metadata: { type: "status", phase: "started" },
      },
      {
        role: "assistant",
        content: "mmlu: completed · acc=0.5000 · cost=$0.0010",
        created_at: "2026-05-03T00:00:01Z",
        metadata: { type: "result", bench: "mmlu" },
      },
    ],
  };

  await page.route("**/api/defaults", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        base_url: "https://fake.test/v1",
        model: "fake-model",
        adapter: "chat_completions",
        profile: null,
        thinking: null,
        reasoning_effort: null,
        concurrency: null,
        rpm: null,
        tpm: null,
        max_cost_usd: null,
        accept_code_exec: false,
        no_cache: false,
        strict_failures: false,
        no_thinking_rerun: false,
        prompt_cache_aware: false,
        drop_params: null,
        api_key_env: "OPENAI_API_KEY",
        has_api_key: false,
        detected_api_key_envs: [],
        api_keys: {},
      }),
    });
  });
  await page.route("**/api/benchmarks", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { name: "mmlu", quick_size: 200, is_code_bench: false, category: "knowledge", license: "MIT" },
      ]),
    });
  });
  await page.route("**/api/models", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { id: "fake-model", owned_by: "test", created: 0 },
        { id: "fake-model-alt", owned_by: "test", created: 0 },
      ]),
    });
  });
  await page.route("**/api/connection/test", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ok: true,
        adapter: "chat_completions",
        model_listed: true,
        model_count: 1,
        latency_ms: 50,
        finish_reason: "stop",
        thinking_observed: false,
        text_preview: "OK",
        capability: {
          accepts_temperature: true,
          accepts_top_p: true,
          accepts_top_k: false,
          accepts_seed: true,
          accepts_reasoning_effort: false,
          use_max_completion_tokens: false,
          notes: "",
        },
        learned_drop_params: [],
        error: null,
      }),
    });
  });
  await page.route("**/api/pricing/estimate", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        est_prompt_tokens: 1600,
        est_completion_tokens: 10,
        est_reasoning_tokens: 0,
        est_cost_usd: 0.01,
        est_seconds: 2,
      }),
    });
  });
  await page.route("**/api/runs", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ run_id: "evalbox-e2e", status: "queued" }),
    });
  });
  await page.route("**/api/runs/evalbox-e2e/events", (route) => {
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        "event: progress",
        "data: {\"type\":\"progress\",\"phase\":\"eval\",\"bench\":\"mmlu\",\"current\":2,\"total\":2,\"running_accuracy\":0.5,\"thinking_used\":false,\"message\":\"mmlu: 2/2 · acc=0.5000\",\"created_at\":\"2026-05-03T00:00:00Z\"}",
        "",
        "event: result",
        "data: {\"type\":\"result\",\"bench\":\"mmlu\",\"data\":{\"name\":\"mmlu\",\"samples\":2,\"accuracy\":0.5,\"cost_usd\":0.001},\"message\":\"mmlu: completed · acc=0.5000 · cost=$0.0010\",\"created_at\":\"2026-05-03T00:00:01Z\"}",
        "",
        "event: done",
        "data: {\"type\":\"done\",\"summary\":{\"run_id\":\"evalbox-e2e\"},\"message\":\"run completed · 1 benchmark(s)\",\"created_at\":\"2026-05-03T00:00:01Z\"}",
        "",
        "",
      ].join("\n"),
    });
  });
  await page.route("**/api/runs/evalbox-e2e", (route) => {
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        run_id: "evalbox-e2e",
        status: "completed",
        started_at: result.started_at,
        finished_at: result.finished_at,
        messages: result.messages,
        result,
      }),
    });
  });

  await page.goto("/");
  await page.waitForTimeout(1000);

  await expect(page.getByText(/Available models|조회된 모델/)).toBeVisible();
  await page.getByRole("button", { name: /fake-model-alt/ }).click();
  await expect(page.getByPlaceholder("gpt-4o-mini")).toHaveValue("fake-model-alt");

  // Test connection
  await page.getByRole("button", { name: /Test connection|연결 확인/ }).click();
  await expect(page.getByText(/Connected|연결됨/)).toBeVisible({ timeout: 15_000 });

  // Run
  await page.getByRole("button", { name: /Run benchmarks|벤치마크 실행/ }).click();

  // We're on the Running page now. Wait for transition to Results.
  await expect(page.getByRole("button", { name: /New run|새 실행/ })).toBeVisible({
    timeout: 60_000,
  });

  // Results matrix shows the benchmark we ran.
  await expect(page.getByText(/^mmlu$/)).toBeVisible();
  await page.getByRole("button", { name: "Messages" }).click();
  await expect(page.getByText(/mmlu: completed/)).toBeVisible();
});
