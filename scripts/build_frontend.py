#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build the SPA from `web_src/` and publish it into `llm_evalbox/web/frontend/`.

Usage:
    python scripts/build_frontend.py            # pnpm build
    python scripts/build_frontend.py --skip-install  # don't run pnpm install

Wheel building expects the output at `llm_evalbox/web/frontend/index.html`
(see `pyproject.toml` → `[tool.hatch.build.targets.wheel.force-include]`).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_SRC = ROOT / "web_src"
DIST = WEB_SRC / "dist"
TARGET = ROOT / "llm_evalbox" / "web" / "frontend"


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-install", action="store_true", help="Don't run the package manager install step.")
    p.add_argument("--manager", choices=["pnpm", "npm", "yarn"], help="Force a specific package manager.")
    args = p.parse_args()

    if not WEB_SRC.is_dir():
        print(f"error: {WEB_SRC} is missing", file=sys.stderr)
        return 2

    pm = args.manager or _detect_manager()
    if pm is None:
        print("error: pnpm / npm / yarn not found in PATH", file=sys.stderr)
        return 2
    print(f"  using package manager: {pm}")

    if not args.skip_install:
        print(f"→ {pm} install")
        rc = subprocess.call([pm, "install"], cwd=str(WEB_SRC))
        if rc != 0:
            return rc

    print(f"→ {pm} build")
    rc = subprocess.call([pm, "run", "build"], cwd=str(WEB_SRC))
    if rc != 0:
        return rc

    if not (DIST / "index.html").exists():
        print(f"error: vite build did not produce {DIST}/index.html", file=sys.stderr)
        return 1

    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(DIST, TARGET)
    print(f"  → published {TARGET}")
    print("done.")
    return 0


def _detect_manager() -> str | None:
    for cmd in ("pnpm", "npm", "yarn"):
        if _which(cmd):
            return cmd
    return None


if __name__ == "__main__":
    raise SystemExit(main())
