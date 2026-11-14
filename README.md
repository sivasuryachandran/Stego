# Stego: benchmark harness

> Stego: contract triage without the big brain.

Contract clause triage with **zero general-purpose reasoning LLM calls after ingestion**:
Drex decides, plain code aggregates, the LLM appears only as a baseline and in the cascade arm.

## What it measures
- **Data:** official CUAD **test split** (`data/cuad/test.json`, 102 contracts, lawyer-annotated).
  20 yes/no clause categories (see `stego/config.py`). Each Drex question uses CUAD's **own
  labeling definition** ("Details: ..."), so the questions match the guidelines the annotators used.
- **Split (fixed seed 14):** 20 contracts only for picking thresholds, 82 for the report.
- **Arms:**
  - **A:** a frontier LLM reads all chunks and returns one JSON per contract.
  - **B:** Drex only. A section sweep (20 questions per chunk), then a paragraph drill-down for chunks with 0.2 < p < 0.9. Code aggregates: presence = max p, evidence = chunks ranked by p.
  - **C:** cascade. Drex decides, and only categories with confidence < τ go to the LLM, which sees just Drex's top-4 chunks.
- **Metrics:** accuracy, macro/micro-F1, per-category F1, evidence hit@1/@3 (gold CUAD span inside the
  predicted chunk), Brier, ECE + reliability bins, selective accuracy @80/90/100% coverage,
  "accuracy when confidence ≥ 0.93" (Nace's published calibration claim), p50/p95 wall-clock per contract,
  $ per contract, LLM calls, Drex decisions per contract. **Failed runs count as wrong on every category.**
- **Receipts:** `runs/<name>/ledger.jsonl` logs every call: model, unit, latency, tokens, probabilities.

Why CUAD text and not NDI text for the benchmark: CUAD's gold spans are character offsets into its own
text. Running NDI changes the text, so you'd need fuzzy realignment, which adds label noise. NDI is used in the
live demo pipeline (PDF → sections → page/bbox). Say this on the slide.

## Setup
```bash
pip install -r requirements.txt
# CUAD (official repo): unzip data.zip from github.com/TheAtticusProject/cuad into data/cuad/
export DREX_API_KEY=nace_sk_...            # DREX_BASE_URL defaults to https://drex.nace.ai
export DREX_PRICE_PER_M_INPUT=0.06         # set from Nace's pricing page for the model you get
export LLM_PROVIDER=openai                 # or anthropic
export LLM_MODEL=<current frontier model>  # write the exact id on the results slide
export LLM_API_KEY=...
export LLM_PRICE_PER_M_INPUT=... LLM_PRICE_PER_M_OUTPUT=...
# reasoning models that reject temperature: export LLM_TEMPERATURE=
```
The Drex model is resolved at startup from `GET /v1/models` (prefers drex-v2.0, then drex-max-v1.1, ...).
If the hosted path isn't `/v1/systemone`, the client retries `/v1/decisions`, or you can set `DREX_PATH`.

## Run order (tonight, then freeze)
```bash
MOCK=1 python run_bench.py gate --limit 3     # offline smoke test, no keys needed
python run_bench.py gate --limit 3 --out runs/gate     # real go/no-go on 3 contracts, all arms
python run_bench.py calib                               # picks theta, tau on the 20 calib contracts -> runs/thresholds.json
git commit -am "freeze thresholds"                      # timestamped proof you didn't tune on the report set
python run_bench.py bench --no-cache --out runs/final   # final timed run, 82 contracts
```
`--no-cache` matters for the timed run: the cache is there to save money while iterating, not for latency numbers.

## Go / no-go (printed by `gate`)
- Drex probabilities aren't trivial (std > 0.15)
- Confidence is higher on correct answers than wrong ones (margin > 0.05)
- Drex-only macro-F1 is within 0.15 of the LLM. **If this fails, the headline becomes the cascade (C), not Zero (B).**
  Decide this **before** `bench`, and report all three arms either way.

## Knobs (all in `stego/config.py`; change only before `calib`)
`CHUNK_CHARS`, `DRILL_LOW/HIGH`, `CASCADE_TOPK_CHUNKS`, `TARGET_AUTO_ACCURACY`, `DREX_MAX_INFLIGHT`,
`DREX_QUESTIONS_PER_REQ`, `CONTRACT_CONCURRENCY`.

## App (UI + live pipeline)
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python samples/make_sample.py     # invented demo contract -> samples/sample_vendor_agreement.pdf
.venv/bin/python app.py                     # http://localhost:8000/
```
- Upload a text-based PDF or .txt: pages -> Drex section sweep + drill-down -> plain-code aggregation -> clause board with the PDF opened on the evidence page. One chunk per page.
- No `DREX_API_KEY` = the harness's MOCK Drex (keyword heuristics). The UI shows a warning banner; those probabilities are not real.
- Benchmark/receipts screens read `runs/final` (else `runs/latest`, `runs/gate`); otherwise labeled sample data. `?run=runs/gate` picks a run.
- Uploads land in `runs/live/` (contracts, PDFs, `ledger.jsonl`). NDI ingest and scanned PDFs are not wired yet.
- "Urgent" is a policy list in `ui/index.html` (`URGENT`), not ground truth.

## The Fossil Record (Adobe Content Credentials)
Brief page -> **Seal & export brief** signs the rendered brief PNG with C2PA Content Credentials. The seal carries the
Drex model and mode, probabilities, evidence pages, thresholds, human reviews and a sha256 of `runs/live/ledger.jsonl`.
It proves who decided from what evidence, not that the decision was right.
```bash
.venv/bin/python fossil.py demo           # seal latest upload, verify, tamper one pixel, verify again (fails)
.venv/bin/python fossil.py verify FILE.png
```
- Signing uses a generated **TEST** certificate chain in `keys/` (gitignored). Adobe's verify site (contentcredentials.org/verify)
  will show an untrusted signer. Production needs a certificate from the C2PA trust list.
- Adobe's verify page shows standard fields only; the full decision record is shown in the app's Fossil Record panel from the same seal.
- Mock Drex output is sealed with `mode: mock` and the UI says so. Seals on benchmark/sample contracts are disabled (no ledger).
- Not built yet: Adobe PDF Embed API viewer (needs a free client ID), Firefly mascot as an ingredient (`assets/`), Express template.

## Drex credentials (live mode)
Copy `.env.example` to `.env` (gitignored) and set `NACE_API_KEY`. `stego/config.py` loads `.env` (real env vars win) and points at
`https://console.nace.ai`; the client sends `X-Nace-Client: stego/0.1` and resolves the model from `GET /v1/models`
(`drex-v2.0` first). With a key present the app and harness run live Drex; without one they fall back to MOCK.
The LLM baseline (arms A/C, the race's right side) still needs `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`.

## Human decisions (Stego routes, a person decides)
In the Workspace, a reviewer enters a name and picks **Confirm present**, **Not present** or **Escalate** for a clause. Each decision is appended to
`runs/live/decisions.jsonl` (reviewer, time, Drex probability, evidence page, Drex model). Sealing a brief reads that ledger, so the Content Credentials
seal records both Drex's call and the human's. Stego never recommends approve or reject: CUAD labels presence, not acceptability. Queues: Urgent (policy flag),
Found · confirm, Human review (below τ), Auto-cleared. The default τ is not calibrated; run `calib` on real data before quoting a human-workload number.
