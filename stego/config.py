"""Pre-registered settings. Freeze this file before the final run and commit it."""
import os


def _load_dotenv(path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")):
    """Tiny .env reader (no dependency). Real environment variables win. Never prints values."""
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_dotenv()

# ---------- Data ----------
CUAD_TEST_JSON = os.getenv("CUAD_TEST_JSON", "data/cuad/test.json")  # official CUAD test split (102 contracts)
SEED = 14                       # fixed seed for the calibration/report split
N_CALIB = 20                    # contracts used ONLY to pick tau
CHUNK_CHARS = 3500              # ~ one page of contract text
PARA_MIN_CHARS = 300            # drill-down paragraph size floor

# 20 CUAD categories with clean yes/no semantics and >=10 positives in the test split.
CATEGORIES = [
    "Anti-Assignment", "License Grant", "Cap On Liability", "Audit Rights",
    "Revenue/Profit Sharing", "Exclusivity", "Insurance", "Minimum Commitment",
    "Termination For Convenience", "Post-Termination Services", "Renewal Term",
    "Change Of Control", "Covenant Not To Sue", "Non-Compete", "Ip Ownership Assignment",
    "Non-Transferable License", "Rofr/Rofo/Rofn", "Liquidated Damages",
    "Uncapped Liability", "Warranty Duration",
]

# ---------- Drex ----------
DREX_BASE_URL = os.getenv("DREX_BASE_URL", "https://console.nace.ai")
DREX_PATH = os.getenv("DREX_PATH", "/v1/systemone")       # client falls back to /v1/decisions on 404
DREX_MODEL = os.getenv("DREX_MODEL", "drex-v2.0")         # resolved at startup against GET /v1/models
DREX_MODEL_PREFS = ["drex-v2.0", "drex-max-v1.1", "drex-max", "drex-latest"]
DREX_API_KEY = os.getenv("DREX_API_KEY") or os.getenv("NACE_API_KEY", "")   # keys live in .env (gitignored); DREX_API_KEY wins so a provider switch is env-only
DREX_PROVIDER = ("Drex via DeepInfra" if "deepinfra" in DREX_BASE_URL.lower() else "Drex via Nace" if "nace.ai" in DREX_BASE_URL.lower()
                 else "Drex via " + DREX_BASE_URL.split("//")[-1].split("/")[0])
DREX_MAX_INFLIGHT = int(os.getenv("DREX_MAX_INFLIGHT", "8"))   # free tier is reportedly 8 in-flight; verify
DREX_QUESTIONS_PER_REQ = int(os.getenv("DREX_QUESTIONS_PER_REQ", "20"))  # <=64 on TypeSafe-compatible hosts
DREX_PRICE_PER_M_INPUT = float(os.getenv("DREX_PRICE_PER_M_INPUT", "0.06"))  # set from Nace pricing page

# Drill-down band: chunks whose p(yes) is in this band get re-asked per paragraph.
DRILL_LOW, DRILL_HIGH = 0.2, 0.9

# ---------- LLM baseline ----------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")   # "openai" (any OpenAI-compatible) or "anthropic"
LLM_ARM_LABEL = os.getenv("LLM_ARM_LABEL", "A frontier LLM")   # name arm A honestly: only say "frontier" for a frontier model
LLM_MODEL = os.getenv("LLM_MODEL", "")               # use a CURRENT frontier model; record it on the slide
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_PRICE_PER_M_INPUT = float(os.getenv("LLM_PRICE_PER_M_INPUT", "0"))
LLM_PRICE_PER_M_OUTPUT = float(os.getenv("LLM_PRICE_PER_M_OUTPUT", "0"))
LLM_TEMPERATURE = os.getenv("LLM_TEMPERATURE", "0")  # set to "" for models that reject temperature
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "8000"))

# ---------- Cascade ----------
CASCADE_TOPK_CHUNKS = 4          # chunks sent to the LLM per uncertain category
TARGET_AUTO_ACCURACY = 0.95      # tau = lowest confidence whose auto-decided accuracy on CALIB >= this

# ---------- Runtime ----------
CONTRACT_CONCURRENCY = int(os.getenv("CONTRACT_CONCURRENCY", "4"))
MOCK = os.getenv("MOCK", "0") == "1"   # offline mode for testing the pipeline without API keys
