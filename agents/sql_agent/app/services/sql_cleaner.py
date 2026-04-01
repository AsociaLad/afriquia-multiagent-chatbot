"""Clean raw LLM output to extract a pure SQL query.

Handles common LLM formatting artifacts:
- Markdown code fences (```sql ... ```)
- Leading/trailing backticks
- Explanatory text before or after the query
- Extra whitespace and semicolons
"""

from __future__ import annotations

import re

from loguru import logger


def clean_sql(raw_output: str) -> str:
    """Extract a clean SQL SELECT statement from raw LLM output.

    Args:
        raw_output: The raw text returned by the LLM.

    Returns:
        A cleaned SQL string ready for validation and execution.
        Returns empty string if no SELECT is found.
    """
    text = raw_output.strip()

    if not text:
        logger.warning("[sql_cleaner] Empty input")
        return ""

    # --- Step 1: Remove markdown code fences ---
    # Match ```sql ... ``` or ``` ... ```
    fence_pattern = re.compile(
        r"```(?:sql|SQL|postgres|postgresql)?\s*\n?(.*?)\n?\s*```",
        re.DOTALL | re.IGNORECASE,
    )
    fence_match = fence_pattern.search(text)
    if fence_match:
        text = fence_match.group(1).strip()
        logger.debug("[sql_cleaner] Extracted from code fence")

    # --- Step 2: Remove inline backticks ---
    if text.startswith("`") and text.endswith("`"):
        text = text.strip("`").strip()

    # --- Step 3: Remove <think>...</think> blocks (qwen3 reasoning) ---
    think_pattern = re.compile(r"<think>.*?</think>", re.DOTALL)
    text = think_pattern.sub("", text).strip()

    # --- Step 4: Extract SELECT statement if surrounded by text ---
    # Look for SELECT ... ; (greedy on the last semicolon)
    select_pattern = re.compile(
        r"(SELECT\s+.+)",
        re.DOTALL | re.IGNORECASE,
    )
    select_match = select_pattern.search(text)
    if select_match:
        text = select_match.group(1).strip()
    else:
        logger.warning(f"[sql_cleaner] No SELECT found in: {text[:100]!r}")
        return ""

    # --- Step 5: Trim trailing noise after the query ---
    # If there's text after the last semicolon, remove it
    last_semi = text.rfind(";")
    if last_semi > 0:
        text = text[: last_semi + 1]

    # --- Step 6: Normalize whitespace ---
    text = re.sub(r"\s+", " ", text).strip()

    # --- Step 7: Ensure trailing semicolon ---
    if not text.endswith(";"):
        text += ";"

    logger.debug(f"[sql_cleaner] Cleaned SQL: {text}")
    return text
