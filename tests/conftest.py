# SPDX-License-Identifier: Apache-2.0
"""Test-wide fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIX_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def chat_completion_payload():
    """Minimal valid /v1/chat/completions payload (no thinking)."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-4o-mini",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "B"},
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
    }


@pytest.fixture
def chat_completion_with_thinking():
    """Payload with <think> block + reasoning_content metadata."""
    return {
        "id": "chatcmpl-test-2",
        "model": "deepseek-r1",
        "choices": [{
            "index": 0,
            "finish_reason": "stop",
            "message": {
                "role": "assistant",
                "content": "<think>let me think</think>\nAnswer: A",
                "reasoning_content": "more reasoning",
            },
        }],
        "usage": {
            "prompt_tokens": 20,
            "completion_tokens": 5,
            "total_tokens": 25,
            "completion_tokens_details": {"reasoning_tokens": 4},
            "prompt_tokens_details": {"cached_tokens": 8},
        },
    }


@pytest.fixture
def mini_mmlu():
    """5-item mini MMLU sample (subject + question + choices + answer)."""
    return [
        {"id": "mc-1", "question": "2+2 = ?", "choices": ["3", "4", "5", "6"],
         "answer": "B", "subject": "math"},
        {"id": "mc-2", "question": "Capital of France?", "choices": ["Berlin", "Paris", "Rome", "Madrid"],
         "answer": "B", "subject": "geo"},
        {"id": "mc-3", "question": "H2O is?", "choices": ["water", "salt", "air", "metal"],
         "answer": "A", "subject": "science"},
        {"id": "mc-4", "question": "Largest planet?", "choices": ["Earth", "Mars", "Jupiter", "Venus"],
         "answer": "C", "subject": "science"},
        {"id": "mc-5", "question": "Sun rises in?", "choices": ["West", "East", "North", "South"],
         "answer": "B", "subject": "geo"},
    ]
