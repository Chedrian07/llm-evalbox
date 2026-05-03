# SPDX-License-Identifier: Apache-2.0
"""Result rendering: rich table (CLI), JSON schema v1."""

from llm_evalbox.reports.html import render_run_html
from llm_evalbox.reports.json_report import (
    SCHEMA_VERSION,
    serialize_result,
    write_result_json,
    write_result_questions_jsonl,
)
from llm_evalbox.reports.markdown import render_compare_md, render_run_md
from llm_evalbox.reports.table import render_run_table, render_thinking_compare_table

__all__ = [
    "SCHEMA_VERSION",
    "render_compare_md",
    "render_run_html",
    "render_run_md",
    "render_run_table",
    "render_thinking_compare_table",
    "serialize_result",
    "write_result_json",
    "write_result_questions_jsonl",
]
