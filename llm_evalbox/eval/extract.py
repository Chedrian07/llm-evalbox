# SPDX-License-Identifier: Apache-2.0
"""Answer extraction utilities shared across benchmarks.

These are pure functions — easier to unit-test independently than methods
hung off a class.
"""

from __future__ import annotations

import re

_LAST_CODE_BLOCK_LANGS = ("python", "")


def extract_mc_answer(response: str, valid_letters: list[str] | str) -> str:
    """Multiple-choice letter extractor.

    Strategy (last match wins to avoid models hedging mid-response):
      1. "answer is X" / "answer: X".
      2. "(A)" / "(B)" patterns.
      3. Last standalone valid letter with word boundary.
      4. First non-whitespace character if it's a valid letter.
    """
    if isinstance(valid_letters, str):
        letters = list(valid_letters)
    else:
        letters = list(valid_letters)
    text = (response or "").strip().upper()
    pat = "[" + "".join(letters) + "]"

    m = re.findall(rf"(?:ANSWER\s*(?:IS|:)\s*)({pat})\b", text)
    if m:
        return m[-1]

    m = re.findall(rf"\(({pat})\)", text)
    if m:
        return m[-1]

    m = re.findall(rf"\b({pat})\b", text)
    if m:
        return m[-1]

    if text and text[0] in letters:
        return text[0]

    return ""


def extract_last_code_block(response: str) -> str:
    """Return the LAST python (or generic) fenced code block.

    Falls back to a heuristic line scan starting from the first def/import.
    """
    response = (response or "").strip()
    for lang in _LAST_CODE_BLOCK_LANGS:
        head = rf"```{lang}" if lang else r"```"
        blocks = re.findall(rf"{head}\s*\n(.*?)```", response, re.DOTALL)
        if blocks:
            return blocks[-1].strip()

    lines = response.split("\n")
    code: list[str] = []
    in_code = False
    for line in lines:
        if not in_code and (
            line.startswith("def ")
            or line.startswith("class ")
            or line.startswith("import ")
            or line.startswith("from ")
            or line.startswith("#!")
        ):
            in_code = True
        if in_code:
            code.append(line)

    return "\n".join(code) if code else response


_NUMERIC_RE = re.compile(r"-?[\d,]+(?:\.\d+)?")


def extract_numeric_answer(text: str) -> str:
    """GSM8K-style: prefer "#### N" else last number-like token."""
    m = re.search(r"####\s*(-?[\d,]+(?:\.\d+)?)", text or "")
    if m:
        return m.group(1).replace(",", "")
    nums = _NUMERIC_RE.findall(text or "")
    if nums:
        return nums[-1].replace(",", "")
    return ""


def normalize_number(s: str) -> str:
    """Strip commas/whitespace; return canonical int-or-float string."""
    s = (s or "").strip().replace(",", "")
    try:
        v = float(s)
        if v == int(v):
            return str(int(v))
        return str(v)
    except (ValueError, OverflowError):
        return s


def extract_imports(prompt: str) -> str:
    """Return the import block of a prompt — used by HumanEval to avoid NameError."""
    return "\n".join(
        line for line in (prompt or "").split("\n")
        if line.strip().startswith(("import ", "from "))
    )
