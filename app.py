"""Stego app server: serves ui/, analyzes uploaded contracts with the real Drex pipeline, serves benchmark runs.

  .venv/bin/python app.py            ->  http://localhost:8000/
Without DREX_API_KEY it runs the harness's MOCK Drex (keyword heuristics) and the UI says so loudly.
"""
import asyncio
import json
import mimetypes
import os
import re
import datetime
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from stego import config
from stego.appchunk import chunk_hash, chunk_text_of, content_chunks
from stego.arms import run_drex, run_llm
from stego.data import Chunk, Contract, chunk_text
from stego.defs import CUES, DEFINITIONS
from stego.drex import DrexClient
from stego.ledger import Cache, Ledger
from stego.llm import LLMClient

try:
    import fossil  # C2PA Content Credentials ("the Fossil Record")
except Exception:  # optional dependency
    fossil = None

ROOT = os.path.dirname(os.path.abspath(__file__))
LIVE = os.path.join(ROOT, "runs", "live")
os.makedirs(os.path.join(LIVE, "uploads"), exist_ok=True)
os.makedirs(os.path.join(LIVE, "contracts"), exist_ok=True)
if not config.DREX_API_KEY:
    config.MOCK = True
LEDGER = Ledger(os.path.join(LIVE, "ledger.jsonl"))
MAX_BYTES = 40 * 1024 * 1024


def thresholds():
    p = os.path.join(ROOT, "runs", "thresholds.json")
    if os.path.exists(p):
        t = json.load(open(p))
        return t["theta"], t["tau"], True
    return 0.5, 0.9, False


def extract_pages(name, data):
    if name.lower().endswith(".pdf"):
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [(pg.extract_text() or "").strip() for pg in reader.pages]
        if not any(pages):
            raise ValueError("No extractable text (scanned PDF). Scanned PDFs are not supported: upload a text-based PDF.")
        return pages
    text = data.decode("utf-8", errors="replace")
    if "\f" in text:
        return [p.strip() for p in text.split("\f")]
    return [c.text for c in chunk_text(text)]


def build_contract(title, pages):
    """One chunk per page so the Drex evidence maps straight to a page number."""
    text, chunks = "", []
    for i, pg in enumerate(pages):
        start = len(text)
        text += pg + "\n"
        chunks.append(Chunk(i, start, len(text), pg + "\n"))
    return Contract(title, text, chunks)


def build_contract_content(title, pages):
    """App path only: content-defined chunks (see stego/appchunk.py). contract.meta[i] = [(page, line), ...]."""
    text, chunks, meta = "", [], []
    for i, lines in enumerate(content_chunks(pages)):
        t = chunk_text_of(lines)
        chunks.append(Chunk(i, len(text), len(text) + len(t), t))
        text += t
        meta.append(lines)
    ct = Contract(title, text, chunks)
    ct.meta = meta
    return ct


class CountingCache(Cache):
    """Counts answers served from the warm cache vs sent to Drex."""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.hits = self.misses = 0

    def get(self, k):
        v = super().get(k)
        if v is None:
            self.misses += 1
        else:
            self.hits += 1
        return v


def evidence_page(ct, idx, category):
    lines = ct.meta[idx]
    cue = re.compile(CUES.get(category, category), re.I)
    return next((pg for pg, ln in lines if cue.search(ln)), lines[0][0])


def clip(text, limit):
    """Cut at a sentence end if possible, else at a word boundary, never mid-word."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    i = max(cut.rfind(". "), cut.rfind("; "))
    if i > limit * 0.5:
        return cut[:i + 1]
    sp = cut.rfind(" ")
    return cut[:sp if sp > 0 else limit] + "…"


def locate(page_text, category, limit=420):
    """Plain-code evidence paragraph inside the page Drex ranked: first sentence matching the category cue."""
    flat = re.sub(r"\s*\n\s*", " ", page_text)
    sents = re.split(r"(?<=[.;])\s+", flat)
    cue = re.compile(CUES.get(category, category), re.I)
    for i, s in enumerate(sents):
        if cue.search(s):
            seg = s
            if len(seg) < 160 and i + 1 < len(sents):
                seg += " " + sents[i + 1]
            return clip(seg, limit)
    return clip(flat, limit)


DECISIONS = os.path.join(LIVE, "decisions.jsonl")   # append-only ledger of human decisions
DEC_LOCK = threading.Lock()
DECISION_KINDS = {"confirmed", "not_present", "escalated"}


def latest_decisions():
    """{contract_id: {clause: row}}: the last row per clause wins; the file keeps every decision."""
    out = {}
    if os.path.exists(DECISIONS):
        for ln in open(DECISIONS, encoding="utf-8"):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            out.setdefault(r["contract_id"], {})[r["clause"]] = r
    return out


JOBS = {}   # upload job id -> {"phase", "pct", "detail", ...} for the progress bar; "loop"/"task" let it be cancelled


def _job_progress(drex, prog, n_pages):
    """Map real work done to a 0-100 bar: 10-15 read, 15-65 page sweep, 65-95 drill-down, 95-100 save."""
    sweep = max(1, prog.get("sweep_total", n_pages))
    done = drex.requests_done
    if "drill_total" not in prog:
        k = min(done, sweep)
        return {"phase": "sweep", "pct": 15 + 50 * k / sweep, "detail": f"Sweeping pages: {k} / {sweep}"}
    tot = max(1, prog["drill_total"])
    k = min(max(0, done - sweep), tot)
    return {"phase": "drill", "pct": 65 + 30 * k / tot, "detail": f"Drilling into uncertain paragraphs: {k} / {prog['drill_total']}"}


async def run_analysis(title, pages, pdf_name, job, parent=None):
    task = asyncio.ensure_future(analyze(title, pages, pdf_name, job, parent))
    if job is not None:
        job["loop"], job["task"] = asyncio.get_running_loop(), task
    return await task


async def analyze(title, pages, pdf_name, job=None, parent=None):
    theta, tau, _ = thresholds()
    ledger_start = LEDGER.f.tell()
    cache = CountingCache(os.path.join(LIVE, "cache.sqlite"), enabled=True)   # warm content-hash cache: key = hash(model, chunk text, questions)
    drex = DrexClient(LEDGER, cache)
    await drex.ensure_model()
    ct = build_contract_content(title, pages)
    parent_rec = None
    if parent:
        pp = os.path.join(LIVE, "contracts", re.sub(r"[^a-z0-9]", "", parent.lower()) + ".json")
        if os.path.exists(pp):
            parent_rec = json.load(open(pp))
    cats = config.CATEGORIES
    prog = {}

    async def ticker():
        while True:
            if job is not None:
                p = _job_progress(drex, prog, len(pages))
                job.update(phase=p["phase"], pct=max(job.get("pct", 0), p["pct"]), detail=p["detail"])
            await asyncio.sleep(0.15)

    tk = asyncio.ensure_future(ticker())
    try:
        out, ms = await run_drex(ct, cats, DEFINITIONS, drex, arm="live", progress=prog)
    finally:
        tk.cancel()
        await drex.close()
    clauses = {}
    for c in cats:
        ev = []
        for idx in out[c]["evidence"][:3]:
            ev.append({"page": evidence_page(ct, idx, c), "chunk": idx, "text": locate(ct.chunks[idx].text, c)})
        clauses[c] = {"p": round(out[c]["p"], 4), "evidence": ev}
    cid = uuid.uuid4().hex[:10]
    rec = {"id": cid, "title": title, "pages": len(pages), "ms": round(ms), "pdf": f"/runs/live/uploads/{pdf_name}" if pdf_name else None,
           "live": True, "drex_decisions": drex.decisions, "analyzed_at": time.time(), "mock": config.MOCK, "clauses": clauses,
           "chunk_hashes": [chunk_hash(c.text) for c in ct.chunks], "version": 1, "parent_id": None,
           "cache": {"requests_cached": cache.hits, "requests_sent": cache.misses}}
    if parent_rec:
        old = set(parent_rec.get("chunk_hashes") or [])
        reused = sum(1 for h in rec["chunk_hashes"] if h in old)
        rec.update(version=(parent_rec.get("version") or 1) + 1, parent_id=parent_rec["id"])
        rec["cache"].update(label="warm cache", chunks_total=len(ct.chunks), chunks_reused=reused, chunks_reasked=len(ct.chunks) - reused,
                            parent_ms=parent_rec.get("ms"), parent_chunks=len(old))
    json.dump(rec, open(os.path.join(LIVE, "contracts", cid + ".json"), "w"))
    if job is not None:
        job.update(phase="done", pct=100, detail="Fossil unearthed")
    return rec



# ---------------------------------------------------------------- live race: Stego (Drex only) vs the LLM baseline
RACES = {}


DREX_RPM_BUDGET = int(os.getenv("DREX_RPM_BUDGET", "100"))   # conservative: Drex counts every request per account in a sliding 60 s window


def recent_drex_requests(now=None):
    """Timestamps of Drex requests in the last 60 s, read from the ledger (analyze + races share the account's limit)."""
    now = now or time.time()
    path = os.path.join(LIVE, "ledger.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8").read().splitlines()[-2500:]:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("kind") == "drex" and r.get("ts", 0) > now - 60:
            out.append(r["ts"])
    return sorted(out)


RACE_LLM_CAP_S = int(os.getenv("RACE_LLM_CAP_S", "300"))   # a race never waits longer than this for the LLM side
RACE_RT = {}   # race id -> {"loop", "tasks"} so a race can be cancelled from another thread


def cancel_races(except_id=None):
    """Stop every running race (e.g. after a page refresh) so old races can't steal the Drex rate limit."""
    n = 0
    for rid, rt in list(RACE_RT.items()):
        R = RACES.get(rid)
        if rid != except_id and R and not R.get("finished"):
            for t in rt["tasks"]:
                rt["loop"].call_soon_threadsafe(t.cancel)
            n += 1
    return n


def _race_main(rid, title, pages):
    R = RACES[rid]

    async def go():
        ct = build_contract(title, pages)
        cats = config.CATEGORIES
        cache = Cache(os.path.join(LIVE, "cache.sqlite"), enabled=False)
        drex, llm = DrexClient(LEDGER, cache), LLMClient(LEDGER, cache)
        try:
            await drex.ensure_model()
        except Exception as e:
            R["stego"].update(status="error", error=f"{type(e).__name__}: {str(e)[:160]}")
        R["drex_model"] = config.DREX_MODEL
        need = int(len(pages) * 2.2)   # rough request count for this contract: one sweep per page plus drill-downs

        async def cooldown():
            """Wait (untimed) until Drex's per-minute window has room, so an earlier upload or race can't throttle this one."""
            while True:
                now = time.time(); ts = recent_drex_requests(now)
                if not ts or len(ts) + need <= DREX_RPM_BUDGET:
                    break
                # a contract bigger than the whole budget just waits for the window to empty
                k = min(len(ts) - 1, max(0, len(ts) + need - DREX_RPM_BUDGET - 1))
                free_at = ts[k] + 60
                R["cool_s"] = max(1, round(free_at - now))
                await asyncio.sleep(1)
            R["phase"] = "racing"; R.pop("cool_s", None)

        cool = asyncio.ensure_future(cooldown())
        RACE_RT[rid] = {"loop": asyncio.get_running_loop(), "tasks": [cool]}
        try:
            await cool
        except asyncio.CancelledError:
            for k in ("stego", "llm"):
                R[k].update(status="cancelled", error="cancelled before the race started")
            await drex.close(); await llm.close()
            return
        t0 = time.perf_counter()
        ms_now = lambda: round((time.perf_counter() - t0) * 1000)

        async def stego():
            if R["stego"]["status"] == "error":
                return
            try:
                out, _ = await run_drex(ct, cats, DEFINITIONS, drex, arm="race-stego")
                R["stego"].update(status="done", ms=ms_now(), clauses={
                    c: {"p": round(out[c]["p"], 4), "page": (out[c]["evidence"][0] + 1 if out[c]["evidence"] else None)} for c in cats})
            except Exception as e:
                R["stego"].update(status="error", ms=ms_now(), error=f"{type(e).__name__}: {str(e)[:160]}")

        async def baseline():
            if not config.MOCK and not config.LLM_API_KEY:
                R["llm"].update(status="error", ms=ms_now(), error="LLM_API_KEY not set: the baseline can't run, so there is no race.")
                return
            try:
                out, _ = await asyncio.wait_for(run_llm(ct, cats, DEFINITIONS, llm, arm="race-llm"), timeout=RACE_LLM_CAP_S)
                R["llm"].update(status="done", ms=ms_now(), calls=llm.calls, present={c: bool(out[c]["pred"]) for c in cats})
            except asyncio.TimeoutError:
                R["llm"].update(status="error", ms=ms_now(), error=f"The LLM did not finish within {RACE_LLM_CAP_S} s (a thinking model on a long contract). Stego's result stands.")
            except Exception as e:
                R["llm"].update(status="error", ms=ms_now(), error=f"{type(e).__name__}: {str(e)[:160]}")

        async def ticker():
            while "running" in (R["stego"]["status"], R["llm"]["status"]):
                R["stego"]["decisions"] = drex.decisions
                await asyncio.sleep(0.1)
            R["stego"]["decisions"] = drex.decisions

        tasks = [asyncio.ensure_future(f()) for f in (stego, baseline, ticker)]
        RACE_RT[rid] = {"loop": asyncio.get_running_loop(), "tasks": tasks}
        await asyncio.gather(*tasks, return_exceptions=True)
        for k in ("stego", "llm"):
            if R[k]["status"] == "running":
                R[k].update(status="cancelled", error="cancelled: a newer race started or the page was refreshed")
        await drex.close(); await llm.close()

    try:
        asyncio.run(go())
    except Exception as e:   # never leave the UI stuck: surface the failure
        for k in ("stego", "llm"):
            if R[k]["status"] == "running":
                R[k].update(status="error", error=f"race failed: {type(e).__name__}: {str(e)[:200]}")
    finally:
        R["finished"] = True


def read_jsonl(path, tail=None):
    if not os.path.exists(path):
        return []
    rows = []
    for ln in open(path, encoding="utf-8"):
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            pass
    return rows[-tail:] if tail else rows


def state():
    theta, tau, frozen = thresholds()
    live = []
    for f in sorted(os.listdir(os.path.join(LIVE, "contracts"))):
        live.append(json.load(open(os.path.join(LIVE, "contracts", f))))
    live.sort(key=lambda r: -r["analyzed_at"])
    led = read_jsonl(os.path.join(LIVE, "ledger.jsonl"))
    for r in led:
        r.pop("probs", None)
    return {"mode": "mock" if config.MOCK else "live", "drex_model": config.DREX_MODEL, "drex_provider": "Mock Drex" if config.MOCK else config.DREX_PROVIDER, "theta": theta, "tau": tau,
            "thresholds_frozen": frozen, "llm_model": config.LLM_MODEL or None, "llm_ready": bool(config.LLM_API_KEY) or config.MOCK, "fossil": fossil is not None, "drex_price_per_m": config.DREX_PRICE_PER_M_INPUT, "categories": config.CATEGORIES, "contracts": live, "decisions": latest_decisions(), "ledger": led[-500:]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/state":
            return self.send_json(state())
        if path.startswith("/api/progress/"):
            j = JOBS.get(os.path.basename(path))
            return self.send_json({k: v for k, v in j.items() if k not in ("loop", "task")} if j else {"pct": None})
        if path.startswith("/api/race/"):
            R = RACES.get(os.path.basename(path))
            return self.send_json(R) if R else self.send_json({"error": "unknown race"}, 404)
        if path == "/":
            path = "/ui/index.html"
        elif path == "/ui/":
            path = "/ui/index.html"
        if not path.startswith(("/ui/", "/runs/", "/samples/")):
            path = "/ui" + path          # page served at "/" loads sample.js etc. relative to it
        full = os.path.normpath(os.path.join(ROOT, path.lstrip("/")))
        allowed = [os.path.join(ROOT, d) for d in ("ui", "runs", "samples")]
        if not any(full.startswith(a + os.sep) for a in allowed) or not os.path.isfile(full):
            self.send_response(404); self.end_headers(); return
        data = open(full, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(full)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def decision_api(self):
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > 10_000:
            return self.send_json({"error": "bad request"}, 400)
        try:
            req = json.loads(self.rfile.read(n))
            cid = re.sub(r"[^0-9a-f]", "", str(req.get("id", "")))
            cpath = os.path.join(LIVE, "contracts", cid + ".json")
            reviewer = str(req.get("reviewer", "")).strip()[:60]
            if not cid or not os.path.exists(cpath):
                return self.send_json({"error": "decisions are recorded for uploaded contracts only"}, 404)
            if req.get("clause") not in config.CATEGORIES or req.get("decision") not in DECISION_KINDS or not reviewer:
                return self.send_json({"error": "clause, decision and a reviewer name are required"}, 422)
            c = json.load(open(cpath))
            cl = c["clauses"][req["clause"]]
            ev = cl["evidence"][0] if cl["evidence"] else {}
            row = {"ts": time.time(), "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                   "contract_id": cid, "contract": c["title"], "clause": req["clause"], "decision": req["decision"], "reviewer": reviewer,
                   "drex_probability": round(cl["p"], 4), "page": ev.get("page"), "drex_model": config.DREX_MODEL, "mock": bool(c.get("mock"))}
            with DEC_LOCK, open(DECISIONS, "a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
            return self.send_json(row)
        except Exception as e:
            return self.send_json({"error": f"{type(e).__name__}: {str(e)[:200]}"}, 500)

    def fossil_api(self, path):
        if fossil is None:
            return self.send_json({"error": "Content Credentials unavailable: pip install c2pa-python pillow cryptography"}, 501)
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > MAX_BYTES:
            return self.send_json({"error": "body missing or too large"}, 413)
        body = self.rfile.read(n)
        try:
            if path == "/api/verify":
                v = fossil.verify(body)
                return self.send_json(v)
            req = json.loads(body)
            if path == "/api/seal":
                cid = re.sub(r"[^0-9a-f]", "", str(req.get("id", "")))
                cpath = os.path.join(LIVE, "contracts", cid + ".json")
                if not cid or not os.path.exists(cpath):
                    return self.send_json({"error": "Only uploaded (live) contracts can be sealed: they have a call ledger."}, 404)
                theta, tau, frozen = thresholds()
                reviews = {c: {"decision": r["decision"], "reviewer": r["reviewer"], "at": r["at"]} for c, r in latest_decisions().get(cid, {}).items()}   # the server ledger is the authority
                rec, name, data = fossil.seal_contract(json.load(open(cpath)), config.DREX_MODEL, theta, tau, frozen, reviews)
                v = fossil.verify(data); v.pop("record", None)
                return self.send_json({"record": rec, "name": name, "url": f"/runs/live/briefs/{name}", "verify": v})
            if path == "/api/tamper":
                name = os.path.basename(str(req.get("name", "")))
                src = os.path.join(LIVE, "briefs", name)
                if not name.endswith(".png") or "tampered" in name or not os.path.exists(src):
                    return self.send_json({"error": "sealed brief not found"}, 404)
                bad = fossil.tamper(open(src, "rb").read())
                tname = name[:-4] + "-tampered.png"
                open(os.path.join(LIVE, "briefs", tname), "wb").write(bad)
                v = fossil.verify(bad); v.pop("record", None)
                return self.send_json({"url": f"/runs/live/briefs/{tname}", "verify": v})
            if path == "/api/forge":
                name = os.path.basename(str(req.get("name", "")))
                src = os.path.join(LIVE, "briefs", name)
                if not name.endswith(".png") or "tampered" in name or "forged" in name or not os.path.exists(src):
                    return self.send_json({"error": "sealed brief not found"}, 404)
                orig = open(src, "rb").read()
                bad, victim = fossil.forge(orig)
                fname = name[:-4] + "-forged.png"
                open(os.path.join(LIVE, "briefs", fname), "wb").write(bad)
                v, o = fossil.verify(bad), fossil.verify(orig)
                v.pop("record", None); o.pop("record", None)
                return self.send_json({"url": f"/runs/live/briefs/{fname}", "victim": victim, "verify": v, "original": o})
            self.send_response(404); self.end_headers()
        except Exception as e:
            self.send_json({"error": f"{type(e).__name__}: {str(e)[:300]}"}, 500)

    def do_POST(self):
        route = urlparse(self.path).path
        if route in ("/api/seal", "/api/verify", "/api/tamper", "/api/forge"):
            return self.fossil_api(route)
        if route == "/api/decision":
            return self.decision_api()
        if route.startswith("/api/cancel/"):
            j = JOBS.get(os.path.basename(route))
            if j and j.get("task") and not j["task"].done():
                j["loop"].call_soon_threadsafe(j["task"].cancel)
                j["phase"] = "cancelled"
                return self.send_json({"cancelled": True})
            return self.send_json({"cancelled": False})
        if route == "/api/race/cancel":
            return self.send_json({"cancelled": cancel_races()})
        if route == "/api/race":
            n = int(self.headers.get("Content-Length", 0))
            if n <= 0 or n > MAX_BYTES:
                return self.send_json({"error": "file missing or larger than 40 MB"}, 413)
            name = os.path.basename(unquote(self.headers.get("X-Filename", "contract.pdf"))) or "contract.pdf"
            if not name.lower().endswith((".pdf", ".txt")):
                return self.send_json({"error": "only .pdf and .txt are supported"}, 415)
            try:
                pages = extract_pages(name, self.rfile.read(n))
            except ValueError as e:
                return self.send_json({"error": str(e)}, 422)
            cancel_races()   # only one race at a time
            rid = uuid.uuid4().hex[:8]
            title = os.path.splitext(name)[0]
            RACES[rid] = {"id": rid, "title": title, "pages": len(pages), "mock": config.MOCK, "llm_model": config.LLM_MODEL or "(unset)",
                          "drex_model": config.DREX_MODEL, "started": time.time(), "finished": False,
                          "cold_llm": True, "phase": "cooling", "stego": {"status": "running", "decisions": 0}, "llm": {"status": "running"}}
            threading.Thread(target=_race_main, args=(rid, title, pages), daemon=True).start()
            return self.send_json({"id": rid})
        if route != "/api/analyze":
            self.send_response(404); self.end_headers(); return
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > MAX_BYTES:
            return self.send_json({"error": "file missing or larger than 40 MB"}, 413)
        name = os.path.basename(unquote(self.headers.get("X-Filename", "contract.pdf"))) or "contract.pdf"
        if not name.lower().endswith((".pdf", ".txt")):
            return self.send_json({"error": "only .pdf and .txt are supported"}, 415)
        data = self.rfile.read(n)
        job_id = re.sub(r"[^a-z0-9]", "", self.headers.get("X-Job", "").lower())[:16]
        job = None
        if job_id:
            job = JOBS[job_id] = {"phase": "extract", "pct": 10, "detail": "Reading the PDF…"}
            while len(JOBS) > 60:
                JOBS.pop(next(iter(JOBS)))
        try:
            pages = extract_pages(name, data)
            if job is not None:
                job.update(pct=15, detail=f"{len(pages)} pages found")
            pdf_name = None
            if name.lower().endswith(".pdf"):
                pdf_name = uuid.uuid4().hex[:8] + ".pdf"
                open(os.path.join(LIVE, "uploads", pdf_name), "wb").write(data)
            parent = re.sub(r"[^a-z0-9]", "", self.headers.get("X-Parent", "").lower())[:16] or None
            rec = asyncio.run(run_analysis(os.path.splitext(name)[0], pages, pdf_name, job, parent))
            self.send_json(rec)
        except asyncio.CancelledError:
            if job is not None:
                job.update(phase="cancelled", detail="Cancelled")
            self.send_json({"error": "cancelled"}, 499)
        except ValueError as e:
            self.send_json({"error": str(e)}, 422)
        except Exception as e:  # surface Drex/API failures to the UI instead of hiding them
            self.send_json({"error": f"{type(e).__name__}: {str(e)[:300]}"}, 500)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Stego: http://localhost:{port}/   mode={'MOCK Drex (no DREX_API_KEY)' if config.MOCK else 'live Drex'}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
