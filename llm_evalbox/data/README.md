# `llm_evalbox/data/`

Holds the dataset **manifest** and **bundled JSONL corpora** under
`datasets/`. Bundled means the package ships with these files and they
load with zero network access at runtime.

Each entry in `manifest.yaml` records `license` and `citation`. All
bundled corpora use permissive licenses (MIT / Apache-2.0 / CC variants).
Sources are unmodified copies of the upstream HuggingFace mirrors cited
per entry.

## Resolution order

When a benchmark calls `ensure_dataset(name)`:

1. `llm_evalbox/data/datasets/<file>` (bundled, shipped in the wheel).
2. `$EVALBOX_DATASETS_DIR/<name>/<file>` (user override).
3. `~/.cache/llm-evalbox/datasets/<name>/<file>` (lazy download).

Entries marked `bundled: true` skip step 3 and raise a clear error if the
file is missing — that would mean a packaging bug.

## Why bundle (revised 2026-04-30)

PLAN.md §14 originally forbade bundling. We reversed that decision for two
reasons:

1. **Upstream URLs broke.** HuggingFace migrated all five M0 datasets from
   JSONL to parquet, so every `*.jsonl` URL we'd manifested started
   returning 404. Adding parquet support would have meant pulling in
   `pyarrow` (~50 MB).
2. **Licenses permit it.** Every dataset shipped here is MIT, Apache-2.0,
   or a CC variant that allows redistribution as long as we cite the
   source — which `manifest.yaml` does for every entry.

Total bundled size: ~62 MB. Acceptable for a tool whose value proposition
is "works in one `pip install`."

## Refreshing data

Drop replacement JSONL files into `datasets/` and update the manifest
entry's `citation` / `source` if needed. There is no SHA verification step
for bundled files — the wheel itself is the integrity boundary.
