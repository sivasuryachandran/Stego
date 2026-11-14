# Stego

> Contract triage without the big brain.

Stego reads a contract and answers 20 yes/no clause questions (anti-assignment, cap on liability, audit rights, ...) with
**Drex** (Nace's decision model), then plain code aggregates the answers into a review brief. A person confirms the uncertain
ones, and the brief is sealed with **C2PA Content Credentials**. The Drex-only path makes **zero general-purpose
reasoning-LLM calls after ingestion**. An LLM appears only as a benchmark baseline and in the cascade arm.

Hackathon: Drexathon, track **Apex Predator** (hand a frontier-LLM-style task's decisions to Drex and measure speed, cost and accuracy).
Partner tools used: Nace Drex, DeepInfra (the LLM baseline), Adobe Content Credentials (C2PA) and Firefly (mascot).

## How it works
1. **Ingest:** a text PDF or `.txt` is split into chunks (one per page in the app). NDI ingest and scanned PDFs are not wired yet.
2. **Decide (Drex):** a section sweep asks all 20 questions per chunk. Chunks with 0.2 < p < 0.9 get a paragraph drill-down.
3. **Aggregate (plain code):** presence = max p over chunks; evidence = chunks ranked by p. Thresholds θ and τ are calibrated, not guessed.
4. **Triage:** Urgent (a policy list, not ground truth), Found · confirm, Human review (below τ), Auto-cleared. Clauses far below θ read "likely absent".
5. **Human decides:** a reviewer picks Confirm present / Not present / Escalate. Each decision is appended to `runs/live/decisions.jsonl`.
6. **Seal:** the brief PNG is signed with Content Credentials. The seal carries the Drex model and mode, probabilities, evidence pages,
   thresholds, human reviews and a sha256 of the call ledger. It proves who decided from what evidence, not that the decision was right.

Stego routes; a person decides. It never recommends approve or reject: CUAD labels clause presence, not acceptability.

## Install and run
```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/python samples/make_sample.py        # invented demo contract -> samples/sample_vendor_agreement.pdf
.venv/bin/python app.py                        # http://localhost:8000/
```
Upload a PDF, open the clause board, review clauses, then seal the brief. Mock mode is on whenever no Drex key is set.

### Environment variables (names only; put values in `.env`, which is gitignored)
| Name | Purpose |
|---|---|
| `NACE_API_KEY` (or `DREX_API_KEY`) | Drex. Without it the app and harness run **MOCK** Drex (keyword heuristics) and say so in the UI. |
| `DREX_BASE_URL`, `DREX_PATH`, `DREX_MODEL` | Optional overrides. The model is resolved from `GET /v1/models` (prefers `drex-v2.0`). |
| `DREX_PRICE_PER_M_INPUT` | Used for cost per contract. |
| `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | The LLM baseline (arms A and C). Any OpenAI-compatible endpoint, or `anthropic`. |
| `LLM_PRICE_PER_M_INPUT`, `LLM_PRICE_PER_M_OUTPUT`, `LLM_TEMPERATURE`, `LLM_ARM_LABEL` | Cost and labelling for the baseline. |
| `MOCK=1` | Force the offline mock for the harness. |

Copy `.env.example` to `.env` to start. Never commit `.env`.

## Benchmark protocol
- **Data:** official CUAD **test split** (`data/cuad/test.json`, 102 contracts, lawyer-annotated, CC BY 4.0, The Atticus Project).
  Download `data.zip` from github.com/TheAtticusProject/cuad and put `test.json` in `data/cuad/` (not committed).
- **Questions:** 20 categories (`stego/config.py`), each asked with CUAD's own labelling definition.
- **Split:** fixed seed 14. **20 calibration contracts** are used only to pick θ and τ; **82 report contracts** are scored.
- **Frozen thresholds:** θ = 0.48, τ = 0.918, recorded with `frozen_at` in `runs/thresholds.json` before the report run.
  The repository was created after the run, so the commit history does not prove the order. The timestamps in
  `runs/latest/ledger.jsonl` (calibration) and `runs/final/ledger.jsonl` (report) do.
- **Arms:** **A** an LLM reads all chunks and returns JSON; **B** Stego, Drex only; **C** cascade: Drex decides and only low-confidence
  categories go to the LLM, which sees Drex's top-4 chunks; **M** majority-class baseline.
- **Metrics:** accuracy, macro/micro-F1, evidence hit@1/@3 (gold CUAD span inside the predicted chunk), Brier, ECE, selective accuracy,
  p50/p95 latency, cost and LLM calls per contract. Failed runs count as wrong on every category.
- **Receipts:** `runs/<name>/ledger.jsonl` logs every call (model, unit, latency, tokens, probabilities).
- **LLM baseline label:** Qwen3.8-27B via DeepInfra, the organizer-provided System 2 model, in thinking mode. It is an open 27B model, **not** a frontier model.

```bash
MOCK=1 python run_bench.py gate --limit 3 --out runs/smoke   # offline smoke test, no keys needed
python run_bench.py gate --limit 3 --out runs/smoke          # real go/no-go on 3 contracts, all arms
python run_bench.py calib                                    # picks theta and tau on the 20 calibration contracts
python run_bench.py bench --no-cache --out runs/final        # timed run on the 82 report contracts
```
Use `--out` for experiments: the default output is `runs/latest`, which holds the calibration ledger.

## Measured results (CUAD test split, 82 report contracts, from `runs/final/results.json`)
| Drex-only arm (B) | |
|---|---|
| Macro-F1 / micro-F1 | 0.796 / 0.834 |
| Accuracy | 90.5% (flattered: most clauses are absent; the majority-class baseline gets 73.5% accuracy but macro-F1 0.043) |
| Evidence on the right chunk | 94.4% (top 1), 99.5% (top 3) |
| Calibration | Brier 0.072, ECE 0.031 |
| Accuracy at confidence ≥ 0.93 | 96.3% over 1,139 of 1,640 decisions |
| Speed / cost | 6.9 s median per contract, about $0.002 per contract, 0 LLM calls |

**Arms A (LLM alone) and C (cascade) are not in `runs/final` yet.** Until they are merged (`python run_bench.py merge`), this repo
makes no head-to-head claim against the LLM; the Benchmark page shows only B and the majority baseline.

## Content Credentials
```bash
.venv/bin/python fossil.py demo           # seal the latest upload, verify, tamper one pixel, verify again (fails)
.venv/bin/python fossil.py verify FILE.png
```
- Signing uses a generated **TEST** certificate chain in `keys/` (gitignored). Adobe's verifier shows an **untrusted signer**. Production needs a certificate from the C2PA trust list.
- The claim is "modified or stripped after sealing", never who changed it.
- Rehearsal results: a one-pixel tamper fails verification; the in-app **Forger Test** is **simulated** (a second test signer re-signs an edited brief) and is labelled as such.
  A real edit in Photoshop on the web exported a file with **no credentials**, which the app reports as "No credentials".
- `assets/mascot_firefly.png` is a Firefly-generated image embedded as an ingredient. It is a re-saved copy, so it does not carry Firefly's own credentials.

## Limits
- Weakest categories (F1): Warranty Duration 0.50, Uncapped Liability 0.60, Non-Transferable License 0.62, Post-Termination Services 0.64.
- CUAD labels clause presence, not risk or acceptability. The "Urgent" list is a policy flag in `ui/index.html`, not ground truth.
- The benchmark scores yes/no presence on 20 categories of one dataset, English, in plain text. Scanned PDFs and NDI ingest are not wired.
- Mock mode output is not real Drex output. The UI labels it, and mock seals say `mode: mock`.
- The Content Credentials seal uses a test certificate and proves provenance of the file, not the correctness of the decision.
- Not built: Adobe PDF Embed API viewer, Express template.

License: MIT for the code (see `LICENSE`). The CUAD data is not included and keeps its own license.

Data: CUAD, CC BY 4.0, The Atticus Project, https://www.atticusprojectai.org/cuad.
