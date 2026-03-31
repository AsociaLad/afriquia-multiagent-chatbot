"""Text chunker — sliding-window split with configurable separators."""

from __future__ import annotations

from loguru import logger

CHUNK_SIZE = 500   # characters
OVERLAP    = 50    # characters of overlap between consecutive chunks
SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " ", ""]


def _split_on_separator(text: str, separator: str) -> list[str]:
    """Split text on separator, re-appending the separator to each part."""
    if separator == "":
        return list(text)
    parts = text.split(separator)
    # Re-attach the separator to all parts except the last
    return [p + separator for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def _merge_splits(splits: list[str], chunk_size: int) -> list[str]:
    """Greedily merge small splits into chunks of at most chunk_size chars."""
    chunks: list[str] = []
    current = ""
    for part in splits:
        if len(current) + len(part) <= chunk_size:
            current += part
        else:
            if current:
                chunks.append(current.strip())
            # If a single part exceeds chunk_size, keep it as-is
            current = part
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _recursive_split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    """Recursively split text using the separator list until chunks fit."""
    if not text:
        return []

    separator = separators[0]
    next_separators = separators[1:]

    splits = _split_on_separator(text, separator)
    good: list[str] = []

    for part in splits:
        if len(part) <= chunk_size:
            good.append(part)
        elif next_separators:
            # Part is too big — recurse with the next separator
            good.extend(_recursive_split(part, next_separators, chunk_size))
        else:
            # No more separators — hard-cut
            for i in range(0, len(part), chunk_size):
                good.append(part[i:i + chunk_size])

    return _merge_splits(good, chunk_size)


def chunk(
    text: str,
    source: str = "",
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
) -> list[dict]:
    """Split text into overlapping chunks.

    Returns a list of dicts: {text, source, chunk_index, char_start, char_end}.
    """
    raw_chunks = _recursive_split(text, SEPARATORS, chunk_size)

    result: list[dict] = []
    for i, raw in enumerate(raw_chunks):
        if not raw.strip():
            continue

        # Build chunk with overlap: prepend tail of previous chunk
        if i > 0 and overlap > 0:
            tail = raw_chunks[i - 1][-overlap:]
            text_with_overlap = tail + raw
        else:
            text_with_overlap = raw

        result.append({
            "text":        text_with_overlap.strip(),
            "source":      source,
            "chunk_index": i,
        })

    logger.debug(f"chunker: '{source}' → {len(result)} chunk(s)")
    return result
