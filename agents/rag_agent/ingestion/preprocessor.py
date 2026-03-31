"""Text preprocessor — cleans raw document text before chunking."""

from __future__ import annotations

import re
from loguru import logger


def clean(text: str) -> str:
    """Normalize raw document text for chunking.

    Operations:
    - Remove separator lines made of = or - characters
    - Collapse 3+ blank lines into 2
    - Strip trailing whitespace on each line
    - Remove leading/trailing whitespace from the full text
    """
    # Remove lines that are only decoration (===, ---, spaces)
    text = re.sub(r"^[=\-]{4,}\s*$", "", text, flags=re.MULTILINE)
    # Collapse 3+ blank lines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace on each line
    text = "\n".join(line.rstrip() for line in text.splitlines())
    text = text.strip()
    logger.debug(f"preprocessor.clean → {len(text)} chars after cleaning")
    return text
