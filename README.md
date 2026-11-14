# Stego

> Contract triage without the big brain.

Stego reads a contract and answers 20 yes/no clause questions (anti-assignment, cap on liability, audit rights, ...) with
**Drex** (Nace's decision model), then plain code aggregates the answers into a review brief. A person confirms the uncertain
ones, and the brief is sealed with **C2PA Content Credentials**. The Drex-only path makes **zero general-purpose
reasoning-LLM calls after ingestion**. An LLM appears only as a benchmark baseline and in the cascade arm.

Hackathon: Drexathon, track **Apex Predator** (hand a frontier-LLM-style task's decisions to Drex and measure speed, cost and accuracy).
Partner tools used: Nace Drex, DeepInfra (the LLM baseline), Adobe Content Credentials (C2PA) and Firefly (mascot).

## How it works
1. **Ingest:** a text PDF or `.txt` is split into chunks (one per page in the app). Scanned PDFs are not supported.
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
Upload a PDF, open the clause board, review clauses, then seal the brief. `.venv/bin/python scripts/smoke.py` runs an offline end-to-end check (MOCK Drex, temporary folder, no keys). Mock mode is on whenever no Drex key is set.

### Run it: Drex provider (env only, no code change)
The app header badge shows the active provider ("Drex via Nace" or "Drex via DeepInfra") next to the LIVE or MOCK badge.

| | Nace (default) | DeepInfra |
|---|---|---|
| `DREX_BASE_URL` | `https://console.nace.ai` (default) | `https://api.deepinfra.com` |
| `DREX_MODEL` | `drex-v2.0` | `nace-ai/drex-v2.0` |
| `DREX_API_KEY` (or `NACE_API_KEY` for Nace) | your Nace key | your DeepInfra key |
| `DREX_QUESTIONS_PER_REQ` | `20` (default) | `10` (DeepInfra rejects more than 16 questions per request) |

When `DREX_MODEL` is set, the app and demo paths use it as is and never call `GET /v1/models`. The benchmark harness still resolves the model from `/v1/models`.
Both providers serve the same `/v1/systemone` contract. `DREX_API_KEY` takes priority over `NACE_API_KEY`. The published benchmark numbers were measured on Nace.

### Environment variables (names only; put values in `.env`, which is gitignored)
| Name | Purpose |
|---|---|
| `DREX_API_KEY` (or `NACE_API_KEY`) | Drex. `DREX_API_KEY` wins if both are set. Without either, the app and harness run **MOCK** Drex (keyword heuristics) and say so in the UI. |
| `DREX_BASE_URL`, `DREX_PATH`, `DREX_MODEL` | Optional overrides. If `DREX_MODEL` is set, the app uses it as is; otherwise (and always in the benchmark harness) the model is resolved from `GET /v1/models`, preferring `drex-v2.0`. |
| `DREX_QUESTIONS_PER_REQ`, `DREX_MAX_INFLIGHT` | Questions per request (default 20; DeepInfra needs 10) and concurrent requests (default 8). See `docs/DEPLOY_NOTES.md`. |
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

### All four arms (pre-registered scoring: a failed contract counts as wrong on every category)
| | **B** Stego (Drex only) | **C** cascade | **A** open 27B LLM (Qwen3.8-27B) | **M** majority-class |
|---|---|---|---|---|
| Macro-F1 | **0.796** | 0.741 | 0.738 | 0.043 |
| Micro-F1 | **0.834** | 0.769 | 0.762 | 0.219 |
| Accuracy | **90.5%** | 85.9% | 85.7% | 73.5% |
| Evidence on the right chunk (top 1) | **94.4%** | 92.2% | 90.1% | – |
| Median time per contract | **6.9 s** | 135.5 s | 137.7 s | – |
| Cost per contract | **$0.0022** | $0.0186 | $0.0183 | $0 |
| LLM calls (82 contracts) | 0 | 77 | 82 | 0 |
| Failed contracts | 0 | 2 | 3 | 0 |

How to read this:
- **Stego (Drex only) is not more accurate than the LLM in any way we can show.** Its lead in the table comes mostly from the contracts where the LLM
  timed out (300 s read timeout on a thinking model; A: 3 contracts, C: 2). Two **labelled, not pre-registered** sensitivity checks are stored in
  `runs/final/results.json` and shown on the Benchmark page: on the 79 contracts where A completed, macro-F1 is **A 0.798 vs B 0.788** (accuracy 89.0% vs 90.6%);
  on the 80 where C completed, **C 0.778 vs B 0.788** (accuracy 88.1% vs 90.5%). That is roughly a tie on accuracy.
- **What the data does support:** about equal accuracy at roughly **20x the speed and 8x lower cost**, plus calibrated probabilities and an abstention rule.
- **The cascade did not help.** C is not better than Drex-only, and it costs as much as the LLM alone.
- **The LLM is an open 27B model in thinking mode, not a frontier model.** A frontier model, or Qwen with thinking off, would be faster; no frontier arm was run.
- The failed-contract rule was not changed after seeing results. Arm C had a pre-declared cutoff of 1:15 PM; it finished at 12:32, so the cutoff was not used.
- Per-contract latency and cost come from the ledgers: `runs/final/armA_per_contract.json`, `runs/final/armC_per_contract.json` (`tools/ledger_costs.py`).
  `tools/sensitivity.py` reproduces the arm A check.

## App features beyond the benchmark (none of this is in `runs/final`)
These are app-path features. The benchmark, its chunker and the frozen thresholds are untouched.

- **Warm cache and "Re-upload as v2".** App uploads use a content-defined, page-bounded chunker and a SQLite cache keyed on a hash of
  (Drex model, chunk text, questions). Every upload shows its cache counts (exact hits, similar-text hits, fresh Drex calls) next to its time, labelled WARM CACHE when any hit exists. Re-upload a revised contract and unchanged chunks are answered from the cache; the Workspace shows
  chunks reused / re-asked and the time, labelled **warm cache**. A second, approximate tier reuses answers for chunks at least 90% similar
  (MinHash over 5-word shingles, numbers ignored, same questions and model). Similar-text answers can differ from a fresh Drex answer, so they are counted separately.
  Measured in our own test runs: on an 80-page contract with new numbers and two edited paragraphs, 4.1 s against 11.2 s fresh, with no yes/no flips against fresh Drex (0 of 20)
  and a largest probability difference of 0.021. A contract with party names throughout reused nothing. The CUAD test split has no genuine near-duplicate contracts, so we cannot cite a real-world hit rate.
  The cold first upload is the honest speed number; a v2 is fast only because v1 ran first.
- **Contract-type templates (not benchmarked).** Lease, loan and health insurance clause sets (10 clauses each, `stego/templates.py`), chosen with the **Type** dropdown
  (default: commercial, the CUAD 20; "Auto-detect with Drex" is opt-in and needs at least 0.60). There are no gold labels for these clauses, so they have no accuracy claim.
  The θ and τ thresholds used for them are the CUAD ones, calibrated on the CUAD 20 and **uncalibrated for these templates**. We checked them only on three invented samples (`samples/make_template_samples.py`): detection was correct on all three and 30 of 30 clauses matched what we built in.
  The sealed brief says "not benchmarked". Urgent flags are policy lists, not ground truth.
- **Draft reviewer note (Intern), optional.** A button that runs `intern -p` (nace-ai/intern, headless) to draft a two to three sentence reviewer note from a clause's probability and evidence text.
  It is labelled "Drafted by Intern (LLM), not a Drex decision"; Stego's decisions come from Drex only. It sends that clause's evidence text to an LLM (DeepInfra), and the Intern subprocess gets exactly two secrets in its environment, `NACE_API_KEY` and `DEEPINFRA_API_KEY` (plus PATH/HOME); no other variables are passed. It is capped at 20 s and fails soft. Each draft is an LLM call: it is logged as `kind="intern"`, counted in the seal's `reasoning_llm_calls`, left out of the Drex row count and ledger hash, and the seal then says the brief is not Drex-only.
  Intern needs Linux or macOS, so on Windows it runs in a Docker image: `docker build -t stego-intern tools/intern`. Without Docker the button shows a message and nothing else changes.
  Intern is used in the product only through this button.

## Content Credentials
```bash
.venv/bin/python fossil.py demo           # seal the latest upload, verify, tamper one pixel, verify again (fails)
.venv/bin/python fossil.py verify FILE.png
```
- Signing uses a generated **TEST** certificate chain in `keys/` (gitignored). Adobe's verifier shows the file as **"Unrecognized"** ("The Content Credential issuer couldn't be recognized"). Production needs a certificate from the C2PA trust list.
- The claim is "modified or stripped after sealing", never who changed it.
- Rehearsal results: a one-pixel tamper fails verification; the in-app **Forger Test** is **simulated** (a second test signer re-signs an edited brief) and is labelled as such.
  A real edit in Photoshop on the web exported a file with **no credentials**, which the app reports as "No credentials".
- **Tested on Adobe's verify page** (contentcredentials.org/verify, 14 Nov 2026, a sealed brief of the invented sample contract, test certificate). It showed:
  status **"Unrecognized"** with the banner "The Content Credential issuer couldn't be recognized. This file may not come from where it claims to";
  Process: App or device used **"Stego Fossil Record Signer (TEST)"**, Actions **"Created: The asset was created"**;
  Ingredients: **"Stego mascot (Adobe Firefly)"** shown with a Content Credential icon and its date (re-tested Nov 14, 2026 with the original Adobe-signed mascot; the earlier run used a re-saved copy that showed "No Content Credential"); Adobe's page does not expand the ingredient's own issuer in this view; About this Content Credential: **"Issued by: Stego (TEST ONLY)"**.
  Adobe's page shows standard fields only: the decision record (model, probabilities, evidence pages, human decisions, ledger hash) is read by Stego's own verifier from the same seal.
- `assets/mascot_firefly.png` is the original file downloaded from Adobe Firefly, unmodified, with its own Content Credentials (generator Adobe Firefly, issuer Adobe Inc.). Every seal embeds it as an ingredient and draws it in the seal box.

## Limits
- Weakest categories (F1): Warranty Duration 0.50, Uncapped Liability 0.60, Non-Transferable License 0.62, Post-Termination Services 0.64.
- CUAD labels clause presence, not risk or acceptability. The "Urgent" list is a policy flag in `ui/index.html`, not ground truth.
- **Tested in Chrome only** (real Chrome, 14 Nov 2026). Safari and Firefox were not tested.
- **Text-based PDFs and .txt only.** Scanned PDFs are not supported. The benchmark scores yes/no presence on 20 categories of one dataset, in English plain text.
- **The LLM baseline is an open 27B model, not a frontier model:** Qwen3.8-27B via DeepInfra, in thinking mode (arm A, and the LLM step of arm C). Its slowness is mostly reasoning tokens, so a frontier model, or Qwen with thinking off, would narrow the speed gap. No frontier arm was run.
- **One source for the Drex-only time:** every Drex-only timing quoted here is the median in `runs/final/results.json` (arm B, `latency_p50_ms` = 6,945 ms, i.e. **6.9 s**). The Live Race and the recorded replay show single runs of one contract, not that median.
- **The Forger Test button is simulated:** a second test signer stands in for an editing tool. It is labelled that way in the app. A real Photoshop export carried no credentials at all and is reported as such.
- Mock mode output is not real Drex output. The UI labels it, and mock seals say `mode: mock`.
- The Content Credentials seal uses a test certificate and proves provenance of the file, not the correctness of the decision.
- Not built: Adobe PDF Embed API viewer, Express template.

License: MIT for the code (see `LICENSE`). The CUAD data is not included and keeps its own license.

Data: CUAD, CC BY 4.0, The Atticus Project, https://www.atticusprojectai.org/cuad.
