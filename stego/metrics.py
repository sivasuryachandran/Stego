"""Scoring against CUAD gold. Failed contracts count as wrong on every category."""
import statistics


def pick_thresholds(rows, target):
    """rows: list of (p, gold). theta maximizes F1; tau = lowest confidence with covered acc >= target."""
    best = (0.5, -1)
    for t in [x / 100 for x in range(30, 96)]:
        tp = sum(1 for p, g in rows if p >= t and g)
        fp = sum(1 for p, g in rows if p >= t and not g)
        fn = sum(1 for p, g in rows if p < t and g)
        f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0
        if f1 > best[1]:
            best = (t, f1)
    theta = best[0]
    conf = sorted(((p if p >= theta else 1 - p), (p >= theta) == g) for p, g in rows)
    tau = 1.0
    for i in range(len(conf)):
        covered = conf[i:]
        if sum(ok for _, ok in covered) / len(covered) >= target:
            tau = conf[i][0]
            break
    return theta, tau


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def score(arm, results, contracts, categories, theta=None):
    """results: {title: {"out": {...} or None, "ms": float}}."""
    per_cat = {c: [0, 0, 0, 0] for c in categories}  # tp fp fn tn
    rows, ev1, ev3, ev_n, lat, failed = [], 0, 0, 0, [], 0
    for ct in contracts:
        r = results.get(ct.title)
        out = r["out"] if r else None
        if out is None:
            failed += 1
        else:
            lat.append(r["ms"])
        for c in categories:
            gold = ct.gold_present[c]
            if out is None:
                pred, p = (not gold), None
            else:
                o = out[c]
                pred = o["pred"] if "pred" in o else o["p"] >= theta
                p = o.get("p")
            k = per_cat[c]
            if pred and gold: k[0] += 1
            elif pred and not gold: k[1] += 1
            elif gold: k[2] += 1
            else: k[3] += 1
            if p is not None and out is not None and out[c].get("source") == "drex":
                rows.append((p, gold, pred))
            if out is not None and pred and gold and ct.gold_chunks[c]:
                ev_n += 1
                evid = out[c]["evidence"]
                ev1 += int(bool(evid) and evid[0] in ct.gold_chunks[c])
                ev3 += int(any(i in ct.gold_chunks[c] for i in evid[:3]))
    cat_f1 = {c: _prf(*v[:3])[2] for c, v in per_cat.items()}
    tot = [sum(v[i] for v in per_cat.values()) for i in range(4)]
    micro_p, micro_r, micro_f1 = _prf(*tot[:3])
    res = {
        "arm": arm,
        "contracts": len(contracts), "failed_contracts": failed,
        "decisions_scored": sum(tot),
        "accuracy": (tot[0] + tot[3]) / sum(tot),
        "macro_f1": statistics.mean(cat_f1.values()),
        "micro_precision": micro_p, "micro_recall": micro_r, "micro_f1": micro_f1,
        "evidence_hit@1": ev1 / ev_n if ev_n else None,
        "evidence_hit@3": ev3 / ev_n if ev_n else None,
        "latency_p50_ms": statistics.median(lat) if lat else None,
        "latency_p95_ms": (sorted(lat)[int(0.95 * (len(lat) - 1))] if lat else None),
        "per_category_f1": cat_f1,
    }
    if rows and theta is not None:
        res.update(calibration(rows, theta))
    return res


def calibration(rows, theta, bins=10):
    """rows: (p_yes, gold, pred). Brier, ECE on p_yes, selective accuracy by confidence."""
    brier = statistics.mean((p - g) ** 2 for p, g, _ in rows)
    ece, rel = 0.0, []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, g) for p, g, _ in rows if lo <= p < hi or (b == bins - 1 and p == 1.0)]
        if sel:
            mp, fr = statistics.mean(p for p, _ in sel), statistics.mean(g for _, g in sel)
            ece += len(sel) / len(rows) * abs(mp - fr)
            rel.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(sel), "mean_p": mp, "frac_yes": fr})
    conf = sorted((((p if p >= theta else 1 - p), pred == g) for p, g, pred in rows), reverse=True)
    sel = {}
    for cov in (0.8, 0.9, 1.0):
        k = max(1, int(round(cov * len(conf))))
        sel[f"selective_acc@{int(cov * 100)}"] = sum(ok for _, ok in conf[:k]) / k
    hi = [ok for c, ok in conf if c >= 0.93]
    return {"brier": brier, "ece": ece, "reliability": rel, **sel,
            "acc_when_conf>=0.93": (sum(hi) / len(hi)) if hi else None, "n_conf>=0.93": len(hi)}
