import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useApp } from "./store";

function jsonResponse(body: unknown): Response {
  return {
    ok: true,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

describe("run resume store flow", () => {
  beforeEach(() => {
    useApp.setState({
      stage: "setup",
      runId: null,
      benchProgress: {},
      finalResult: null,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("selects the newest active run and restores running progress", async () => {
    const fetchMock = vi.fn(async (input: unknown) => {
      const url = String(input);
      if (url === "/api/runs") {
        return jsonResponse([
          {
            run_id: "older",
            status: "running",
            started_at: "2026-05-03T00:00:00Z",
            finished_at: null,
            model: "m",
            base_url: "https://api.test/v1",
          },
          {
            run_id: "done",
            status: "completed",
            started_at: "2026-05-03T00:02:00Z",
            finished_at: "2026-05-03T00:03:00Z",
            model: "m",
            base_url: "https://api.test/v1",
          },
          {
            run_id: "newer",
            status: "running",
            started_at: "2026-05-03T00:01:00Z",
            finished_at: null,
            model: "m",
            base_url: "https://api.test/v1",
          },
        ]);
      }
      if (url === "/api/runs/newer") {
        return jsonResponse({
          run_id: "newer",
          status: "running",
          started_at: "2026-05-03T00:01:00Z",
          finished_at: null,
          messages: [
            {
              role: "system",
              content: "mmlu: 2/5",
              created_at: "2026-05-03T00:01:10Z",
              metadata: {
                type: "progress",
                bench: "mmlu",
                current: 2,
                total: 5,
                running_accuracy: 0.5,
                thinking_used: false,
              },
            },
          ],
          result: null,
        });
      }
      throw new Error(`unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const resumed = await useApp.getState().resumeActiveRun();

    expect(resumed).toBe(true);
    expect(useApp.getState().runId).toBe("newer");
    expect(useApp.getState().stage).toBe("running");
    expect(useApp.getState().benchProgress.mmlu.current).toBe(2);
    expect(useApp.getState().benchProgress.mmlu.total).toBe(5);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/runs/newer",
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });
});
