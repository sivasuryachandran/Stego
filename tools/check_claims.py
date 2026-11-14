"""Check that numbers quoted in README.md match runs/final/results.json. Usage: python tools/check_claims.py"""
import json
import os
import sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
res = json.load(open(os.path.join(root, "runs/final/results.json")))
readme = open(os.path.join(root, "README.md")).read()
S = {s["arm"][0]: s for s in res["summary"]}
f3, pc = (lambda v: f"{v:.3f}"), (lambda v: f"{v * 100:.1f}%")
want = []
for L, name in (("B", "B"), ("A", "A"), ("C", "C"), ("M", "M")):
    s = S[L]
    want += [(f"{name} macro-F1", f3(s["macro_f1"])), (f"{name} micro-F1", f3(s["micro_f1"])), (f"{name} accuracy", pc(s["accuracy"]))]
    if s.get("evidence_hit@1") is not None:
        want += [(f"{name} evidence@1", pc(s["evidence_hit@1"]))]
    if s.get("latency_p50_ms"):
        want += [(f"{name} p50 time", f"{s['latency_p50_ms'] / 1000:.1f} s")]
    want += [(f"{name} failed", None)] if False else []
b = S["B"]
want += [("B evidence@3", pc(b["evidence_hit@3"])), ("B Brier", f3(b["brier"])), ("B ECE", f3(b["ece"])), ("B acc@conf>=0.93", pc(b["acc_when_conf>=0.93"])),
         ("B cost", f"${b['cost_per_contract_usd']:.4f}"), ("A cost", f"${S['A']['cost_per_contract_usd']:.4f}"), ("C cost", f"${S['C']['cost_per_contract_usd']:.4f}"),
         ("n conf>=0.93", f"{b['n_conf>=0.93']:,}"), ("decisions", f"{b['decisions_scored']:,}"), ("theta", str(res["theta"])), ("tau", f"{res['tau']:.3f}")]
sa, sc = res["sensitivity"], res["sensitivity_C"]
want += [("sens A macro", f3(sa["A"]["macro_f1"])), ("sens B(79) macro", f3(sa["B"]["macro_f1"])), ("sens C macro", f3(sc["C"]["macro_f1"])), ("sens B(80) macro", f3(sc["B"]["macro_f1"])),
         ("sens A acc", pc(sa["A"]["accuracy"])), ("sens B(79) acc", pc(sa["B"]["accuracy"])), ("sens C acc", pc(sc["C"]["accuracy"])), ("sens contracts A", str(sa["contracts"])), ("sens contracts C", str(sc["contracts"]))]
for c, v in sorted(b["per_category_f1"].items(), key=lambda x: x[1])[:4]:
    want.append((f"weakest {c}", f"{c} {v:.2f}"))
bad = [(k, v) for k, v in want if v not in readme]
print(f"{len(want) - len(bad)} of {len(want)} README numbers match runs/final/results.json")
for k, v in bad:
    print("  NOT FOUND in README:", k, "=", v)
ratio_t, ratio_c = S["A"]["latency_p50_ms"] / b["latency_p50_ms"], S["A"]["cost_per_contract_usd"] / b["cost_per_contract_usd"]
print(f"ratios from the data: speed {ratio_t:.1f}x, cost {ratio_c:.1f}x  (README says roughly 20x and 8x)")
sys.exit(1 if bad else 0)
