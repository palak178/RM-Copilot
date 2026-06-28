"""Prompt asset loading.

Prompts are versioned Markdown under ../../prompts/ (data, not code). Loaded once
and cached.
"""

from functools import cache
from pathlib import Path

PROMPTS_DIR = Path("prompts")


@cache
def load_prompt(name: str) -> str:
    """Read prompts/<name>.md (relative to the working directory / repo root)."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
