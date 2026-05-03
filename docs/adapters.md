# Adapters & gateway compatibility

llm-evalbox supports any OpenAI-compatible endpoint that exposes `/v1/chat/completions`.
The `Responses` adapter (`/v1/responses`) is opt-in and primarily targets OpenAI's o-series
and gpt-5 family.

## Adapter selection

| Value | Endpoint hit | When to use |
|---|---|---|
| `auto` (default) | `/v1/chat/completions` | Default — works with the vast majority of providers. |
| `chat_completions` | `/v1/chat/completions` | Same as auto, explicit. |
| `responses` | `/v1/responses` | OpenAI public for o1 / o3 / o4 / gpt-5 / gpt-oss. |

There is **no automatic probe** between the two adapters — gateways rarely expose `/v1/responses`,
and adding a probe round-trip just wastes a request. If you need the Responses API, set
`EVALBOX_ADAPTER=responses` or pass `--adapter responses`.

## Tested gateways

The list below is what we've actually used or have respx round-trip tests for.
Anything OpenAI-compatible should "just work" with `EVALBOX_ADAPTER=auto`; the
notes below highlight surprises.

| Gateway | `BASE_URL` | API key | Notes |
|---|---|---|---|
| **OpenAI public** | `https://api.openai.com/v1` | `OPENAI_API_KEY` | gpt-4o family on chat; o-series / gpt-5 on either chat or responses. |
| **vLLM** | `http://host:8000/v1` | `EMPTY` (or any) | Accepts `top_k`, `repetition_penalty`, `chat_template_kwargs.enable_thinking` (Qwen3 / GLM-4.5+). |
| **SGLang** | `http://host:30000/v1` | (any) | Same as vLLM. |
| **Ollama** | `http://host:11434/v1` | `ollama` | Some sampling keys silently ignored — capability rules try to strip. |
| **OpenRouter** | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | Add `HTTP-Referer` / `X-Title` via `--extra-header KEY=VAL`. |
| **Together AI** | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` | Wide model catalog; chat-completions only. |
| **Fireworks** | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` | Chat-completions; check per-model whether `top_k` is accepted. |
| **Anthropic via OpenRouter** | (via OpenRouter) | (OpenRouter key) | Thinking encoded as `extra={"extended_thinking": {...}}` (matrix in `core/thinking.py`). |
| **Gemini OpenAI-compat** | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` | Thinking via `extra={"thinking_config": {...}}`; no `seed`. |

## Capability handling

`adapters/capabilities.py` keeps a per-model-family matrix of which sampling keys are
accepted. When the model name doesn't match any rule, we fall back to the OpenAI public
defaults (which are conservative). To recover from a mismatch:

1. Run `evalbox doctor --base-url ... --model ...`. It sends a probe and, on a 4xx,
   parses the response message looking for "unrecognized parameter X" / "X is not supported"
   / `level "Y" not supported` patterns. Recognized keys are added to a `drop_params`
   list and the probe is retried (up to 3 times).
2. If the probe succeeds with a non-empty `learned drop_params`, doctor prints a
   line like:
   ```
   learned drop_params: top_k,reasoning_effort
     (re-use via --drop-params top_k,reasoning_effort or
      EVALBOX_DROP_PARAMS=top_k,reasoning_effort)
   ```
   Set that env var (or pass the flag) so subsequent runs strip those keys before
   they hit the wire.

We do not persist learned capabilities to disk in M0 — output is informational only.
Adding `~/.config/llm-evalbox/learned_capabilities.json` is M3 polish.

## Multiple endpoints in one project

For more than one gateway, prefer `~/.config/llm-evalbox/profiles.toml`:

```toml
[default]
adapter = "auto"
base_url = "https://api.openai.com/v1"
api_key_env = "OPENAI_API_KEY"

[my-vllm]
adapter = "chat_completions"
base_url = "http://localhost:8000/v1"
api_key_env = "VLLM_KEY"

[my-vllm.sampling]
temperature = 0.6
top_p = 0.95
top_k = 20

[openrouter]
adapter = "chat_completions"
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"
extra_headers = { "HTTP-Referer" = "https://github.com/you/proj" }
```

Then: `evalbox run --profile my-vllm --bench mmlu`.
