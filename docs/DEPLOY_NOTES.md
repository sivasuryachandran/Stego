# Deploy notes: Drex providers

Stego talks to Drex through one client (`stego/drex.py`) and the `/v1/systemone` contract. Switching provider is **env only**, in `.env` (gitignored) or the shell. No keys belong in this file.

| Variable | Nace (default) | DeepInfra |
|---|---|---|
| `DREX_BASE_URL` | `https://console.nace.ai` | `https://api.deepinfra.com` |
| `DREX_MODEL` | `drex-v2.0` | `nace-ai/drex-v2.0` |
| `DREX_API_KEY` | your Nace key (`NACE_API_KEY` also works) | your DeepInfra key |
| `DREX_QUESTIONS_PER_REQ` | `20` (default) | **`10`** |

- **DeepInfra needs `DREX_QUESTIONS_PER_REQ=10`.** It rejects more than 16 questions per request with HTTP 422. Stego sends 20 questions per call by default and splits them into batches of this size.
- `DREX_API_KEY` takes priority over `NACE_API_KEY`, so a provider switch needs no code change.
- If `DREX_MODEL` is set, the app and demo paths use it as is and do not call `GET /v1/models`. The benchmark harness still resolves the model from `/v1/models`.
- The header badge shows the active provider ("via Nace" or "via DeepInfra") next to LIVE or MOCK.
- Published benchmark numbers (`runs/final/results.json`) were measured on Nace. DeepInfra was tried on one 5-page upload through the app (200 OK, about 2 s); it has not been benchmarked.
- Rate limits: Nace uses a 60 s sliding RPM window and an in-flight cap (reported as 8 free, 16 paid). `DREX_MAX_INFLIGHT` sets the client's concurrency. The Live Race waits ("cooling") so it does not exceed the RPM window.
- Nace's host (`console.nace.ai`) sat behind a Vercel bot checkpoint and returned HTML with HTTP 403 for a while on 14 Nov 2026. The client does not recognise this case (see below), so keep the DeepInfra settings ready as a fallback.

Offline check before a demo: `.venv/bin/python scripts/smoke.py` (MOCK Drex, no keys, no network).
