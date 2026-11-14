"""Offline smoke test (MOCK Drex, no keys, no network, no paid calls).
Run it with the project's venv:  .venv/bin/python scripts/smoke.py

It copies the code into a temporary folder and runs the app there, so it never touches runs/live,
runs/final, .env or keys/. Checks: app starts, upload returns clause decisions, the ledger gets new
entries, a sealed brief verifies as authentic. Exit code 0 only if every check passes."""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""), flush=True)
    return ok


def call(base, path, data=None, headers=None):
    req = urllib.request.Request(base + path, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    tmp = tempfile.mkdtemp(prefix="stego_smoke_")
    proc = None
    try:
        for item in ("app.py", "fossil.py", "stego", "ui", "assets"):       # code only: no .env, keys/, data/ or run outputs
            src = os.path.join(ROOT, item)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(tmp, item), ignore=shutil.ignore_patterns("__pycache__", "vendor"))
            elif os.path.exists(src):
                shutil.copy(src, tmp)
        os.makedirs(os.path.join(tmp, "runs"))
        shutil.copy(os.path.join(ROOT, "runs", "thresholds.json"), os.path.join(tmp, "runs"))   # read-only copy
        sample = os.path.join(ROOT, "samples", "sample_vendor_agreement.pdf")
        if not os.path.exists(sample):
            subprocess.run([sys.executable, os.path.join(ROOT, "samples", "make_sample.py")], check=True, cwd=ROOT)
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
        env.update(MOCK="1", PORT=str(port))
        proc = subprocess.Popen([sys.executable, "app.py"], cwd=tmp, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        base = f"http://127.0.0.1:{port}"
        up = False
        for _ in range(40):
            try:
                st = call(base, "/api/state"); up = True; break
            except (urllib.error.URLError, ConnectionError):
                time.sleep(0.25)
        if not check("app starts (MOCK)", up and st.get("mode") == "mock", f"mode={st.get('mode') if up else 'no response'}"):
            return
        before = len(st.get("ledger", []))
        data = open(sample, "rb").read()
        ct = call(base, "/api/analyze", data, {"X-Filename": "sample_vendor_agreement.pdf"})
        clauses = ct.get("clauses") or {}
        check("upload returns clause decisions", len(clauses) == 20 and all("p" in c for c in clauses.values()), f"{len(clauses)} clauses")
        after = len(call(base, "/api/state").get("ledger", []))
        check("ledger gets new entries", after > before, f"{before} -> {after}")
        sealed = call(base, "/api/seal", json.dumps({"id": ct["id"]}).encode(), {"Content-Type": "application/json"})
        png = urllib.request.urlopen(base + sealed["url"], timeout=60).read()
        v = call(base, "/api/verify", png, {"Content-Type": "image/png"})
        check("sealed brief verifies as authentic", v.get("verdict") == "authentic", f"verdict={v.get('verdict')}")
    except Exception as e:
        check("smoke test ran without an exception", False, f"{type(e).__name__}: {str(e)[:150]}")
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL PASS" if all(results) else "SOME CHECKS FAILED")
    sys.exit(0 if results and all(results) else 1)


if __name__ == "__main__":
    main()
