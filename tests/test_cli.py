# SPDX-License-Identifier: Apache-2.0
"""CLI usage-level behavior."""

from __future__ import annotations

from typer.testing import CliRunner

from llm_evalbox.cli import app


def test_run_resume_is_disabled():
    result = CliRunner().invoke(app, ["run", "--resume"])

    assert result.exit_code == 2
    assert "response-cache based --resume was removed" in result.output
    assert "Web runs can automatically" in result.output
    assert "reattach while the server process is alive" in result.output
