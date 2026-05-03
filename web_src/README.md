# web_src

React + Vite + TypeScript + Tailwind + shadcn-style UI for the
`evalbox web` SPA.

## Develop

```bash
pnpm install
pnpm dev          # Vite at http://localhost:5173, proxies /api/* → 127.0.0.1:8765
```

In another shell, run the backend:

```bash
evalbox web --no-open
```

## Build

```bash
pnpm build
# -> dist/

# Or, to publish into the wheel:
python ../scripts/build_frontend.py
# -> ../llm_evalbox/web/frontend/
```

## Layout

```
src/
  main.tsx           # entry, mounts <App /> with React Query + i18n
  App.tsx            # stage-machine shell (Setup / Running / Results)
  i18n/              # ko (default) + en JSON resources
  lib/               # api fetcher, sse subscriber, zustand store, formatters, cn()
  components/ui/     # shadcn-style primitives — Button, Card, Input, Label, Badge, Progress
  components/        # ConnectionCard, ThinkingToggle, BenchmarkGrid, OptionsCard,
                     # CostPreview, LocaleToggle
  pages/             # SetupPage, RunningPage, ResultsPage
  styles/globals.css # Tailwind layers + shadcn CSS variables (light + .dark)
```

The SPA talks to the FastAPI backend via `/api/*`. SSE lives at
`/api/runs/{run_id}/events`.
