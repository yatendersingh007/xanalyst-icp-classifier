import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# --- Paths ---
BASE_DIR     = os.path.dirname(__file__)
INPUT_DIR    = os.path.join(BASE_DIR, "input")     # each subfolder = a batch
OUTPUT_DIR   = os.path.join(BASE_DIR, "output")     # mirrors input subfolders

def batch_paths(batch_name):
    """Return (input_dir, ledger_path, output_csv, errors_path) for a named batch."""
    inp = os.path.join(INPUT_DIR, batch_name)
    out = os.path.join(OUTPUT_DIR, batch_name)
    os.makedirs(out, exist_ok=True)
    return {
        "input_dir":      inp,
        "ledger":         os.path.join(out, "icp_ledger.csv"),
        "output_csv":     os.path.join(out, "classified.csv"),
        "errors":         os.path.join(out, "errors.log"),
        "research_cache": os.path.join(out, "research_cache.jsonl"),
    }

# --- TinyFish (research layer — Search + Fetch are free) ---
TINYFISH_API_KEY = os.environ.get("TINYFISH_API_KEY", "")
TF_SEARCH_URL    = "https://api.search.tinyfish.ai"
TF_FETCH_URL     = "https://api.fetch.tinyfish.ai"
TF_LOCATION      = "US"
PAGE_CHAR_LIMIT  = 4000
RESEARCH_WORKERS = 8

# --- Claude Code (classification — logged-in subscription, no API key) ---
CLAUDE_BIN       = os.environ.get("CLAUDE_BIN", "claude")
CLAUDE_MODEL     = os.environ.get("XICP_MODEL", "sonnet")
CLASSIFY_BATCH   = 20
CLASSIFY_WORKERS = 2
CLASSIFY_TIMEOUT = 360

# --- Retry ---
MAX_ATTEMPTS = 2
RATE_LIMIT_BACKOFF = 900  # seconds to wait before retrying after a rate/usage-limit signal

# --- Pre-filter: industries that are NEVER in ICP (deterministic, no research) ---
DISQUALIFIED_INDUSTRIES = {
    "software development", "technology, information and internet",
    "it services and it consulting", "computer and network security",
    "computer hardware manufacturing", "computer games",
    "mobile computing software products", "data security software products",
    "business intelligence platforms", "automation machinery manufacturing",
    "higher education", "education administration programs",
    "primary and secondary education",
    "hospitals and health care", "medical equipment manufacturing",
    "medical practices", "medical device", "health and human services",
    "pharmaceutical manufacturing", "biotechnology research", "biotechnology",
    "wellness and fitness services", "health, wellness & fitness",
    "defense and space manufacturing", "armed forces",
    "airlines and aviation", "aviation and aerospace component manufacturing",
    "motor vehicle manufacturing",
    "law practice", "legal services",
    "advertising services", "marketing services",
    "public relations and communications services",
    "staffing and recruiting", "executive search services",
    "outsourcing/offshoring",
    "government administration", "administration of justice",
    "child day care services", "restaurants", "retail",
    "retail apparel and fashion", "online and mail order retail",
    "food and beverage manufacturing", "food and beverage services",
    "food & beverages", "packaging and containers manufacturing",
    "luxury goods & jewelry", "consumer services",
    "spectator sports", "entertainment providers",
    "online audio and video media", "broadcast media production and distribution",
    "media production", "book and periodical publishing",
    "museums, historical sites, and zoos",
    "professional training and coaching",
    "security and investigations",
    "international affairs", "international trade and development",
    "civic and social organizations",
    "travel arrangements", "recreational facilities",
    "electrical equipment manufacturing",
    "appliances, electrical, and electronics manufacturing",
    "computers and electronics manufacturing",
    "climate technology product manufacturing",
    "telecommunications", "wireless services",
}
