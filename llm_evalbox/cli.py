# SPDX-License-Identifier: Apache-2.0
"""evalbox CLI (typer).

M0 commands: run, doctor, list, cache, profiles. Web is M1.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from llm_evalbox._version import __version__
from llm_evalbox.adapters import resolve_adapter
from llm_evalbox.adapters.auth import resolve_api_key
from llm_evalbox.adapters.capabilities import capability_for
from llm_evalbox.cache import cache_root
from llm_evalbox.config import DEFAULTS, load_env_files, load_profile
from llm_evalbox.config.env import env_bool, env_float, env_int, env_str
from llm_evalbox.core.exceptions import EvalBoxError
from llm_evalbox.core.logging import setup_logging
from llm_evalbox.core.messages import Message
from llm_evalbox.core.request import ChatRequest
from llm_evalbox.eval import BENCHMARKS, get_benchmark
from llm_evalbox.eval._sandbox.policy import accept_code_exec
from llm_evalbox.eval.base import SamplingOverrides
from llm_evalbox.pricing import PriceOverrides, cost_for_usage
from llm_evalbox.reports import (
    render_run_table,
    render_thinking_compare_table,
    serialize_result,
    write_result_json,
    write_result_questions_jsonl,
)

app = typer.Typer(
    add_completion=False,
    help="llm-evalbox — OpenAI-compatible benchmark runner.",
    no_args_is_help=True,
)
list_app = typer.Typer(help="List benchmarks / models / profiles.", no_args_is_help=True)
profiles_app = typer.Typer(help="Manage profiles in ~/.config/llm-evalbox/profiles.toml.")
cache_app = typer.Typer(help="Inspect / clear the local cache.")
app.add_typer(list_app, name="list")
app.add_typer(profiles_app, name="profiles")
app.add_typer(cache_app, name="cache")

console = Console()
logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s or "model"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"llm-evalbox {__version__}")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool | None = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True, help="Print version and exit.",
    ),
) -> None:
    """llm-evalbox — see `evalbox --help` for commands."""


# ============================================================ run
@app.command("run", help="Run benchmarks against a model.")
def cmd_run(
    base_url: str | None = typer.Option(None, "--base-url", envvar="EVALBOX_BASE_URL"),
    model: str | None = typer.Option(None, "--model", envvar="EVALBOX_MODEL"),
    adapter: str | None = typer.Option(None, "--adapter", envvar="EVALBOX_ADAPTER"),
    api_key_env: str | None = typer.Option(None, "--api-key-env"),
    extra_header: list[str] | None = typer.Option(None, "--extra-header", help="KEY=VAL (repeatable)"),
    bench: str | None = typer.Option(None, "--bench", help=f"comma-separated benchmark names. Available: {','.join(sorted(BENCHMARKS))}"),
    samples: int | None = typer.Option(None, "--samples", help="Per-benchmark sample size; 0 = full set."),
    concurrency: int | None = typer.Option(None, "--concurrency", envvar="EVALBOX_CONCURRENCY"),
    rpm: int | None = typer.Option(None, "--rpm", envvar="EVALBOX_RPM"),
    tpm: int | None = typer.Option(None, "--tpm", envvar="EVALBOX_TPM"),
    thinking: str | None = typer.Option(None, "--thinking", envvar="EVALBOX_THINKING", help="auto | on | off"),
    no_thinking_rerun: bool = typer.Option(False, "--no-thinking-rerun"),
    thinking_compare: bool = typer.Option(False, "--thinking-compare", help="Run twice (off + on) and print a delta table. Conflicts with --thinking auto."),
    temperature: float | None = typer.Option(None, "--temperature", envvar="EVALBOX_TEMPERATURE"),
    top_p: float | None = typer.Option(None, "--top-p", envvar="EVALBOX_TOP_P"),
    top_k: int | None = typer.Option(None, "--top-k", envvar="EVALBOX_TOP_K"),
    max_tokens: int | None = typer.Option(None, "--max-tokens"),
    reasoning_effort: str | None = typer.Option(None, "--reasoning-effort", envvar="EVALBOX_REASONING_EFFORT"),
    strict_deterministic: bool = typer.Option(False, "--strict-deterministic"),
    strict_failures: bool = typer.Option(False, "--strict-failures", help="Include sandbox/network failures in accuracy denominator (academic mode)."),
    drop_params: str | None = typer.Option(None, "--drop-params", envvar="EVALBOX_DROP_PARAMS"),
    accept_code: bool = typer.Option(False, "--accept-code-exec"),
    no_code_bench: bool = typer.Option(False, "--no-code-bench"),
    lcb_cutoff: str | None = typer.Option(None, "--lcb-cutoff", help="LiveCodeBench: keep only items with release_date >= YYYY-MM-DD"),
    no_cache: bool = typer.Option(False, "--no-cache", envvar="EVALBOX_NO_CACHE", help="Disable response cache."),
    resume: bool = typer.Option(False, "--resume", help="Resume an interrupted run from --output-dir/state.json."),
    profile: str | None = typer.Option(None, "--profile"),
    env_file: str | None = typer.Option(None, "--env-file"),
    output_dir: Path | None = typer.Option(None, "--output-dir"),
    save_questions: bool = typer.Option(True, "--save-questions/--no-save-questions"),
    seed: int | None = typer.Option(None, "--seed"),
    max_cost_usd: float | None = typer.Option(None, "--max-cost-usd", envvar="EVALBOX_MAX_COST_USD"),
    price_input: float | None = typer.Option(None, "--price-input"),
    price_output: float | None = typer.Option(None, "--price-output"),
    price_cached: float | None = typer.Option(None, "--price-cached"),
    price_reasoning: float | None = typer.Option(None, "--price-reasoning"),
    verbose: int = typer.Option(0, "-v", "--verbose", count=True),
    quiet: bool = typer.Option(False, "-q", "--quiet"),
) -> None:
    load_env_files(env_file)
    setup_logging("DEBUG" if verbose >= 2 else ("INFO" if verbose else ("ERROR" if quiet else "WARNING")))

    prof = load_profile(profile) if profile else None

    eff_base_url = base_url or env_str("EVALBOX_BASE_URL") or (prof.base_url if prof else None)
    eff_model = model or env_str("EVALBOX_MODEL")
    eff_adapter = adapter or env_str("EVALBOX_ADAPTER") or (prof.adapter if prof else str(DEFAULTS["adapter"]))
    eff_api_key_env = api_key_env or (prof.api_key_env if prof else None) or str(DEFAULTS["api_key_env"])
    eff_concurrency = concurrency or env_int("EVALBOX_CONCURRENCY") or int(DEFAULTS["concurrency"])
    eff_thinking = thinking or env_str("EVALBOX_THINKING") or str(DEFAULTS["thinking"])
    eff_seed = seed or env_int("EVALBOX_SEED") or int(DEFAULTS["seed"])
    eff_strict = strict_deterministic or env_bool("EVALBOX_STRICT_DETERMINISTIC")
    eff_samples = samples if samples is not None else int(DEFAULTS["samples"])

    if not eff_base_url or not eff_model:
        console.print("[red]error:[/red] --base-url and --model are required (or set EVALBOX_BASE_URL / EVALBOX_MODEL).")
        raise typer.Exit(2)

    api_key = resolve_api_key(eff_api_key_env)
    headers: dict[str, str] = dict((prof.extra_headers if prof else {}) or {})
    for h in (extra_header or []):
        if "=" not in h:
            console.print(f"[yellow]warn:[/yellow] --extra-header missing '=': {h}")
            continue
        k, v = h.split("=", 1)
        headers[k.strip()] = v.strip()

    if accept_code or env_bool("EVALBOX_ACCEPT_CODE_EXEC"):
        accept_code_exec()

    bench_names = [b.strip() for b in (bench or "mmlu").split(",") if b.strip()]
    unknown = [b for b in bench_names if b not in BENCHMARKS]
    if unknown:
        console.print(f"[red]error:[/red] unknown benchmark(s): {','.join(unknown)}")
        raise typer.Exit(2)

    benches = [get_benchmark(n) for n in bench_names]
    if no_code_bench:
        benches = [b for b in benches if not b.is_code_bench()]
    if lcb_cutoff:
        for b in benches:
            if b.name == "livecodebench":
                b.cutoff = lcb_cutoff

    sampling_obj = None
    eff_temp = temperature if temperature is not None else env_float("EVALBOX_TEMPERATURE")
    eff_top_p = top_p if top_p is not None else env_float("EVALBOX_TOP_P")
    eff_top_k = top_k if top_k is not None else env_int("EVALBOX_TOP_K")
    eff_re = reasoning_effort or env_str("EVALBOX_REASONING_EFFORT")
    if any(v is not None for v in (eff_temp, eff_top_p, eff_top_k, max_tokens, eff_re)):
        sampling_obj = SamplingOverrides(
            temperature=eff_temp,
            top_p=eff_top_p,
            top_k=eff_top_k,
            max_tokens=max_tokens,
            reasoning_effort=eff_re,
        )
    elif prof and prof.sampling:
        sampling_obj = SamplingOverrides(
            temperature=prof.sampling.get("temperature"),
            top_p=prof.sampling.get("top_p"),
            top_k=prof.sampling.get("top_k"),
            reasoning_effort=prof.sampling.get("reasoning_effort"),
        )

    user_drop = [p.strip() for p in (drop_params or "").split(",") if p.strip()]

    overrides = PriceOverrides(
        input=price_input, output=price_output, cached_input=price_cached, reasoning=price_reasoning,
    )

    out_root = output_dir or Path("evalbox-runs")
    started_at = _utc_now_iso()
    if resume:
        # Reuse the latest run-dir in out_root so subsequent runs land on the
        # same path. Combined with the response cache, previously-computed
        # questions return as cache hits (latency_ms=0); only missing ones hit
        # the network. If no prior run exists, fall back to a fresh run-id.
        candidates = (
            sorted(out_root.glob("evalbox-*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if out_root.exists() else []
        )
        if candidates:
            run_dir = candidates[0]
            run_id = run_dir.name
            console.print(f"[bold yellow]--resume[/bold yellow] reusing {run_id}")
            if no_cache:
                console.print(
                    "[yellow]warning:[/yellow] --resume with --no-cache won't skip work; "
                    "drop --no-cache for the cache-hit fast path."
                )
        else:
            run_id = f"evalbox-{started_at.replace(':','-')}-{_slug(eff_model)}"
            run_dir = out_root / run_id
            console.print(
                f"[yellow]--resume[/yellow] but no prior run found in {out_root}; "
                f"starting fresh: {run_id}"
            )
    else:
        run_id = f"evalbox-{started_at.replace(':','-')}-{_slug(eff_model)}"
        run_dir = out_root / run_id

    if thinking_compare:
        if (thinking or "").lower() == "auto":
            console.print(
                "[red]error:[/red] --thinking-compare conflicts with --thinking auto. "
                "Use explicit modes (this flag will run both off and on for you)."
            )
            raise typer.Exit(2)
        _run_thinking_compare(
            base_url=eff_base_url, model=eff_model, adapter_kind=eff_adapter,
            api_key=api_key, extra_headers=headers, benches=benches,
            samples=eff_samples, concurrency=eff_concurrency, rpm=rpm, tpm=tpm,
            no_thinking_rerun=no_thinking_rerun, sampling=sampling_obj,
            user_drop=user_drop, strict=eff_strict, strict_failures=strict_failures,
            no_cache=no_cache, run_id=run_id, run_dir=run_dir,
            started_at=started_at, seed=eff_seed, save_questions=save_questions,
            max_cost_usd=max_cost_usd, price_overrides=overrides,
        )
        return

    asyncio.run(
        _run_async(
            base_url=eff_base_url,
            model=eff_model,
            adapter_kind=eff_adapter,
            api_key=api_key,
            extra_headers=headers,
            benches=benches,
            samples=eff_samples,
            concurrency=eff_concurrency,
            rpm=rpm,
            tpm=tpm,
            thinking=eff_thinking,
            no_thinking_rerun=no_thinking_rerun,
            sampling=sampling_obj,
            user_drop=user_drop,
            strict=eff_strict,
            strict_failures=strict_failures,
            no_cache=no_cache,
            resume=resume,
            run_id=run_id,
            run_dir=run_dir,
            started_at=started_at,
            seed=eff_seed,
            save_questions=save_questions,
            max_cost_usd=max_cost_usd,
            price_overrides=overrides,
        )
    )


async def _run_async(
    *,
    base_url: str,
    model: str,
    adapter_kind: str,
    api_key: str | None,
    extra_headers: dict[str, str],
    benches,
    samples: int,
    concurrency: int,
    rpm: int | None,
    tpm: int | None,
    thinking: str,
    no_thinking_rerun: bool,
    sampling,
    user_drop,
    strict: bool,
    strict_failures: bool,
    no_cache: bool,
    resume: bool,
    run_id: str,
    run_dir: Path,
    started_at: str,
    seed: int,
    save_questions: bool,
    max_cost_usd: float | None,
    price_overrides: PriceOverrides,
    result_filename: str = "result.json",
    questions_filename: str = "result.questions.jsonl",
    print_table: bool = True,
) -> tuple[list, dict]:
    from llm_evalbox.cache import ResponseCache

    cap = capability_for(model)
    adapter = resolve_adapter(
        kind=adapter_kind,
        base_url=base_url,
        api_key=api_key,
        extra_headers=extra_headers,
    )
    cache = ResponseCache(enabled=not no_cache)

    console.print(f"[bold]evalbox[/bold] {model} @ {base_url} (adapter={adapter.name})")
    console.print(f"  capability: temp={'✓' if cap.accepts_temperature else '✗'} "
                  f"top_k={'✓' if cap.accepts_top_k else '✗'} "
                  f"seed={'✓' if cap.accepts_seed else '✗'} "
                  f"reasoning_effort={'✓' if cap.accepts_reasoning_effort else '✗'}")
    if cap.notes:
        console.print(f"  note: {cap.notes}")

    results = []
    costs: dict[str, float | None] = {}
    cumulative_cost = 0.0
    cumulative_known = False

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("acc={task.fields[acc]:.3f}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    try:
        with progress:
            for b in benches:
                console.print(f"\n[bold cyan]{b.name}[/bold cyan]: loading dataset…")
                items = await b.load_dataset(samples)
                if not items:
                    console.print(f"  [yellow]no items loaded for {b.name}[/yellow]")
                    continue
                task = progress.add_task(b.name, total=len(items), acc=0.0)

                async def _on_progress(cur, total, payload, _t=task):
                    progress.update(_t, completed=cur, acc=payload.get("running_accuracy", 0.0))

                result = await b.run(
                    adapter,
                    items,
                    model=model,
                    on_progress=_on_progress,
                    concurrency=concurrency,
                    sampling=sampling,
                    thinking=thinking,
                    strict_deterministic=strict,
                    strict_failures=strict_failures,
                    no_thinking_rerun=no_thinking_rerun,
                    cache=cache,
                    base_url=base_url,
                )
                results.append(result)

                cost = cost_for_usage(model, result.usage_total, overrides=price_overrides)
                costs[result.benchmark_name] = cost
                if cost is not None:
                    cumulative_cost += cost
                    cumulative_known = True

                if max_cost_usd is not None and cumulative_known and cumulative_cost >= max_cost_usd:
                    console.print(
                        f"[yellow]cost cap reached ({cumulative_cost:.4f} ≥ {max_cost_usd}); "
                        "stopping after current benchmark[/yellow]"
                    )
                    break
    finally:
        await adapter.close()

    if not results:
        console.print("[red]no results — exiting[/red]")
        raise typer.Exit(1)

    finished_at = _utc_now_iso()
    payload = serialize_result(
        run_id=run_id,
        started_at=started_at,
        finished_at=finished_at,
        seed=seed,
        provider={"adapter": adapter.name, "base_url": base_url, "model": model},
        sampling={
            "temperature": getattr(sampling, "temperature", None) if sampling else 0.0,
            "top_p": getattr(sampling, "top_p", None) if sampling else None,
            "top_k": getattr(sampling, "top_k", None) if sampling else None,
            "max_tokens_default": None,
            "concurrency": concurrency,
            "rpm": rpm,
            "tpm": tpm,
        },
        thinking={
            "mode": thinking,
            "used": any(r.thinking_used for r in results),
        },
        capability={
            "accepts_temperature": cap.accepts_temperature,
            "accepts_top_k": cap.accepts_top_k,
            "accepts_seed": cap.accepts_seed,
            "accepts_reasoning_effort": cap.accepts_reasoning_effort,
        },
        strict_deterministic=strict,
        strict_failures=strict_failures,
        benchmarks=results,
        costs=costs,
    )

    write_result_json(run_dir / result_filename, payload)
    if save_questions:
        write_result_questions_jsonl(run_dir / questions_filename, results)

    # Persist into the cross-process SQLite history (best effort — never fails the run).
    try:
        from llm_evalbox.cache import upsert_run
        upsert_run(payload)
    except Exception as e:  # pragma: no cover
        logger.warning("history upsert failed: %s", e)

    if print_table:
        console.print()
        render_run_table(results, costs=costs, console=console)
        console.print(f"\nresults written to: [bold]{run_dir / result_filename}[/bold]")
    return results, costs


def _run_thinking_compare(
    *,
    base_url, model, adapter_kind, api_key, extra_headers, benches,
    samples, concurrency, rpm, tpm,
    no_thinking_rerun, sampling, user_drop, strict, strict_failures,
    no_cache,
    run_id, run_dir, started_at, seed, save_questions,
    max_cost_usd, price_overrides,
):
    """Run benches twice (off + on) into the same run-dir, then print delta."""

    # Need fresh benches each pass — some carry few-shot state set during
    # load_dataset (e.g. MMLU). We accept duplicate dataset loads.
    bench_classes = [type(b) for b in benches]

    def _fresh():
        out = []
        for cls in bench_classes:
            inst = cls()
            # propagate optional knobs (e.g. lcb cutoff)
            for attr in ("cutoff",):
                v = getattr(benches[0] if benches else None, attr, None)
                if v is not None and hasattr(inst, attr):
                    setattr(inst, attr, v)
            out.append(inst)
        return out

    console.rule("[bold]thinking=off[/bold]")
    off_results, off_costs = asyncio.run(
        _run_async(
            base_url=base_url, model=model, adapter_kind=adapter_kind,
            api_key=api_key, extra_headers=extra_headers, benches=_fresh(),
            samples=samples, concurrency=concurrency, rpm=rpm, tpm=tpm,
            thinking="off", no_thinking_rerun=no_thinking_rerun,
            sampling=sampling, user_drop=user_drop,
            strict=strict, strict_failures=strict_failures,
            no_cache=no_cache, resume=False,
            run_id=run_id, run_dir=run_dir, started_at=started_at, seed=seed,
            save_questions=save_questions, max_cost_usd=max_cost_usd,
            price_overrides=price_overrides,
            result_filename="result-off.json",
            questions_filename="result.questions-off.jsonl",
            print_table=True,
        )
    )

    console.rule("[bold]thinking=on[/bold]")
    on_results, on_costs = asyncio.run(
        _run_async(
            base_url=base_url, model=model, adapter_kind=adapter_kind,
            api_key=api_key, extra_headers=extra_headers, benches=_fresh(),
            samples=samples, concurrency=concurrency, rpm=rpm, tpm=tpm,
            thinking="on", no_thinking_rerun=no_thinking_rerun,
            sampling=sampling, user_drop=user_drop,
            strict=strict, strict_failures=strict_failures,
            no_cache=no_cache, resume=False,
            run_id=run_id, run_dir=run_dir, started_at=_utc_now_iso(), seed=seed,
            save_questions=save_questions, max_cost_usd=max_cost_usd,
            price_overrides=price_overrides,
            result_filename="result-on.json",
            questions_filename="result.questions-on.jsonl",
            print_table=True,
        )
    )

    console.print()
    console.rule("[bold]delta (on − off)[/bold]")
    render_thinking_compare_table(
        off_results, on_results,
        off_costs=off_costs, on_costs=on_costs, console=console,
    )
    console.print(f"\nresults written to: [bold]{run_dir}[/bold]  "
                  "(result-off.json + result-on.json)")


# ============================================================ web
@app.command("web", help="Launch the local web UI (FastAPI + bundled SPA).")
def cmd_web(
    host: str = typer.Option("127.0.0.1", "--host", envvar="EVALBOX_WEB_HOST"),
    port: int = typer.Option(8765, "--port", envvar="EVALBOX_WEB_PORT"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't auto-open the browser."),
    bind_token: str | None = typer.Option(None, "--bind-token", envvar="EVALBOX_WEB_BIND_TOKEN"),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev)."),
) -> None:
    # Bind safety: when listening on a non-loopback interface we require a
    # token so the server isn't immediately exposed to other hosts.
    if host not in ("127.0.0.1", "::1", "localhost") and not bind_token:
        console.print(
            "[red]error:[/red] --host points at a non-loopback interface. "
            "Set --bind-token (or EVALBOX_WEB_BIND_TOKEN) so the server isn't open."
        )
        raise typer.Exit(2)

    try:
        from llm_evalbox.web.server import run_server
    except ImportError as e:
        console.print(
            "[red]error:[/red] web extras not installed.\n"
            f"  install with: pip install -e \".[web]\"\n  ({e})"
        )
        raise typer.Exit(2) from None

    url = f"http://{host}:{port}"
    console.print(f"[bold]evalbox web[/bold] {url} (version {__version__})")
    if not no_open and host in ("127.0.0.1", "localhost"):
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass
    run_server(host=host, port=port, bind_token=bind_token, reload=reload)


# ============================================================ doctor
@app.command("doctor", help="Check connection, capability, and thinking detection.")
def cmd_doctor(
    base_url: str | None = typer.Option(None, "--base-url", envvar="EVALBOX_BASE_URL"),
    model: str | None = typer.Option(None, "--model", envvar="EVALBOX_MODEL"),
    adapter: str | None = typer.Option(None, "--adapter", envvar="EVALBOX_ADAPTER"),
    api_key_env: str | None = typer.Option(None, "--api-key-env"),
    env_file: str | None = typer.Option(None, "--env-file"),
) -> None:
    load_env_files(env_file)
    setup_logging("INFO")
    eff_base_url = base_url or env_str("EVALBOX_BASE_URL")
    eff_model = model or env_str("EVALBOX_MODEL")
    eff_adapter = adapter or env_str("EVALBOX_ADAPTER") or "auto"
    eff_api_key_env = api_key_env or "OPENAI_API_KEY"

    if not eff_base_url or not eff_model:
        console.print("[red]error:[/red] --base-url and --model are required.")
        raise typer.Exit(2)

    api_key = resolve_api_key(eff_api_key_env)
    asyncio.run(_doctor_async(eff_base_url, eff_model, eff_adapter, api_key))


async def _doctor_async(base_url: str, model: str, adapter_kind: str, api_key: str | None) -> None:
    console.print(f"[bold]doctor[/bold] {model} @ {base_url}")
    cap = capability_for(model)
    console.print(f"  capability rule: {cap.notes or '(default)'}")
    adapter = resolve_adapter(kind=adapter_kind, base_url=base_url, api_key=api_key)
    try:
        models = await adapter.list_models()
        if models:
            ids = [m.id for m in models]
            present = "✓" if model in ids else "?"
            console.print(f"  /v1/models: {len(ids)} model(s) — '{model}' listed: {present}")
        else:
            console.print("  /v1/models: not exposed")
    except EvalBoxError as e:
        console.print(f"  /v1/models: [red]{e}[/red]")

    # Adaptive dry chat: send a probe; on 4xx with a recognizable
    # "unsupported param" message, strip the offending key and retry.
    # Keeps doctor useful for endpoints whose accept-list differs from
    # the static capability matrix (gateways, custom proxies).
    from llm_evalbox.adapters.capabilities import parse_unsupported_param_error
    from llm_evalbox.core.exceptions import BadRequestError

    drop_params: list[str] = []
    resp = None
    last_error: BadRequestError | None = None
    for attempt in range(3):
        req = ChatRequest(
            model=model,
            messages=[Message(role="user", content="Reply with the single word: OK")],
            max_tokens=8,
            thinking="auto",
            drop_params=list(drop_params),
        )
        try:
            resp = await adapter.chat(req)
            break
        except BadRequestError as e:
            last_error = e
            unsupported = parse_unsupported_param_error(str(e))
            new = sorted(k for k in unsupported if k not in drop_params)
            if not new:
                # Couldn't parse — bail out and report the raw error.
                break
            drop_params.extend(new)
            console.print(
                f"  [yellow]4xx noted:[/yellow] adding drop_params={new} "
                f"(attempt {attempt + 1}/3), retrying…"
            )
        except EvalBoxError as e:
            console.print(f"  dry chat: [red]{e}[/red]")
            await adapter.close()
            raise typer.Exit(1) from None

    try:
        if resp is None:
            console.print(f"  dry chat: [red]{last_error}[/red]")
            raise typer.Exit(1)

        console.print(f"  dry chat: {resp.latency_ms:.0f}ms — finish={resp.finish_reason} "
                      f"thinking_observed={resp.thinking_observed}")
        console.print(f"           text: {resp.text[:80]!r}")
        if resp.usage.total_tokens:
            console.print(f"           usage: prompt={resp.usage.prompt_tokens} "
                          f"completion={resp.usage.completion_tokens} "
                          f"reasoning={resp.usage.reasoning_tokens}")
        if drop_params:
            console.print(
                f"  [bold yellow]learned drop_params:[/bold yellow] "
                f"{','.join(drop_params)}  "
                f"(re-use via --drop-params {','.join(drop_params)} or "
                f"EVALBOX_DROP_PARAMS={','.join(drop_params)})"
            )
    finally:
        await adapter.close()


# ============================================================ list
@list_app.command("benchmarks", help="List available benchmarks.")
def cmd_list_benchmarks() -> None:
    for name, cls in sorted(BENCHMARKS.items()):
        b = cls()
        console.print(f"  {name:14s}  quick={b.quick_size}  code={'yes' if b.is_code_bench() else 'no'}")


@list_app.command("models", help="Call /v1/models on the configured endpoint.")
def cmd_list_models(
    base_url: str | None = typer.Option(None, "--base-url", envvar="EVALBOX_BASE_URL"),
    api_key_env: str | None = typer.Option(None, "--api-key-env"),
) -> None:
    load_env_files(None)
    if not base_url:
        console.print("[red]error:[/red] --base-url required.")
        raise typer.Exit(2)
    api_key = resolve_api_key(api_key_env or "OPENAI_API_KEY")
    asyncio.run(_list_models_async(base_url, api_key))


async def _list_models_async(base_url: str, api_key: str | None) -> None:
    adapter = resolve_adapter(kind="chat", base_url=base_url, api_key=api_key)
    try:
        models = await adapter.list_models()
    finally:
        await adapter.close()
    if not models:
        console.print("(empty / not exposed)")
        return
    for m in models:
        suffix = f" ({m.owned_by})" if m.owned_by else ""
        console.print(f"  {m.id}{suffix}")


# ============================================================ profiles
@profiles_app.command("ls", help="List profiles found in profiles.toml.")
def cmd_profiles_ls() -> None:
    from llm_evalbox.config.profile import PROFILE_PATH
    if not PROFILE_PATH.exists():
        console.print(f"(no profiles file at {PROFILE_PATH})")
        return
    import sys
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]
    with open(PROFILE_PATH, "rb") as f:
        data = tomllib.load(f)
    for name, val in data.items():
        if isinstance(val, dict):
            console.print(f"  {name:14s}  base_url={val.get('base_url','-')}  adapter={val.get('adapter','auto')}")


# ============================================================ cache
@cache_app.command("info", help="Show cache directory and disk usage.")
def cmd_cache_info() -> None:
    root = cache_root()
    console.print(f"  cache root: {root}")
    if not root.exists():
        console.print("  (does not exist yet)")
        return
    total = 0
    for p in root.rglob("*"):
        if p.is_file():
            total += p.stat().st_size
    console.print(f"  files total: {total/1e6:.1f} MB")


@cache_app.command("history", help="List runs in the persistent SQLite history.")
def cmd_cache_history(
    limit: int = typer.Option(20, "--limit"),
    model: str | None = typer.Option(None, "--model", help="Filter by model name."),
) -> None:
    from llm_evalbox.cache import list_runs
    rows = list_runs(limit=limit, model=model)
    if not rows:
        console.print("(empty)")
        return
    for r in rows:
        acc = r.get("accuracy_macro")
        cost = r.get("cost_usd")
        console.print(
            f"  {r['run_id']:50s} {r.get('model','?'):20s} "
            f"acc={(acc if acc is not None else 0):.3f}  "
            f"cost={(f'${cost:.4f}') if cost is not None else '-':>9}  "
            f"benches={r.get('bench_count',0)}"
        )


@cache_app.command("clear", help="Delete cached datasets and runs (interactive confirm).")
def cmd_cache_clear(yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    root = cache_root()
    if not root.exists():
        console.print("(nothing to clear)")
        return
    if not yes:
        confirm = typer.confirm(f"Delete everything under {root}?")
        if not confirm:
            raise typer.Exit(1)
    import shutil
    shutil.rmtree(root)
    console.print(f"removed {root}")


# ============================================================ compare
@app.command("compare", help="Print a side-by-side comparison of multiple run-dirs.")
def cmd_compare(
    run_dirs: list[Path] = typer.Argument(..., exists=True, file_okay=False),
    output_md: Path | None = typer.Option(None, "--md", help="Write Markdown to this path."),
) -> None:
    import json as _json

    from llm_evalbox.reports import render_compare_md
    payloads = []
    for rd in run_dirs:
        rj = rd / "result.json"
        if not rj.exists():
            console.print(f"[yellow]skip {rd}[/yellow] (no result.json)")
            continue
        with open(rj, encoding="utf-8") as f:
            payloads.append(_json.load(f))
    if not payloads:
        console.print("[red]error:[/red] no result.json found in any run-dir")
        raise typer.Exit(2)
    md = render_compare_md(payloads)
    if output_md:
        output_md.write_text(md, encoding="utf-8")
        console.print(f"compare written to: [bold]{output_md}[/bold]")
    else:
        console.print(md)


# ============================================================ export
@app.command("export", help="Export a run-dir to markdown / html / json.")
def cmd_export(
    run_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    to: str = typer.Option("md", "--to", help="md | html | json"),
    output: Path | None = typer.Option(None, "--output", help="Output path (default stdout)."),
) -> None:
    import json as _json
    rj = run_dir / "result.json"
    if not rj.exists():
        console.print(f"[red]error:[/red] {rj} missing")
        raise typer.Exit(2)
    with open(rj, encoding="utf-8") as f:
        payload = _json.load(f)

    fmt = to.lower()
    if fmt == "md":
        from llm_evalbox.reports import render_run_md
        text = render_run_md(payload)
    elif fmt == "html":
        from llm_evalbox.reports import render_run_html
        text = render_run_html(payload)
    elif fmt == "json":
        text = _json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    else:
        console.print(f"[red]error:[/red] --to must be md|html|json (got {to!r})")
        raise typer.Exit(2)

    if output:
        output.write_text(text, encoding="utf-8")
        console.print(f"exported to: [bold]{output}[/bold]")
    else:
        console.print(text)


if __name__ == "__main__":
    app()
