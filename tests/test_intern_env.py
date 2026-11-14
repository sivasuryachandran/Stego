"""The Intern subprocess must get only PATH/HOME-type variables plus NACE_API_KEY and DEEPINFRA_API_KEY.  No network, no real keys.
Run: .venv/bin/python tests/test_intern_env.py"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["MOCK"] = "1"
for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "LLM_API_KEY", "SOME_OTHER_SECRET"):
    os.environ[k] = "should-not-leak"
os.environ["DEEPINFRA_API_KEY"] = "fake-di"
import app  # noqa: E402

seen = {}


def fake_run(cmd, **kw):
    seen.update(kw["env"]); return subprocess.CompletedProcess(cmd, 0, stdout="A note.\n", stderr="")


app.subprocess.run = fake_run
app.config.DREX_API_KEY = "fake-nace"
status, text = app.run_intern("prompt")
allowed = {"PATH", "HOME", "LANG", "TMPDIR", "SYSTEMROOT", "USERPROFILE", "TEMP", "TMP", "NACE_API_KEY", "DEEPINFRA_API_KEY"}
extra = set(seen) - allowed
ok = [status == "ok", not extra, seen.get("NACE_API_KEY") == "fake-nace", seen.get("DEEPINFRA_API_KEY") == "fake-di", "GROQ_API_KEY" not in seen]
print(("PASS" if all(ok) else "FAIL") + "  Intern env holds only PATH/HOME-type vars and the two keys", f"(extra: {sorted(extra)})" if extra else "")
sys.exit(0 if all(ok) else 1)
