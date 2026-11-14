"""Error-path tests for stego/drex.py: no network, no keys, no sleeping.  Run: .venv/bin/python tests/test_drex_errors.py"""
import asyncio
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["MOCK"] = "0"
import httpx  # noqa: E402
from stego import config, drex  # noqa: E402

config.MOCK = False
PAYLOAD = {"model": "drex-v2.0", "state": "x", "questions": {"q": {"type": "noul", "instructions": "?"}}}
results = []


class _Ledger:
    def log(self, **k): pass


async def run(handler):
    """Run DrexClient._post against a mock transport; fake clock so sleeps cost nothing."""
    clock = [0.0]
    real_sleep, real_mono = asyncio.sleep, time.monotonic

    async def fake_sleep(d): clock[0] += d
    asyncio.sleep, time.monotonic = fake_sleep, lambda: clock[0]
    try:
        c = drex.DrexClient(_Ledger(), None)
        c.http = httpx.AsyncClient(base_url="http://mock", transport=httpx.MockTransport(handler))
        out = await c._post(PAYLOAD)
        await c.http.aclose()
        return out, clock[0], c
    finally:
        asyncio.sleep, time.monotonic = real_sleep, real_mono


def check(name, ok, detail=""):
    results.append(ok); print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


def main():
    calls = []

    def h403(req): calls.append(1); return httpx.Response(403, text="<!DOCTYPE html><html><title>Vercel Security Checkpoint</title></html>")
    (probs, usage, status), _, _ = asyncio.run(run(h403))
    check("403 HTML body gives the clear error, no retry", status == "error" and usage["error"] == drex.BLOCKED_MSG and len(calls) == 1, f"calls={len(calls)}")

    def h200html(req): return httpx.Response(200, text="<html>checkpoint</html>")
    (probs, usage, status), _, _ = asyncio.run(run(h200html))
    check("200 with an HTML body gives the clear error", status == "error" and "Blocked by the host" in usage["error"])

    def h200bad(req): return httpx.Response(200, text="not json at all")
    (probs, usage, status), _, _ = asyncio.run(run(h200bad))
    check("200 with a non-JSON body gives a clear error (no JSONDecodeError)", status == "error" and "not JSON" in usage["error"])

    n429 = []

    def h429(req): n429.append(1); return httpx.Response(429, text="slow down")
    (probs, usage, status), elapsed, _ = asyncio.run(run(h429))
    check("429 sequence stops at the 60 s cap with a clear message", status == "error" and "429" in usage["error"] and "60 s" in usage["error"] and elapsed <= 60,
          f"{len(n429)} attempts, {elapsed:.0f} s of simulated waiting")

    body = {"answers": {"q": {"type": "noul", "noul": 0.93}}, "usage": {"input_tokens": 50}}

    def h200(req): return httpx.Response(200, json=body)
    (probs, usage, status), _, _ = asyncio.run(run(h200))
    check("normal 200 still returns the parsed result", status == "ok" and probs == {"q": 0.93} and usage == {"input_tokens": 50})

    seq = iter([httpx.Response(429, text="x"), httpx.Response(200, json=body)])
    (probs, usage, status), _, _ = asyncio.run(run(lambda req: next(seq)))
    check("a single 429 then 200 still succeeds", status == "ok" and probs == {"q": 0.93})

    seq = iter([httpx.Response(503, text="<html>Service Unavailable</html>"), httpx.Response(200, json=body)])
    (probs, usage, status), _, _ = asyncio.run(run(lambda req: next(seq)))
    check("503 with an HTML body is retried, then a 200 succeeds", status == "ok" and probs == {"q": 0.93})

    n502 = []

    def h502(req): n502.append(1); return httpx.Response(502, text="<!DOCTYPE html><html>Bad Gateway</html>")
    (probs, usage, status), elapsed, _ = asyncio.run(run(h502))
    check("502 with an HTML body repeated stops at the 60 s cap with the cap message", status == "error" and "502" in usage["error"] and "60 s" in usage["error"] and "Blocked" not in usage["error"] and len(n502) > 1 and elapsed <= 60,
          f"{len(n502)} attempts, {elapsed:.0f} s simulated")

    print("ALL PASS" if all(results) else "SOME CASES FAILED")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
