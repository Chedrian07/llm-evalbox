# SPDX-License-Identifier: Apache-2.0
import pytest

from llm_evalbox.eval.extract import (
    extract_imports,
    extract_last_code_block,
    extract_mc_answer,
    extract_numeric_answer,
    normalize_number,
)


@pytest.mark.parametrize("text,expected", [
    ("The answer is B.", "B"),
    ("answer: A", "A"),
    ("After thinking, ... Therefore the answer is D", "D"),
    ("(C)", "C"),
    ("I think it could be A or B, but the final answer is C.", "C"),
    ("d", "D"),
    ("", ""),
    ("E", ""),  # outside ABCD
])
def test_extract_mc_answer_basic(text, expected):
    assert extract_mc_answer(text, "ABCD") == expected


def test_extract_mc_answer_uses_last_match():
    # "answer is X" wins over a stray earlier letter
    assert extract_mc_answer("First A. But the answer is B", "ABCD") == "B"


@pytest.mark.parametrize("text,expected", [
    ("...lots of CoT... #### 42", "42"),
    ("So the answer is 1,234 #### 1,234", "1234"),
    ("there are 5 cars and 3 buses, so 5+3=8", "8"),
    ("nothing here", ""),
])
def test_extract_numeric(text, expected):
    assert extract_numeric_answer(text) == expected


def test_normalize_number():
    assert normalize_number("1,234") == "1234"
    assert normalize_number("3.0") == "3"
    assert normalize_number("3.5") == "3.5"
    assert normalize_number("nope") == "nope"


def test_extract_last_code_block_picks_last():
    text = """
sketch:
```python
def early(): pass
```

actual answer:

```python
def late():
    return 1
```
"""
    out = extract_last_code_block(text)
    assert "def late" in out
    assert "early" not in out


def test_extract_imports_only_imports():
    prompt = "import math\nfrom typing import List\ndef foo():\n    pass\n"
    out = extract_imports(prompt)
    assert "import math" in out
    assert "from typing import List" in out
    assert "def foo" not in out
