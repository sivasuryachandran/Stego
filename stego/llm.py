"""Frontier-LLM baseline: one structured-JSON call over the same chunks Drex sees."""
import asyncio
import uuid
import json
import random
import re
import time

import httpx

from . import config

SYSTEM = (
    "You are a contract review assistant. For each clause category, decide whether the contract "
    "contains such a clause, using the given definition, and list the chunk ids that contain it. "
    "Return only JSON."
)


def build_prompt(chunks, categories, definitions):
    cat_lines = "\n".join(f'- "{c}": {definitions[c]}' for c in categories)
    body = "\n\n".join(f"[CHUNK {ch.idx}]\n{ch.text}" for ch in chunks)
    schema = '{"<category>": {"present": true|false, "chunks": [<chunk ids>]}, ...}'
    return (
        f"Clause categories:\n{cat_lines}\n\nReturn JSON exactly in this shape, one key per category:\n"
        f"{schema}\n\nContract (split into chunks):\n\n{body}"
    )


def parse(text, categories):
    m = re.search(r"\{.*\}", text, re.S)
    obj = json.loads(m.group(0)) if m else {}
    out = {}
    for c in categories:
        v = obj.get(c, {})
        out[c] = (bool(v.get("present", False)), [int(x) for x in v.get("chunks", []) if str(x).isdigit()])
    return out


class LLMClient:
    def __init__(self, ledger, cache, profile=None):
        """profile (optional): override the LLM settings for this client only, e.g. the Live Race can use a faster model than the benchmark baseline.
        Default (None) reads config.LLM_*, exactly as before."""
        self.ledger, self.cache = ledger, cache
        p = profile or {}
        self.provider = p.get("provider", config.LLM_PROVIDER)
        self.model = p.get("model", config.LLM_MODEL)
        self.base_url = p.get("base_url", config.LLM_BASE_URL)
        self.api_key = p.get("api_key", config.LLM_API_KEY)
        self.temperature = p.get("temperature", config.LLM_TEMPERATURE)
        self.fail_fast_429 = p.get("fail_fast_429", False)   # Live Race: a rate-limit/quota answer ends the call at once instead of retrying for about a minute
        self.http = httpx.AsyncClient(timeout=300)
        self.calls = 0
        self.in_tokens = 0
        self.out_tokens = 0

    async def close(self):
        await self.http.aclose()

    async def judge(self, chunks, categories, definitions, *, arm, contract):
        prompt = build_prompt(chunks, categories, definitions)
        if str(arm).startswith("race"):   # unique prefix so provider-side prompt caching can't speed up a repeated contract
            prompt = f"Run id: {uuid.uuid4().hex}\n\n" + prompt
        key = self.cache.key("llm", self.provider, self.model, prompt)
        cached = self.cache.get(key)
        t0 = time.perf_counter()
        if cached is not None:
            text, usage, status = cached["text"], cached["usage"], "cached"
        elif config.MOCK:
            await asyncio.sleep(random.uniform(2, 4))
            text = json.dumps({c: {"present": random.random() < 0.4, "chunks": [chunks[0].idx]} for c in categories})
            usage, status = {"in": len(prompt) // 4, "out": 400}, "mock"
        else:
            text, usage, status = await self._call(prompt)
            if status == "ok":
                self.cache.put(key, {"text": text, "usage": usage})
        ms = (time.perf_counter() - t0) * 1000
        self.calls += 1
        self.in_tokens += usage.get("in", 0)
        self.out_tokens += usage.get("out", 0)
        self.ledger.log(kind="llm", arm=arm, contract=contract, status=status, model=self.model,
                        n_categories=len(categories), latency_ms=round(ms, 1),
                        input_tokens=usage.get("in", 0), output_tokens=usage.get("out", 0), error=usage.get("error"))
        if status == "error":
            raise RuntimeError(f"LLM failed for {contract}: {usage.get('error')}")
        try:
            return parse(text, categories)
        except Exception as e:  # unparseable output counts as a failed run
            raise RuntimeError(f"LLM JSON parse failed for {contract}: {e}")

    async def _call(self, prompt):
        delay = 2.0
        for _ in range(5):
            try:
                if self.provider == "anthropic":
                    body = {"model": self.model, "max_tokens": config.LLM_MAX_TOKENS, "system": SYSTEM,
                            "messages": [{"role": "user", "content": prompt}]}
                    if self.temperature != "":
                        body["temperature"] = float(self.temperature)
                    r = await self.http.post(
                        "https://api.anthropic.com/v1/messages", json=body,
                        headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"})
                    if r.status_code == 200:
                        j = r.json()
                        text = "".join(b.get("text", "") for b in j["content"] if b.get("type") == "text")
                        u = j.get("usage", {})
                        return text, {"in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0)}, "ok"
                else:
                    body = {"model": self.model, "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": SYSTEM},
                                         {"role": "user", "content": prompt}]}
                    if self.temperature != "":
                        body["temperature"] = float(self.temperature)
                    r = await self.http.post(
                        f"{self.base_url}/chat/completions", json=body,
                        headers={"Authorization": f"Bearer {self.api_key}"})
                    if r.status_code == 200:
                        j = r.json()
                        u = j.get("usage", {})
                        return (j["choices"][0]["message"]["content"],
                                {"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0)}, "ok")
                err = f"HTTP {r.status_code}: {r.text[:300]}"
                if self.fail_fast_429 and r.status_code == 429:
                    break
                if r.status_code not in (408, 429, 500, 502, 503, 504, 529):
                    break
            except httpx.HTTPError as e:
                err = repr(e)
            await asyncio.sleep(delay + random.random())
            delay *= 2
        return "", {"error": err}, "error"
