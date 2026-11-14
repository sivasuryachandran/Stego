"""Build ui/replay/race_replay.json: one REAL recorded race, taken from the finished benchmark (read-only).
Takes a report contract where arm B (Drex only) and arm A (the Qwen LLM) both completed, closest to the median
time of each, and stores the recorded wall-clock times and both sides' answers. Nothing here is simulated.
Usage: python tools/make_replay.py   (needs data/cuad/test.json for the page counts; the output file is committed)"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from stego.data import load, split  # noqa: E402

res = json.load(open(os.path.join(ROOT, "runs/final/results.json")))
read = lambda arm: {r["contract"]: r for r in map(json.loads, open(os.path.join(ROOT, "runs/final/predictions.jsonl"))) if r["arm"] == arm}
B, A = read("drex"), read("llm")
b_med = next(s for s in res["summary"] if s["arm"].startswith("B"))["latency_p50_ms"]
a_med = next(s for s in res["summary"] if s["arm"].startswith("A"))["latency_p50_ms"]
cs, _ = load()
_, report = split(cs)
cands = [c for c in report if B.get(c.title, {}).get("out") and A.get(c.title, {}).get("out") and B[c.title].get("ms") and A[c.title].get("ms")]
score = lambda c: abs(math.log(B[c.title]["ms"] / b_med)) + abs(math.log(A[c.title]["ms"] / a_med))
th = res["theta"]
pick = min(cands, key=score)
b, a = B[pick.title], A[pick.title]
clauses = {c: {"p": round(o["p"], 4), "page": (o["evidence"][0] + 1) if o["evidence"] else None} for c, o in b["out"].items()}
present = {c: bool(o["pred"]) for c, o in a["out"].items()}
agree = sum((clauses[c]["p"] >= th) == present[c] for c in clauses)
out = {"recorded": True, "source": "runs/final/predictions.jsonl, arms drex (B) and llm (A); a real run from the benchmark, not simulated",
       "title": pick.title, "pages": len(pick.chunks), "stego_ms": round(b["ms"]), "llm_ms": round(a["ms"]),
       "stego_median_ms": round(b_med), "llm_median_ms": round(a_med), "agree": agree, "of": len(clauses),
       "drex_model": res["drex_model"], "llm_model": res.get("llm_model"), "theta": th, "clauses": clauses, "present": present}
os.makedirs(os.path.join(ROOT, "ui", "replay"), exist_ok=True)
json.dump(out, open(os.path.join(ROOT, "ui", "replay", "race_replay.json"), "w"), indent=1)
print(f"{pick.title[:60]} | {out['pages']} chunks | Stego {out['stego_ms']/1000:.1f} s vs LLM {out['llm_ms']/1000:.1f} s | agree {agree}/{len(clauses)}")
