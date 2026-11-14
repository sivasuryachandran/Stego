"""An LLM note-helper (kind="intern") row must be counted as an LLM call and kept out of the Drex ledger rows and hash.
No network, no keys.  Run: .venv/bin/python tests/test_fossil_intern.py"""
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import c2pa  # noqa: E402
import fossil  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append(ok); print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def main():
    tmp = tempfile.mkdtemp(prefix="stego_fossil_test_")
    fossil.LIVE, fossil.BRIEFS = tmp, os.path.join(tmp, "briefs")
    ledger = os.path.join(tmp, "ledger.jsonl")
    drex = [json.dumps({"kind": "drex", "contract": "T", "unit": f"c{i}", "status": "ok"}) for i in range(2)]
    open(ledger, "w").write("\n".join(drex) + "\n")
    ct = {"id": "abc123", "title": "T", "pages": 1, "mock": False,
          "clauses": {"Audit Rights": {"p": 0.97, "evidence": [{"page": 1, "text": "the auditor may inspect"}]}}}
    try:
        base = fossil.build_record(ct, "drex-v2.0", 0.48, 0.918, True, {}, ledger)
        check("no intern row: 0 LLM calls, 2 contract rows", base["reasoning_llm_calls"] == 0 and base["ledger"]["contract_rows"] == 2)
        open(ledger, "a").write(json.dumps({"kind": "intern", "contract": "T", "clause": "Audit Rights", "status": "unavailable"}) + "\n")
        un = fossil.build_record(ct, "drex-v2.0", 0.48, 0.918, True, {}, ledger)
        check("an Intern call that never started (unavailable) is not counted", un["reasoning_llm_calls"] == 0)
        open(ledger, "a").write(json.dumps({"kind": "intern", "contract": "T", "clause": "Audit Rights", "status": "ok"}) + "\n")
        rec = fossil.build_record(ct, "drex-v2.0", 0.48, 0.918, True, {}, ledger)
        check("one intern row: reasoning_llm_calls == 1", rec["reasoning_llm_calls"] == 1)
        check("intern row excluded from contract_rows, row hash and ledger hash",
              rec["ledger"]["contract_rows"] == 2 and rec["ledger"]["contract_rows_sha256"] == base["ledger"]["contract_rows_sha256"]
              and rec["ledger"]["file_sha256"] == base["ledger"]["file_sha256"])
        data, name = None, None
        rec2, name, data = fossil.seal_contract(ct, "drex-v2.0", 0.48, 0.918, True, {})
        v = fossil.verify(data)
        check("sealed brief still verifies as authentic", v.get("verdict") == "authentic", f"verdict={v.get('verdict')}")
        path = os.path.join(tmp, "briefs", name)
        d = json.loads(c2pa.Reader(path).json()); m = d["manifests"][d["active_manifest"]]
        desc = json.dumps(m["assertions"])
        check("seal says 1 LLM call and shows no Drex-only claim", rec2["reasoning_llm_calls"] == 1 and "1 reasoning-LLM calls" in desc and "0 reasoning-LLM calls" not in desc and "NOT a Drex-only" in desc.replace("not a Drex-only", "NOT a Drex-only"))
    except Exception as e:
        check("test ran without an exception", False, f"{type(e).__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if results and all(results) else "SOME CASES FAILED")
    sys.exit(0 if results and all(results) else 1)


if __name__ == "__main__":
    main()
