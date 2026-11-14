"""Sensitivity check (NOT the pre-registered result): score arms A and B on the contracts where arm A completed.
Failed (timed-out) contracts count as wrong in the pre-registered result; here they are left out of both arms.
Usage: python tools/sensitivity.py runs/final runs/armA   -> adds a 'sensitivity' entry to <final>/results.json"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stego import config  # noqa: E402
from stego.data import load, split  # noqa: E402
from stego.metrics import score  # noqa: E402

final, arm_a = sys.argv[1], sys.argv[2]
cs, _ = load()
_, report = split(cs)
res = json.load(open(os.path.join(final, "results.json")))
read = lambda path, arm: {r["contract"]: r for r in map(json.loads, open(path)) if r["arm"] == arm}
A, B = read(os.path.join(arm_a, "predictions.jsonl"), "llm"), read(os.path.join(final, "predictions.jsonl"), "drex")
subset = [c for c in report if A.get(c.title, {}).get("out") is not None]
failed = [c.title for c in report if A.get(c.title, {}).get("out") is None]
mk = lambda pr: {c.title: {"out": pr[c.title]["out"], "ms": pr[c.title]["ms"]} for c in subset}
a, b = score("A", mk(A), subset, config.CATEGORIES), score("B", mk(B), subset, config.CATEGORIES, res["theta"])
pick = lambda s: {k: round(s[k], 4) for k in ("macro_f1", "micro_f1", "accuracy")}
res["sensitivity"] = {"label": "NOT the pre-registered result: arms A and B scored only on the contracts where arm A completed",
                      "contracts": len(subset), "left_out_failed_in_A": failed, "A": pick(a), "B": pick(b)}
json.dump(res, open(os.path.join(final, "results.json"), "w"), indent=2)
print(json.dumps(res["sensitivity"], indent=1)[:700])
