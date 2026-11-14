"""Stego benchmark.

  python run_bench.py gate  --limit 3            # go/no-go on 3 contracts (all arms)
  python run_bench.py calib                      # pick theta/tau on the 20 calibration contracts, then FREEZE
  python run_bench.py bench --no-cache           # final timed run on the 82 report contracts
"""
import argparse
import asyncio
import json
import os
import statistics
import time

from stego import config
from stego.arms import confidence, run_cascade, run_drex, run_llm
from stego.data import load, split
from stego.drex import DrexClient
from stego.ledger import Cache, Ledger
from stego.llm import LLMClient
from stego.metrics import pick_thresholds, score


def majority_row(calib, sel, cats):
    """Free baseline: for each category always predict its more common label in the CALIBRATION split."""
    maj = {c: sum(ct.gold_present[c] for ct in calib) * 2 > len(calib) for c in cats}
    res = {ct.title: {"out": {c: {"pred": maj[c], "evidence": [], "source": "baseline"} for c in cats}, "ms": 0.0} for ct in sel}
    s = score("M Majority-class baseline (calibration split)", res, sel, cats)
    for k in ("evidence_hit@1", "evidence_hit@3", "latency_p50_ms", "latency_p95_ms"):
        s[k] = None
    s.update({"cost_per_contract_usd": 0.0, "llm_calls": 0, "majority_present": sorted(c for c in cats if maj[c])})
    return s


async def run_arm(name, contracts, fn):
    sem = asyncio.Semaphore(config.CONTRACT_CONCURRENCY)
    results, t0 = {}, time.perf_counter()

    async def one(ct):
        async with sem:
            try:
                out, ms, *extra = await fn(ct)
                results[ct.title] = {"out": out, "ms": ms, "extra": extra}
            except Exception as e:  # failed runs are kept and scored as errors
                results[ct.title] = {"out": None, "ms": None, "error": str(e)[:300]}
                print(f"  [{name}] FAILED {ct.title[:60]}: {str(e)[:120]}")

    await asyncio.gather(*[one(c) for c in contracts])
    print(f"  [{name}] {len(contracts)} contracts in {time.perf_counter() - t0:.1f}s")
    return results


def costs(drex_tok, llm_in, llm_out, n):
    d = drex_tok / 1e6 * config.DREX_PRICE_PER_M_INPUT
    l = llm_in / 1e6 * config.LLM_PRICE_PER_M_INPUT + llm_out / 1e6 * config.LLM_PRICE_PER_M_OUTPUT
    return {"drex_input_tokens": drex_tok, "llm_input_tokens": llm_in, "llm_output_tokens": llm_out,
            "cost_total_usd": d + l, "cost_per_contract_usd": (d + l) / max(n, 1)}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["gate", "calib", "bench", "baseline", "merge"])
    ap.add_argument("--src", default="runs/armA", help="merge: the run directory to merge from")
    ap.add_argument("--arms", default="llm,drex,cascade")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--out", default="runs/latest")
    ap.add_argument("--thresholds", default="runs/thresholds.json")
    a = ap.parse_args()
    arms = a.arms.split(",")
    os.makedirs(a.out, exist_ok=True)

    contracts, defs = load()
    calib, report = split(contracts)
    cats = config.CATEGORIES
    if a.mode == "baseline":        # no API calls: add the majority-class row to an existing results.json
        res = json.load(open(os.path.join(a.out, "results.json")))
        titles = set(res["contracts"]); sel = [c for c in report if c.title in titles]
        res["summary"] = [x for x in res["summary"] if not x["arm"].startswith("M")] + [majority_row(calib, sel, cats)]
        json.dump(res, open(os.path.join(a.out, "results.json"), "w"), indent=2)
        print_table(res["summary"]); return
    if a.mode == "merge":           # fold another run (e.g. arm A run separately) into --out, replacing rows with the same arm letter
        src = json.load(open(os.path.join(a.src, "results.json"))); dst = json.load(open(os.path.join(a.out, "results.json")))
        letters = {x["arm"][0] for x in src["summary"]}
        dst["summary"] = [x for x in dst["summary"] if x["arm"][0] not in letters] + src["summary"]
        dst["llm_model"] = src.get("llm_model") or dst.get("llm_model")
        json.dump(dst, open(os.path.join(a.out, "results.json"), "w"), indent=2)
        for name in ("predictions.jsonl", "ledger.jsonl"):
            with open(os.path.join(a.out, name), "a") as f:
                f.write(open(os.path.join(a.src, name)).read())
        print_table(dst["summary"]); return
    ledger = Ledger(os.path.join(a.out, "ledger.jsonl"))
    cache = Cache("runs/cache.sqlite", enabled=not a.no_cache)
    drex, llm = DrexClient(ledger, cache), LLMClient(ledger, cache)
    model = await drex.resolve_model()
    print(f"Drex model: {model} | LLM: {config.LLM_PROVIDER}/{config.LLM_MODEL or '(unset)'} | mock={config.MOCK}")

    try:
        if a.mode == "calib":
            sel = calib[: a.limit] if a.limit else calib
            res = await run_arm("drex-calib", sel, lambda ct: run_drex(ct, cats, defs, drex, arm="calib"))
            rows = [(r["out"][c]["p"], ct.gold_present[c]) for ct in sel
                    for c in cats if (r := res[ct.title])["out"]]
            theta, tau = pick_thresholds(rows, config.TARGET_AUTO_ACCURACY)
            json.dump({"theta": theta, "tau": tau, "model": model, "n_calib": len(sel),
                       "target_auto_accuracy": config.TARGET_AUTO_ACCURACY, "frozen_at": time.ctime()},
                      open(a.thresholds, "w"), indent=2)
            print(f"FROZEN theta={theta:.2f} tau={tau:.3f} -> {a.thresholds}")
            return

        if a.mode == "gate":
            sel, theta, tau = report[: (a.limit or 3)], 0.5, 0.9
        else:
            th = json.load(open(a.thresholds))
            theta, tau = th["theta"], th["tau"]
            sel = report[: a.limit] if a.limit else report
        print(f"theta={theta} tau={tau} | {len(sel)} contracts | {sum(len(c.chunks) for c in sel)} chunks")

        summary, all_res = [], {}
        if "drex" in arms or "cascade" in arms:
            d0 = drex.input_tokens; n0 = drex.decisions
            r = await run_arm("drex", sel, lambda ct: run_drex(ct, cats, defs, drex))
            all_res["drex"] = r
            s = score("B Stego (Drex only)", r, sel, cats, theta)
            s.update(costs(drex.input_tokens - d0, 0, 0, len(sel)))
            s["drex_decisions"] = drex.decisions - n0
            s["drex_decisions_per_contract"] = s["drex_decisions"] / len(sel)
            s["llm_calls"] = 0
            summary.append(s)
        if "llm" in arms:
            c0, i0, o0 = llm.calls, llm.in_tokens, llm.out_tokens
            r = await run_arm("llm", sel, lambda ct: run_llm(ct, cats, defs, llm))
            all_res["llm"] = r
            s = score(config.LLM_ARM_LABEL, r, sel, cats)
            s.update(costs(0, llm.in_tokens - i0, llm.out_tokens - o0, len(sel)))
            s["llm_calls"] = llm.calls - c0
            summary.append(s)
        if "cascade" in arms:
            c0, i0, o0 = llm.calls, llm.in_tokens, llm.out_tokens
            dres = all_res["drex"]

            async def casc(ct):
                d = dres[ct.title]
                if d["out"] is None:
                    raise RuntimeError("drex stage failed")
                return await run_cascade(ct, d["out"], d["ms"], cats, defs, llm, theta, tau)

            r = await run_arm("cascade", sel, casc)
            all_res["cascade"] = r
            s = score("C Drex-first cascade", r, sel, cats, theta)
            drex_tok = next((x["drex_input_tokens"] for x in summary if x["arm"].startswith("B")), 0)
            s.update(costs(drex_tok, llm.in_tokens - i0, llm.out_tokens - o0, len(sel)))
            s["llm_calls"] = llm.calls - c0
            sent = sum(x["extra"][0] for x in r.values() if x["out"] is not None)
            s["categories_sent_to_llm"] = sent
            s["share_decided_by_drex"] = 1 - sent / (len(sel) * len(cats))
            summary.append(s)

        summary.append(majority_row(calib, sel, cats))
        json.dump({"theta": theta, "tau": tau, "drex_model": model, "llm_model": config.LLM_MODEL,
                   "categories": cats, "contracts": [c.title for c in sel], "summary": summary},
                  open(os.path.join(a.out, "results.json"), "w"), indent=2)
        with open(os.path.join(a.out, "predictions.jsonl"), "w") as f:
            for arm, res in all_res.items():
                for ct in sel:
                    rr = res.get(ct.title, {})
                    f.write(json.dumps({"arm": arm, "contract": ct.title, "ms": rr.get("ms"),
                                        "error": rr.get("error"), "gold": ct.gold_present,
                                        "gold_chunks": {k: sorted(v) for k, v in ct.gold_chunks.items()},
                                        "out": rr.get("out")}) + "\n")
        print_table(summary)
        if a.mode == "gate":
            gate_checks(all_res, sel, cats, theta, summary)
    finally:
        await drex.close()
        await llm.close()


def print_table(summary):
    keys = ["accuracy", "macro_f1", "micro_f1", "evidence_hit@1", "evidence_hit@3", "brier", "ece",
            "selective_acc@80", "selective_acc@90", "selective_acc@100", "acc_when_conf>=0.93",
            "latency_p50_ms", "latency_p95_ms", "cost_per_contract_usd", "llm_calls",
            "drex_decisions_per_contract", "share_decided_by_drex", "failed_contracts"]
    print("\n" + "metric".ljust(30) + "".join(s["arm"][:26].ljust(28) for s in summary))
    for k in keys:
        vals = [s.get(k) for s in summary]
        if all(v is None for v in vals):
            continue
        fmt = lambda v: "-" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))
        print(k.ljust(30) + "".join(fmt(v).ljust(28) for v in vals))


def gate_checks(all_res, sel, cats, theta, summary):
    print("\nGO / NO-GO")
    d = all_res.get("drex", {})
    ps = [o[c]["p"] for r in d.values() if (o := r["out"]) for c in cats]
    if ps:
        sd = statistics.pstdev(ps)
        print(f"  Drex probabilities non-trivial (std {sd:.3f} > 0.15): {'PASS' if sd > 0.15 else 'FAIL'}")
        right, wrong = [], []
        for ct in sel:
            o = d[ct.title]["out"]
            if not o:
                continue
            for c in cats:
                conf = confidence(o[c]["p"], theta)
                (right if (o[c]["p"] >= theta) == ct.gold_present[c] else wrong).append(conf)
        if right and wrong:
            ok = statistics.mean(right) - statistics.mean(wrong) > 0.05
            print(f"  Uncertainty tracks errors (conf right {statistics.mean(right):.2f} vs wrong "
                  f"{statistics.mean(wrong):.2f}): {'PASS' if ok else 'FAIL'}")
    acc = {s["arm"][0]: s["macro_f1"] for s in summary}
    if "A" in acc and "B" in acc:
        gap = acc["A"] - acc["B"]
        print(f"  Drex-only macro-F1 within 0.15 of LLM (gap {gap:+.3f}): {'PASS' if gap <= 0.15 else 'FAIL'}"
              "  -> if FAIL, lead with the cascade (C), not Drex-only (B)")
    print("  Evidence mapping: check evidence_hit@3 above; NDI page mapping is checked in the demo pipeline.")


if __name__ == "__main__":
    asyncio.run(main())
