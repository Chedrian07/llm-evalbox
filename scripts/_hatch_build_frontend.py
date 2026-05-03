# SPDX-License-Identifier: Apache-2.0
"""Hatchling custom build hook — runs scripts/build_frontend.py before wheel
packaging so the SPA bundle (`llm_evalbox/web/frontend/`) is materialized
and gets force-included.

Skipped in three cases:
  1. SDist build (we don't need the bundle in the source distribution).
  2. EVALBOX_SKIP_FRONTEND=1 (developer override).
  3. No node package manager on PATH (graceful — wheel ships without the SPA;
     `evalbox web` falls back to its placeholder page).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class FrontendBuildHook(BuildHookInterface):
    PLUGIN_NAME = "frontend-build"

    def initialize(self, version, build_data):  # type: ignore[override]
        if self.target_name == "sdist":
            return
        if os.environ.get("EVALBOX_SKIP_FRONTEND") == "1":
            self.app.display_info("evalbox: EVALBOX_SKIP_FRONTEND=1 set, skipping frontend build")
            return

        root = Path(self.root)
        web_src = root / "web_src"
        target = root / "llm_evalbox" / "web" / "frontend"
        if not web_src.is_dir():
            self.app.display_warning(
                "evalbox: web_src/ missing — wheel will ship without the SPA bundle"
            )
            return

        # Need a package manager. Skip rather than fail in environments without one.
        manager = next((m for m in ("pnpm", "npm", "yarn") if shutil.which(m)), None)
        if manager is None:
            self.app.display_warning(
                "evalbox: pnpm / npm / yarn not on PATH — skipping frontend build "
                "(wheel will ship without the SPA bundle; `evalbox web` will use the "
                "placeholder page until you run `python scripts/build_frontend.py`)"
            )
            return

        # Reuse the standalone build script for consistency between manual
        # invocation and the hatch hook.
        script = root / "scripts" / "build_frontend.py"
        rc = subprocess.call([sys.executable, str(script)], cwd=str(root))
        if rc != 0:
            raise RuntimeError(f"evalbox: frontend build failed (exit {rc})")
        if not (target / "index.html").exists():
            raise RuntimeError(
                "evalbox: build_frontend.py succeeded but no index.html at "
                f"{target} — packaging would skip the bundle"
            )
        self.app.display_info(f"evalbox: SPA bundle ready at {target}")
