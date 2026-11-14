"""The Fossil Record: seal a Stego review brief with C2PA Content Credentials.

The seal records which Drex model decided, the probabilities, the evidence pages, a hash of the call
ledger and whether a human reviewed each flag. It proves who decided from what evidence; it does NOT
prove the decision was right.

  .venv/bin/python fossil.py demo            # seal the latest live contract, verify, then tamper and re-verify
  .venv/bin/python fossil.py verify FILE.png

The signing certificate is a generated TEST chain (see keys/). Adobe's verify site will show it as an
untrusted signer. Production needs a certificate from the C2PA trust list.
"""
import datetime
import hashlib
import io
import json
import os
import sys
import time

from PIL import Image, ImageDraw, ImageFont
from c2pa import (Builder, C2paSignerInfo, C2paSigningAlg, Reader, Signer)

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYS = os.path.join(ROOT, "keys")
LIVE = os.path.join(ROOT, "runs", "live")
BRIEFS = os.path.join(LIVE, "briefs")
URGENT = {"Uncapped Liability", "Change Of Control", "Liquidated Damages", "Non-Compete"}
VERIFY_URL = "https://contentcredentials.org/verify"
RENDER_VERSION = 5  # bump when render_brief changes, so older seals are not falsely flagged as edited
MASCOT = os.path.join(ROOT, "assets", "mascot_firefly.png")  # a Firefly image; its own Content Credentials join the chain


# ---------------------------------------------------------------- test certificates
def ensure_certs(who="stego"):
    chain, key = os.path.join(KEYS, f"{who}_test_chain.pem"), os.path.join(KEYS, f"{who}_test_key.pem")
    if os.path.exists(chain) and os.path.exists(key):
        return chain, key
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    os.makedirs(KEYS, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)

    root_cn = "Stego Test Root CA" if who == "stego" else "Forger Test Root CA"
    leaf_cn = "Stego Fossil Record Signer (TEST)" if who == "stego" else "Simulated Forger (TEST)"
    org = "Stego (TEST ONLY)" if who == "stego" else "Forger Co. (SIMULATED, TEST ONLY)"

    def name(cn):
        return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, org),
                          x509.NameAttribute(NameOID.COMMON_NAME, cn)])

    root_key, leaf_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    root = (x509.CertificateBuilder().subject_name(name(root_cn)).issuer_name(name(root_cn))
            .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    leaf = (x509.CertificateBuilder().subject_name(name(leaf_cn)).issuer_name(root.subject)
            .public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now).not_valid_after(now + datetime.timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False,
                                         key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    pem = serialization.Encoding.PEM
    open(chain, "wb").write(leaf.public_bytes(pem) + root.public_bytes(pem))
    open(key, "wb").write(leaf_key.private_bytes(pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    os.chmod(key, 0o600)
    return chain, key


# ---------------------------------------------------------------- the decision record
def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def queue(cat, p, theta, tau, urgent=URGENT):
    conf = p if p >= theta else 1 - p
    if conf < tau:
        return "human"
    if p < theta:
        return "cleared"
    return "urgent" if cat in urgent else "review"


def build_record(contract, drex_model, theta, tau, frozen, reviews=None, ledger_path=None):
    """contract: a runs/live/contracts/<id>.json dict. reviews: {clause: 'approved'|'escalated'} (human actions)."""
    reviews = reviews or {}
    ledger_path = ledger_path or os.path.join(LIVE, "ledger.jsonl")
    raw = open(ledger_path, "rb").read() if os.path.exists(ledger_path) else b""
    rows = [ln for ln in raw.decode().splitlines() if ln.strip()]
    mine = [ln for ln in rows if json.loads(ln).get("contract") == contract["title"]]
    decisions = []
    urgent = set(contract.get("urgent") or URGENT)
    for cat, c in contract["clauses"].items():
        q = queue(cat, c["p"], theta, tau, urgent)
        if q == "cleared":
            continue
        ev = c["evidence"][0] if c["evidence"] else {}
        decisions.append({"clause": cat, "probability": round(c["p"], 4), "queue": q, "evidence_page": ev.get("page"),
                          "evidence_sha256": sha(ev.get("text", "")), "human_review": reviews.get(cat)})
    decisions.sort(key=lambda d: -d["probability"])
    human = [{"clause": c, "decision": v.get("decision"), "reviewer": v.get("reviewer"), "at": v.get("at"),
              "drex_probability": round(contract["clauses"][c]["p"], 4)}
             for c, v in reviews.items() if isinstance(v, dict) and c in contract["clauses"]]
    return {"schema": "org.stego.decision-record/1", "contract": contract["title"], "contract_id": contract["id"], "pages": contract["pages"], "render_version": RENDER_VERSION, "human_decisions": human,
            "drex": {"model": drex_model, "mode": "mock" if contract.get("mock") else "live"},
            "thresholds": {"theta": theta, "tau": tau, "frozen_on_calibration_set": frozen},
            "firefly_mascot_ingredient": os.path.exists(MASCOT), "reasoning_llm_calls": 0, "clauses_evaluated": len(contract["clauses"]), "flagged": decisions,
            "cleared": [k for k, c in contract["clauses"].items() if queue(k, c["p"], theta, tau, urgent) == "cleared"],
            "template": contract.get("template", "commercial"), "template_label": contract.get("template_label", "Commercial contract (CUAD 20)"), "benchmarked": contract.get("benchmarked", True),
            "ledger": {"file_sha256": sha(raw), "contract_rows": len(mine), "contract_rows_sha256": sha("\n".join(mine))},
            "sealed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}


# ---------------------------------------------------------------- render the brief PNG
def _font(size, bold=False):
    for path in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size, index=1 if (bold and path.endswith(".ttc")) else 0)
        except Exception:
            continue
    return ImageFont.load_default(size)


def _mono(size):
    for path in ("/System/Library/Fonts/Menlo.ttc", "/System/Library/Fonts/Monaco.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default(size)


HR_LABEL = {"confirmed": "confirmed present", "not_present": "marked not present", "escalated": "escalated to counsel"}


def _hr_text(v):
    if isinstance(v, dict):
        return f"{HR_LABEL.get(v.get('decision'), v.get('decision'))} by {v.get('reviewer')}"
    return v or "no human action yet"


def render_brief(rec):
    W, INK, CANVAS = 1240, (17, 17, 17), (246, 243, 234)
    G, A, R, GR, Y = (47, 168, 79), (245, 165, 36), (229, 72, 77), (226, 223, 210), (255, 216, 61)
    groups = [("URGENT · SEND TO COUNSEL", R, [d for d in rec["flagged"] if d["queue"] == "urgent"]),
              ("FOUND · CONFIRM", A, [d for d in rec["flagged"] if d["queue"] == "review"]),
              ("HUMAN · READ AND DECIDE", GR, [d for d in rec["flagged"] if d["queue"] == "human"])]
    rows = sum(max(1, len(g[2])) for g in groups)
    cl_lines, cur = [], ""
    for w in (f"Cleared as absent ({len(rec['cleared'])}): " + ", ".join(rec["cleared"])).split(" "):
        t = (cur + " " + w).strip()
        if cur and _font(17).getlength(t) > W - 180:
            cl_lines.append(cur); cur = w
        else:
            cur = t
    cl_lines.append(cur)
    H = 520 + rows * 74 + 3 * 70 + 130 + (len(cl_lines) - 1) * 24
    im = Image.new("RGB", (W, H), CANVAS)
    d = ImageDraw.Draw(im)
    f_t, f_h, f_b, f_s, f_m = _font(44, True), _font(26, True), _font(22), _font(17), _mono(17)
    d.rectangle([40, 40, W - 40, H - 40], outline=INK, width=4)
    d.rectangle([48, 48, W - 32, H - 32], outline=INK, width=2)
    d.text((80, 80), "CONTRACT REVIEW BRIEF", font=f_t, fill=INK)
    d.text((80, 150), rec["contract"], font=f_h, fill=INK)
    mode = rec["drex"]["mode"].upper()
    d.rounded_rectangle([W - 470, 84, W - 80, 144], radius=8, fill=Y if mode == "LIVE" else A, outline=INK, width=3)
    d.text((W - 455, 92), f"DREX {mode} · {rec['drex']['model']}", font=f_m, fill=INK)
    d.text((W - 455, 116), "clause triage, not legal approval" if rec.get("benchmarked", True) else f"{rec.get('template_label', 'template')} · not benchmarked", font=f_s, fill=INK)
    tiles = [("URGENT", sum(1 for x in rec["flagged"] if x["queue"] == "urgent"), R), ("FOUND", sum(1 for x in rec["flagged"] if x["queue"] == "review"), A),
             ("CLEARED", len(rec["cleared"]), G), ("HUMAN", sum(1 for x in rec["flagged"] if x["queue"] == "human"), GR)]
    for i, (lab, n, col) in enumerate(tiles):
        x = 80 + i * 275
        d.rectangle([x + 5, 215, x + 255, 315], fill=INK)
        d.rectangle([x, 210, x + 250, 310], fill=(255, 255, 255), outline=INK, width=3)
        d.rectangle([x, 210, x + 14, 310], fill=col)
        d.text((x + 28, 220), lab, font=f_m, fill=INK)
        d.text((x + 28, 248), f"{n:02d}", font=_mono(44), fill=INK)
    y = 350
    for title, col, items in groups:
        d.rectangle([80, y, W - 80, y + 52], fill=col, outline=INK, width=3)
        d.text((100, y + 12), title, font=f_h, fill=(255, 255, 255) if col in (R, A) else INK)
        y += 62
        if not items:
            d.text((100, y + 10), "None", font=f_b, fill=INK)
            y += 54
        for it in items:
            d.text((100, y), it["clause"], font=_font(24, True), fill=INK)
            hr = _hr_text(it["human_review"])
            d.text((100, y + 34), f"page {it['evidence_page']} · human review: {hr}", font=f_s, fill=(80, 78, 70))
            d.text((W - 260, y + 6), f"p = {it['probability']:.2f}", font=_mono(26), fill=INK)
            d.line([100, y + 66, W - 100, y + 66], fill=GR, width=2)
            y += 74
        y += 14
    for i, ln in enumerate(cl_lines):
        d.text((80, y + 8 + i * 24), ln, font=f_s, fill=INK)
    y += 64 + (len(cl_lines) - 1) * 24
    d.rectangle([80, y, W - 80, y + 150], fill=(255, 255, 255), outline=INK, width=3)
    if os.path.exists(MASCOT):
        m = Image.open(MASCOT).convert("RGBA")
        m = m.crop((0, 0, m.width, int(m.height * 0.9)))   # the generated image carries a stray colour label at the bottom
        bg = m.getpixel((2, 2))
        keep = Image.new("L", m.size, 255)
        px, kp = m.load(), keep.load()
        for yy in range(m.height):
            for xx in range(m.width):
                p = px[xx, yy]
                if max(abs(p[i] - bg[i]) for i in range(3)) < 14:
                    kp[xx, yy] = 0
        m.putalpha(keep)
        m = m.crop(m.getbbox()) if m.getbbox() else m
        m.thumbnail((130, 84))
        im.paste(m, (W - 80 - 20 - m.width, y + 10), m)
    d.text((100, y + 14), "SEALED WITH CONTENT CREDENTIALS (C2PA) · THE FOSSIL RECORD", font=f_m, fill=INK)
    d.text((100, y + 44), f"ledger sha256  {rec['ledger']['file_sha256'][:48]}…", font=f_m, fill=INK)
    d.text((100, y + 70), f"contract rows  {rec['ledger']['contract_rows']}  ·  reasoning-LLM calls  {rec['reasoning_llm_calls']}", font=f_m, fill=INK)
    d.text((100, y + 100), "Proves who decided and from what evidence, not that the decision was right. TEST certificate: verify shows an untrusted signer.", font=f_s, fill=(80, 78, 70))
    out = io.BytesIO()
    im.save(out, "PNG")
    return out.getvalue()


# ---------------------------------------------------------------- seal / verify
def _signer(who="stego"):
    chain, key = ensure_certs(who)
    info = C2paSignerInfo(C2paSigningAlg.ES256, open(chain, "rb").read(), open(key, "rb").read(), None)
    return Signer.from_info(info)


def seal(png, rec):
    """Embed a C2PA manifest (standard actions + the Stego decision record) into the PNG bytes."""
    flagged = [d for d in rec["flagged"] if d["queue"] in ("urgent", "review")]
    manifest = {
        "claim_generator_info": [{"name": "Stego Fossil Record", "version": "0.1"}],
        "title": f"Stego review brief: {rec['contract']}",
        "assertions": [
            {"label": "c2pa.actions", "data": {"actions": [{
                "action": "c2pa.created", "softwareAgent": {"name": "Stego"},
                "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/digitalCreation",
                "description": f"Clause triage brief: {len(flagged)} clauses flagged by Drex ({rec['drex']['model']}, {rec['drex']['mode']}); 0 reasoning-LLM calls"}]}},
            {"label": "org.stego.decision-record", "data": rec},
        ],
    }
    builder = Builder.from_json(manifest)
    if os.path.exists(MASCOT):
        with open(MASCOT, "rb") as mf:
            builder.add_ingredient({"title": "Stego mascot (Adobe Firefly)", "relationship": "componentOf"}, "image/png", mf)
    signer = _signer()
    out = io.BytesIO()
    builder.sign(signer, "image/png", io.BytesIO(png), out)
    builder.close(); signer.close()
    return out.getvalue()


def _stego_record(manifests):
    for label, m in manifests.items():
        for a in (m.get("assertions") or []):
            if str(a.get("label", "")).startswith("org.stego.decision-record"):
                return label, a.get("data")
    return None, None


def _content_matches(png, rec):
    """Re-render the brief from the sealed record and compare pixels with the file we were given."""
    if rec.get("render_version") != RENDER_VERSION:
        return None   # sealed by an older renderer: cannot compare
    try:
        from PIL import ImageChops
        a = Image.open(io.BytesIO(png)).convert("RGB")
        b = Image.open(io.BytesIO(render_brief(rec))).convert("RGB")
    except Exception:
        return None
    if a.size != b.size:
        return False
    d = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v > 8 else 0)
    return d.histogram()[255] / (a.size[0] * a.size[1]) < 0.001


def _ledger_matches(rec):
    path = os.path.join(LIVE, "ledger.jsonl")
    if not os.path.exists(path):
        return None
    rows = [ln for ln in open(path, encoding="utf-8").read().splitlines() if ln.strip()]
    mine = [ln for ln in rows if json.loads(ln).get("contract") == rec["contract"]]
    n = rec["ledger"]["contract_rows"]  # the ledger is append-only, so compare the rows the seal covered
    return sha("\n".join(mine[:n])) == rec["ledger"]["contract_rows_sha256"]


def verify(png):
    """Verdicts: authentic | edited-after-seal | tampered | not-stego | no-seal."""
    try:
        reader = Reader.try_create("image/png", io.BytesIO(png))
    except Exception as e:
        return {"has_credentials": False, "valid": False, "verdict": "no-seal", "state": "no-manifest", "problems": [f"{type(e).__name__}: {str(e)[:160]}"]}
    if reader is None:
        return {"has_credentials": False, "valid": False, "verdict": "no-seal", "state": "no-manifest", "problems": ["no Content Credentials found"]}
    state = reader.get_validation_state() or "unknown"
    results = reader.get_validation_results() or {}
    data = json.loads(reader.json())
    reader.close()
    manifests, active_label = data.get("manifests", {}), data.get("active_manifest")
    active = manifests.get(active_label, {})
    fails = [f.get("code") for f in ((results.get("activeManifest") or {}).get("failure") or [])]
    untrusted = [c for c in fails if "untrusted" in str(c)]
    real = [c for c in fails if c not in untrusted]
    sig = active.get("signature_info") or {}
    stego_label, rec = _stego_record(manifests)
    out = {"has_credentials": True, "state": state, "tampered": bool(real), "problems": real, "untrusted_signer": bool(untrusted),
           "signer": sig.get("issuer") or sig.get("common_name"), "record": rec, "verify_url": VERIFY_URL, "editor": None, "issues": [],
           "ingredients": [i.get("title") for i in (active.get("ingredients") or [])]}
    if real:
        out.update(valid=False, verdict="tampered")
    elif rec is None:
        out.update(valid=True, verdict="not-stego")
    else:
        issues = []
        if stego_label != active_label:
            gen = ((active.get("claim_generator_info") or [{}])[0].get("name")) or sig.get("issuer") or "another tool"
            out["editor"] = gen
            issues.append(f"Edited after Stego sealed it (by {gen})")
        cm = _content_matches(png, rec)
        if cm is False:
            issues.append("The visible content no longer matches the sealed decision record")
        lm = _ledger_matches(rec)
        if lm is False:
            issues.append("The call-ledger hash no longer matches")
        out.update(issues=issues, content_matches=cm, ledger_matches=lm, valid=True, verdict="authentic" if not issues else "edited-after-seal")
    return out


def forge(sealed_png):
    """REHEARSAL ONLY: a second test signer quietly clears a flag, re-renders the brief and re-signs with the
    original as its parent ingredient. Stands in for 'edit it in Photoshop with Content Credentials on'."""
    v = verify(sealed_png)
    rec = json.loads(json.dumps(v["record"]))
    victim = next((d for d in rec["flagged"] if d["queue"] in ("urgent", "review")), None)
    if victim:
        rec["flagged"].remove(victim)
        rec["cleared"].append(victim["clause"])
    manifest = {"claim_generator_info": [{"name": "Photoshop (SIMULATED forger, not Adobe)", "version": "0"}], "title": "Edited brief",
                "assertions": [{"label": "c2pa.actions", "data": {"actions": [
                    {"action": "c2pa.opened", "softwareAgent": {"name": "Photoshop (SIMULATED forger, not Adobe)"}, "parameters": {"ingredientIds": ["xmp:iid:original-stego-brief"]}},
                    {"action": "c2pa.edited", "softwareAgent": {"name": "Photoshop (SIMULATED forger, not Adobe)"}, "description": "Changed a flagged clause to cleared"}]}}]}
    builder = Builder.from_json(manifest)
    builder.add_ingredient({"title": "Original Stego brief", "relationship": "parentOf", "instance_id": "xmp:iid:original-stego-brief"}, "image/png", io.BytesIO(sealed_png))
    signer = _signer("forger")
    out = io.BytesIO()
    builder.sign(signer, "image/png", io.BytesIO(render_brief(rec)), out)
    builder.close(); signer.close()
    return out.getvalue(), (victim or {}).get("clause")


def tamper(png):
    """Change one pixel's data but keep the embedded manifest chunk, like editing a sealed file."""
    import struct
    import zlib
    sig, pos, chunks = png[:8], 8, []
    while pos < len(png):
        n, typ = struct.unpack(">I4s", png[pos:pos + 8])
        chunks.append((typ, png[pos + 8:pos + 8 + n]))
        pos += 12 + n
    idat = zlib.decompress(b"".join(c for t, c in chunks if t == b"IDAT"))
    mid = len(idat) // 2
    idat = idat[:mid] + bytes([idat[mid] ^ 0xFF]) + idat[mid + 1:]
    out, wrote = [sig], False
    for typ, data in chunks:
        if typ == b"IDAT":
            if wrote:
                continue
            data, wrote = zlib.compress(idat, 6), True
        out.append(struct.pack(">I", len(data)) + typ + data + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))
    return b"".join(out)


def seal_contract(contract, drex_model, theta, tau, frozen, reviews=None):
    rec = build_record(contract, drex_model, theta, tau, frozen, reviews)
    data = seal(render_brief(rec), rec)
    os.makedirs(BRIEFS, exist_ok=True)
    name = f"{contract['id']}-{int(time.time())}.png"
    open(os.path.join(BRIEFS, name), "wb").write(data)
    return rec, name, data


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "verify":
        print(json.dumps({k: v for k, v in verify(open(sys.argv[2], "rb").read()).items() if k != "record"}, indent=2))
    else:
        cdir = os.path.join(LIVE, "contracts")
        files = sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []
        if not files:
            sys.exit("No analyzed contract. Upload one in the app first (samples/sample_vendor_agreement.pdf).")
        c = json.load(open(os.path.join(cdir, files[-1])))
        tp = os.path.join(ROOT, "runs", "thresholds.json")
        th = json.load(open(tp)) if os.path.exists(tp) else {"theta": 0.5, "tau": 0.9}
        rec, name, data = seal_contract(c, "drex-v2.0", th["theta"], th["tau"], os.path.exists(tp))
        print("sealed ->", os.path.join(BRIEFS, name))
        v = verify(data); print("1. verify sealed:  valid=%s state=%s tampered=%s signer=%s" % (v["valid"], v["state"], v.get("tampered"), v.get("signer")))
        t = verify(tamper(data)); print("2. verify tampered: valid=%s state=%s tampered=%s problems=%s" % (t["valid"], t["state"], t.get("tampered"), t["problems"]))
        print("   flagged in record:", [(d["clause"], d["probability"]) for d in v["record"]["flagged"][:4]] if v.get("record") else None)
        print("   check on Adobe's site:", VERIFY_URL)
