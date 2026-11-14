"""Per-contract latency, tokens and cost for an LLM arm, straight from its ledger (no accuracy involved).
Usage: python tools/ledger_costs.py runs/armA   ->  runs/armA/per_contract.json"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stego import config  # noqa: E402

d = sys.argv[1]
by = defaultdict(lambda: {"calls": 0, "errors": 0, "latency_s": 0.0, "input_tokens": 0, "output_tokens": 0})
for ln in open(os.path.join(d, "ledger.jsonl")):
    r = json.loads(ln)
    if r.get("kind") != "llm":
        continue
    c = by[r["contract"]]
    c["calls"] += 1
    c["errors"] += r.get("status") not in ("ok", "cached")
    c["latency_s"] += r["latency_ms"] / 1000
    c["input_tokens"] += r.get("input_tokens", 0)
    c["output_tokens"] += r.get("output_tokens", 0)
rows = []
for title, c in sorted(by.items()):
    c.update(contract=title, latency_s=round(c["latency_s"], 1),
             cost_usd=round(c["input_tokens"] / 1e6 * config.LLM_PRICE_PER_M_INPUT + c["output_tokens"] / 1e6 * config.LLM_PRICE_PER_M_OUTPUT, 5))
    rows.append(c)
lat = sorted(r["latency_s"] for r in rows)
out = {"model": config.LLM_MODEL, "prices_per_m_tokens": [config.LLM_PRICE_PER_M_INPUT, config.LLM_PRICE_PER_M_OUTPUT], "contracts": len(rows),
       "latency_p50_s": lat[len(lat) // 2] if lat else None, "cost_total_usd": round(sum(r["cost_usd"] for r in rows), 4), "per_contract": rows}
json.dump(out, open(os.path.join(d, "per_contract.json"), "w"), indent=1)
print(f"{d}: {len(rows)} contracts so far | median latency {out['latency_p50_s']} s | cost ${out['cost_total_usd']} (no accuracy computed)")
