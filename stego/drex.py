"""Async Drex client (TypeSafe System One wire format).

Request : {"model", "state", "questions": {qid: {"type": "noul", "instructions": ...}}}
Response: {"answers": {qid: {"type": "noul", "noul": p_yes}}, "usage": {"input_tokens": ...}}
"""
import asyncio
import os
import random
import re
import time

import httpx

from . import config

_MOCK_KW = {
    "Anti-Assignment": r"assign", "License Grant": r"licen[cs]e", "Cap On Liability": r"liabilit",
    "Audit Rights": r"audit|inspect", "Revenue/Profit Sharing": r"royalt|revenue|profit",
    "Exclusivity": r"exclusiv", "Insurance": r"insur", "Minimum Commitment": r"minimum",
    "Termination For Convenience": r"terminat", "Post-Termination Services": r"after (the )?terminat",
    "Renewal Term": r"renew", "Change Of Control": r"change (of|in) control|merger",
    "Covenant Not To Sue": r"not to sue|challenge", "Non-Compete": r"compet",
    "Ip Ownership Assignment": r"intellectual property|owner", "Non-Transferable License": r"non-?transfer",
    "Rofr/Rofo/Rofn": r"first refusal|first offer", "Liquidated Damages": r"liquidated",
    "Uncapped Liability": r"unlimited|gross negligence", "Warranty Duration": r"warrant",
}


BLOCKED_MSG = ("Blocked by the host (HTML 403, possibly a bot checkpoint). This is not an API-key problem. "
               "Switch provider with DREX_BASE_URL.")
RETRY_CAP_S = 60   # total time spent retrying 429/5xx responses before failing with a clear message


class DrexClient:
    def __init__(self, ledger, cache):
        self.ledger, self.cache = ledger, cache
        self.sem = asyncio.Semaphore(config.DREX_MAX_INFLIGHT)
        self.path = config.DREX_PATH
        self.http = httpx.AsyncClient(
            base_url=config.DREX_BASE_URL, timeout=60,
            headers={"Authorization": f"Bearer {config.DREX_API_KEY}", "X-Nace-Client": "stego/0.1"},
        )
        self.decisions = 0
        self.requests_done = 0
        self.input_tokens = 0

    async def close(self):
        await self.http.aclose()

    async def resolve_model(self):
        """Use a model this key can actually call: env override, else first preferred id in GET /v1/models."""
        if config.MOCK:
            return config.DREX_MODEL
        r = await self.http.get("/v1/models")
        r.raise_for_status()
        body = r.json()
        rows = (body.get("models") or body.get("data") or []) if isinstance(body, dict) else body
        avail = [m.get("name") or m.get("id") for m in rows]
        prefs = ([config.DREX_MODEL] if os.getenv("DREX_MODEL") else []) + config.DREX_MODEL_PREFS
        for m in prefs:
            if m in avail:
                config.DREX_MODEL = m
                return m
        raise RuntimeError(f"No preferred Drex model available. /v1/models returned: {avail}")

    async def ensure_model(self):
        """App and demo paths: if DREX_MODEL is set in the environment use it as is (no GET /v1/models). Benchmark keeps resolve_model()."""
        if config.MOCK or os.getenv("DREX_MODEL"):
            return config.DREX_MODEL
        return await self.resolve_model()

    @staticmethod
    def question(category, definition):
        return {
            "type": "noul",
            "instructions": (
                f'Does this contract text contain a "{category}" clause? '
                f"Definition: {definition} Answer yes only if this text itself contains such a clause."
            ),
        }

    async def decide(self, state, questions, *, arm, contract, unit):
        """questions: {qid: question}. Returns ({qid: p_yes}, meta). Splits into batches if needed."""
        items = list(questions.items())
        size = config.DREX_QUESTIONS_PER_REQ
        batches = [dict(items[i:i + size]) for i in range(0, len(items), size)]
        results = await asyncio.gather(*[
            self._one(state, b, arm=arm, contract=contract, unit=unit) for b in batches
        ])
        probs = {}
        for r in results:
            probs.update(r)
        return probs

    async def _one(self, state, questions, *, arm, contract, unit):
        payload = {"model": config.DREX_MODEL, "state": state, "questions": questions}
        key = self.cache.key("drex", payload)
        cached = self.cache.get(key)
        t0 = time.perf_counter()
        if cached is not None:
            probs, usage, status = cached["probs"], cached["usage"], "cached"
        elif config.MOCK:
            await asyncio.sleep(random.uniform(0.15, 0.3))
            probs = {}
            for qid, q in questions.items():
                cat = re.search(r'"(.+?)" clause', q["instructions"]).group(1)
                hit = re.search(_MOCK_KW.get(cat, cat), state, re.I) is not None
                probs[qid] = min(0.99, max(0.01, (0.8 if hit else 0.1) + random.gauss(0, 0.12)))
            usage, status = {"input_tokens": len(state) // 4 * len(questions)}, "mock"
        else:
            probs, usage, status = await self._post(payload)
            if status == "ok":
                self.cache.put(key, {"probs": probs, "usage": usage})
        ms = (time.perf_counter() - t0) * 1000
        n_ok = len(probs) if status != "error" else 0
        self.decisions += n_ok
        self.requests_done += 1
        self.input_tokens += usage.get("input_tokens", 0)
        self.ledger.log(kind="drex", model=config.DREX_MODEL, arm=arm, contract=contract, unit=unit, status=status,
                        n_questions=len(questions), latency_ms=round(ms, 1),
                        input_tokens=usage.get("input_tokens", 0), probs=probs, error=usage.get("error"))
        if status == "error":
            raise RuntimeError(f"Drex failed for {contract} {unit}: {usage.get('error')}")
        return probs

    async def _post(self, payload):
        delay = 1.0
        t_start = time.monotonic()
        for attempt in range(10):
            async with self.sem:
                try:
                    r = await self.http.post(self.path, json=payload)
                except httpx.HTTPError as e:
                    r, err = None, repr(e)
            if r is not None and r.status_code == 404 and self.path == "/v1/systemone":
                self.path = "/v1/decisions"          # alternate wire path used by some hosts
                continue
            if r is not None and (r.status_code == 403 or (r.status_code == 200 and r.text.lstrip()[:9].lower().startswith(("<!doctype", "<html")))):
                return {}, {"error": BLOCKED_MSG}, "error"          # a host or bot-checkpoint block, not an API-key problem: never retried (429 and 5xx keep their retries, HTML body or not)
            if r is not None and r.status_code == 200:
                try:
                    body = r.json()
                except ValueError:
                    return {}, {"error": "Drex returned HTTP 200 with a body that is not JSON. Check DREX_BASE_URL and DREX_PATH, or switch provider with DREX_BASE_URL."}, "error"
                probs = {}
                for qid, a in body.get("answers", {}).items():
                    if "noul" in a:
                        probs[qid] = float(a["noul"])
                    elif "probabilities" in a:     # tolerate a choice-style yes/no answer
                        probs[qid] = float(a["probabilities"].get("true", a["probabilities"].get("yes", 0)))
                return probs, body.get("usage", {}), "ok"
            if r is not None:
                err = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code not in (408, 429, 500, 502, 503, 504):
                    break
            wait = delay + random.random()
            if r is not None:                                  # honor the server's Retry-After when it sends one
                try:
                    ra = r.headers.get("retry-after-ms")
                    wait = max(wait, float(ra) / 1000 if ra else float(r.headers.get("retry-after", 0)))
                except ValueError:
                    pass
            wait = min(wait, 30)
            if r is not None and time.monotonic() - t_start + wait > RETRY_CAP_S:
                return {}, {"error": f"Drex kept answering HTTP {r.status_code}; gave up after {RETRY_CAP_S} s of retrying. Wait a minute and retry, or lower DREX_MAX_INFLIGHT."}, "error"
            await asyncio.sleep(wait)
            delay = min(delay * 2, 20)
        return {}, {"error": err}, "error"
