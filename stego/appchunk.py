"""Content-defined chunker for the APP path only (the benchmark keeps the fixed 3,500-char chunker).

Chunks never cross a page. Inside a page, boundaries depend on the text of the line that ends a chunk, not on character offsets, so an edit or an
inserted sentence changes only the chunk(s) around it and every other chunk keeps the same text (and the same cache key).
"""
import hashlib
import re

MIN_CHARS = 200     # avoid one-line chunks (weak gate: it resynchronises right after an edit)
MAX_CHARS = 3500    # safety cut
# Cut after a line whose hash % mod == 0. Smaller mod = smaller chunks. The mod is chosen from the document size
# (coarse buckets) so a small edit keeps the same mod and every untouched chunk keeps the same text.
BUCKETS = [(150, 5), (1000, 12), (10**9, 20)]


def _line_hash(line):
    norm = re.sub(r"\s+", " ", line).strip().lower()
    return int(hashlib.md5(norm.encode()).hexdigest()[:8], 16)


def content_chunks(pages):
    """pages: list of page texts. Returns [[(page_number, line), ...], ...], one list of lines per chunk."""
    n_lines = sum(1 for pg in pages for ln in pg.splitlines() if ln.strip())
    mod = next(m for lim, m in BUCKETS if n_lines < lim)
    chunks, cur, size = [], [], 0
    for pi, pg in enumerate(pages):
        for line in pg.splitlines():
            if not line.strip():
                continue
            cur.append((pi + 1, line))
            size += len(line) + 1
            if size >= MAX_CHARS or (size >= MIN_CHARS and _line_hash(line) % mod == 0):
                chunks.append(cur)
                cur, size = [], 0
        if cur:   # a chunk never crosses a page, so Drex evidence maps to an exact page
            chunks.append(cur)
            cur, size = [], 0
    return chunks


def chunk_text_of(lines):
    return "\n".join(l for _, l in lines) + "\n"


def chunk_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]
