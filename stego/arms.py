"""The three pre-registered arms.

A  llm     : frontier LLM reads every chunk, one JSON call per contract.
B  drex    : Drex only. Section sweep (all categories per chunk) + paragraph drill-down. Zero LLM calls.
C  cascade : B, then the LLM only for categories whose Drex confidence < tau, on Drex's top-k chunks.
"""
import asyncio
import time

from . import config
from .data import split_paragraphs


def _qset(categories, definitions, client):
    """Stable, host-safe question ids (some categories contain '/')."""
    ids = {f"q{i}": c for i, c in enumerate(categories)}
    return ids, {qid: client.question(c, definitions[c]) for qid, c in ids.items()}


async def run_drex(contract, categories, definitions, drex, arm="drex", progress=None):
    t0 = time.perf_counter()
    ids, questions = _qset(categories, definitions, drex)
    if progress is not None:
        progress["sweep_total"] = len(contract.chunks)   # one Drex request per page

    # 1) Section sweep: one state per chunk, all categories asked against the cached state.
    sweeps = await asyncio.gather(*[
        drex.decide(ch.text, questions, arm=arm, contract=contract.title, unit=f"chunk{ch.idx}")
        for ch in contract.chunks
    ])
    score = {c: {} for c in categories}           # category -> {chunk idx: p}
    for ch, probs in zip(contract.chunks, sweeps):
        for qid, p in probs.items():
            score[ids[qid]][ch.idx] = p

    # 2) Drill-down: uncertain (chunk, category) pairs are re-asked per paragraph.
    jobs = []
    for ch in contract.chunks:
        unsure = [c for c in categories if config.DRILL_LOW < score[c].get(ch.idx, 0) < config.DRILL_HIGH]
        if not unsure:
            continue
        sub_ids, sub_q = _qset(unsure, definitions, drex)
        for j, (s, e) in enumerate(split_paragraphs(ch)):
            jobs.append((ch.idx, sub_ids, drex.decide(contract.text[s:e], sub_q, arm=arm,
                                                      contract=contract.title, unit=f"chunk{ch.idx}.p{j}")))
    if progress is not None:
        progress["drill_total"] = len(jobs)
    drilled = await asyncio.gather(*[j[2] for j in jobs])
    para_max = {}
    for (cidx, sub_ids, _), probs in zip(jobs, drilled):
        for qid, p in probs.items():
            k = (sub_ids[qid], cidx)
            para_max[k] = max(para_max.get(k, 0.0), p)
    for (cat, cidx), p in para_max.items():
        score[cat][cidx] = p                       # pre-registered: paragraph max replaces chunk score

    out = {}
    for c in categories:
        ranked = sorted(score[c], key=lambda i: -score[c][i])
        out[c] = {"p": score[c][ranked[0]] if ranked else 0.0, "evidence": ranked, "source": "drex"}
    return out, (time.perf_counter() - t0) * 1000


async def run_llm(contract, categories, definitions, llm, chunks=None, arm="llm"):
    t0 = time.perf_counter()
    res = await llm.judge(chunks or contract.chunks, categories, definitions, arm=arm, contract=contract.title)
    out = {c: {"p": None, "pred": res[c][0], "evidence": res[c][1], "source": "llm"} for c in categories}
    return out, (time.perf_counter() - t0) * 1000


def confidence(p, theta):
    return p if p >= theta else 1 - p


async def run_cascade(contract, drex_out, drex_ms, categories, definitions, llm, theta, tau):
    t0 = time.perf_counter()
    unsure = [c for c in categories if confidence(drex_out[c]["p"], theta) < tau]
    out = {c: dict(drex_out[c], pred=drex_out[c]["p"] >= theta) for c in categories}
    if unsure:
        keep = sorted({i for c in unsure for i in drex_out[c]["evidence"][:config.CASCADE_TOPK_CHUNKS]})
        chunks = [ch for ch in contract.chunks if ch.idx in keep]
        llm_out, _ = await run_llm(contract, unsure, definitions, llm, chunks=chunks, arm="cascade")
        out.update(llm_out)
    return out, drex_ms + (time.perf_counter() - t0) * 1000, len(unsure)
