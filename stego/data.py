"""CUAD loading, fixed split, chunking and gold labels.

Gold presence = the CUAD category has at least one lawyer-highlighted span.
Gold evidence chunks = chunks overlapping any highlighted span (character offsets from CUAD).
"""
import json
import random
import re
from dataclasses import dataclass, field

from . import config


@dataclass
class Chunk:
    idx: int
    start: int
    end: int
    text: str


@dataclass
class Contract:
    title: str
    text: str
    chunks: list
    gold_present: dict = field(default_factory=dict)   # category -> bool
    gold_chunks: dict = field(default_factory=dict)    # category -> set(chunk idx)


def _definitions(qas):
    """Pull CUAD's own labeling definition ('Details: ...') for each category."""
    defs = {}
    for qa in qas:
        cat = qa["id"].split("__", 1)[1]
        m = re.search(r"Details:\s*(.*)$", qa["question"], re.S)
        defs[cat] = (m.group(1).strip() if m else cat)
    return defs


def chunk_text(text, size=config.CHUNK_CHARS):
    """Split on line boundaries into ~size-char chunks, keeping exact offsets."""
    chunks, start = [], 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            nl = text.rfind("\n", start + size // 2, end)
            if nl != -1:
                end = nl + 1
        chunks.append(Chunk(len(chunks), start, end, text[start:end]))
        start = end
    return chunks


def split_paragraphs(chunk, min_chars=config.PARA_MIN_CHARS):
    """Drill-down units inside a chunk (offsets kept relative to the contract)."""
    parts, buf_start, pos = [], chunk.start, chunk.start
    for line in chunk.text.splitlines(keepends=True):
        pos += len(line)
        if pos - buf_start >= min_chars:
            parts.append((buf_start, pos))
            buf_start = pos
    if buf_start < chunk.end:
        if parts and chunk.end - buf_start < min_chars // 2:
            parts[-1] = (parts[-1][0], chunk.end)
        else:
            parts.append((buf_start, chunk.end))
    return parts


def load(path=config.CUAD_TEST_JSON, categories=config.CATEGORIES):
    data = json.load(open(path, encoding="utf-8"))["data"]
    contracts, definitions = [], {}
    for doc in data:
        para = doc["paragraphs"][0]
        text = para["context"]
        definitions.update(_definitions(para["qas"]))
        c = Contract(doc["title"], text, chunk_text(text))
        by_cat = {qa["id"].split("__", 1)[1]: qa for qa in para["qas"]}
        for cat in categories:
            qa = by_cat.get(cat)
            if qa is None:
                raise KeyError(f"Category {cat!r} not in CUAD; available: {sorted(by_cat)}")
            spans = [(a["answer_start"], a["answer_start"] + len(a["text"])) for a in qa["answers"]]
            c.gold_present[cat] = bool(spans)
            c.gold_chunks[cat] = {
                ch.idx for ch in c.chunks for (s, e) in spans if s < ch.end and e > ch.start
            }
        contracts.append(c)
    return contracts, {k: definitions[k] for k in categories}


def split(contracts, seed=config.SEED, n_calib=config.N_CALIB):
    order = sorted(contracts, key=lambda c: c.title)
    random.Random(seed).shuffle(order)
    return order[:n_calib], order[n_calib:]
