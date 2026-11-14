"""LLM client 429 behaviour: the benchmark path keeps its retries; the Live Race profile fails fast.  No network, no keys.
Run: .venv/bin/python tests/test_llm_429.py"""
import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["MOCK"] = "0"
import httpx  # noqa: E402
from stego import config  # noqa: E402
from stego.llm import LLMClient  # noqa: E402

config.MOCK = False
results = []


async def call(profile, handler):
    slept = [0.0]
    real = asyncio.sleep

    async def fake(d): slept[0] += d
    asyncio.sleep = fake
    try:
        c = LLMClient(None, None, profile)
        c.http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        out = await c._call("prompt")
        await c.http.aclose()
        return out, slept[0]
    finally:
        asyncio.sleep = real


def check(name, ok, detail=""):
    results.append(ok); print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))


n = []
def h429(req): n.append(1); return httpx.Response(429, text="quota")
(_, usage, status), slept = asyncio.run(call({"fail_fast_429": True}, h429))
check("race profile: a 429 ends the call after ONE request", status == "error" and len(n) == 1 and slept == 0, f"{len(n)} request, {slept:.0f} s waited")
n.clear()
(_, usage, status), slept = asyncio.run(call(None, h429))
check("default (benchmark) profile still retries 429s", status == "error" and len(n) == 5 and slept > 30, f"{len(n)} requests, {slept:.0f} s of backoff")
ok = {"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 3, "completion_tokens": 4}}
(text, usage, status), _ = asyncio.run(call({"fail_fast_429": True}, lambda req: httpx.Response(200, json=ok)))
check("a normal 200 still works with the race profile", status == "ok" and text == "{}" and usage == {"in": 3, "out": 4})
print("ALL PASS" if all(results) else "SOME CASES FAILED")
sys.exit(0 if all(results) else 1)
