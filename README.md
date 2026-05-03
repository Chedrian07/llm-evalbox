# llm-evalbox

> A lightweight LLM evaluation tool for OpenAI-compatible endpoints
> (`/v1/chat/completions`, `/v1/responses`). Bring your own `BASE_URL` +
> `MODEL_NAME` and run academic benchmarks (MMLU / GSM8K / HumanEval / MBPP /
> LiveCodeBench / TruthfulQA / HellaSwag / Winogrande / KMMLU / CMMLU / JMMLU /
> BBQ / SafetyBench / …) from the CLI or a local web UI.

## Quick start

```bash
git clone https://github.com/Chedrian07/llm-evalbox && cd llm-evalbox
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"            # add ".[web]" too once you want `evalbox web`

cp .env.example .env               # set EVALBOX_BASE_URL / EVALBOX_MODEL / OPENAI_API_KEY
evalbox doctor                     # connection + capability probe
evalbox run --bench mmlu --samples 50
```

Datasets are bundled (~62 MB, MIT/Apache/CC). No network fetch on first run.

## What's in scope

- Provider-agnostic core. Adapters absorb Chat Completions vs Responses
  shape differences and per-model capability quirks (o-series rejecting
  `temperature`, gpt-5 family using `max_completion_tokens`, gpt-5.4-mini
  rejecting `reasoning_effort=minimal`, …).
- Three-mode thinking (`auto` / `on` / `off`) with provider mapping for
  Qwen3, GLM-4.5+, DeepSeek-R1, OpenAI o-series, GPT-5, gpt-oss, Claude via
  OpenRouter, and Gemini.
- 16 bundled benchmarks across knowledge, reasoning, math, coding,
  truthfulness, multilingual, and safety. Stratified sampling, Wilson
  CI95, p50/p95 latency, full token accounting (incl. reasoning + cached).
- Subprocess sandbox (tier 1) for code benchmarks with RLIMIT + timeout +
  env whitelist. Opt-in only.
- Cost estimation per model with overrides; `--max-cost-usd` cap.
- SHA256 response cache + `--resume`. `--thinking-compare` for off/on
  side-by-side delta tables.

## Common commands

```bash
evalbox list benchmarks
evalbox doctor

# single benchmark, small sample
evalbox run --bench mmlu --samples 50

# multiple benchmarks with cost guardrail
evalbox run --bench mmlu,gsm8k,truthfulqa --samples 200 --concurrency 8 --max-cost-usd 5.0

# multilingual
evalbox run --bench kmmlu,cmmlu,jmmlu --samples 50

# code benchmarks (require explicit opt-in — model-generated code runs locally)
evalbox run --bench humaneval,mbpp --samples 30 --accept-code-exec

# off vs on comparison, same data
evalbox run --bench gsm8k --samples 30 --thinking-compare

# academic mode (sandbox / network failures count toward the denominator)
evalbox run --bench humaneval --samples 30 --accept-code-exec --strict-failures

# resume an interrupted run (uses the response cache for the fast path)
evalbox run --bench mmlu --samples 200 --output-dir runs/x
# ctrl-c
evalbox run --bench mmlu --samples 200 --output-dir runs/x --resume
```

Full option list: `evalbox run --help` (30+ flags). Gateway recipes for
vLLM, SGLang, Ollama, OpenRouter, Together, Fireworks: see
[`docs/adapters.md`](./docs/adapters.md) and the `.env.example` comment
block.

## Web UI

```bash
pip install -e ".[web]"
evalbox web                        # opens http://127.0.0.1:8765 in your browser
evalbox web --env-file .env.local  # load a non-default dotenv file first
```

`evalbox web` auto-loads `.env` from the current directory, then exposes the
non-secret values via `GET /api/defaults`. The SPA hydrates its connection /
options inputs from that endpoint, so anything you set in `.env`
(`EVALBOX_BASE_URL`, `EVALBOX_MODEL`, `EVALBOX_THINKING`,
`EVALBOX_CONCURRENCY`, `EVALBOX_MAX_COST_USD`, `EVALBOX_REASONING_EFFORT`,
`EVALBOX_STRICT_FAILURES`, `EVALBOX_PROMPT_CACHE_AWARE`,
`EVALBOX_ACCEPT_CODE_EXEC`, …) shows up in the UI immediately. API key
**values** are never returned — only `has_api_key` / `api_keys` so the UI
can show a "✓ $OPENAI_API_KEY" hint and let the backend resolve the key
server-side per request.

The web UI is a single-page app (Setup → Running → Results). All UI text is
i18n'd (Korean default + English).

## Output

```
evalbox-runs/evalbox-<UTC>--<model-slug>/
  result.json                    # schema v1 (PLAN.md §7)
  result.questions.jsonl         # per-question raw response (turn off with --no-save-questions)
  result-on.json                 # only with --thinking-compare
  result-off.json
```

The same command run twice returns instantly the second time — the response
cache lives at `~/.cache/llm-evalbox/responses/`. Disable with `--no-cache`
or `EVALBOX_NO_CACHE=1`.

## License

Apache-2.0 for the code. Bundled datasets carry their upstream licenses (MIT
/ Apache-2.0 / CC variants); see [`llm_evalbox/data/manifest.yaml`](./llm_evalbox/data/manifest.yaml)
for the full citation/source list. Replace any dataset with your own audited
mirror by editing the manifest entry — the loader checks the bundled path
first, then the cache, then the URL.
