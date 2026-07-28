import csv, os
from filelock import FileLock

LEDGER_COLS = [
    "uid", "source_file", "company", "contact_name", "title", "email",
    "linkedin", "industry", "hq", "website",
    "Relevance", "Category", "Category Primary", "Evidence",
]

def _ensure(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(LEDGER_COLS)

def done_uids(path):
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as f:
        return {r["uid"] for r in csv.DictReader(f) if r.get("uid")}

def append(path, record):
    lock = FileLock(path + ".lock")
    with lock:
        _ensure(path)
        if str(record.get("uid","")) in done_uids(path):
            return False
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([record.get(c, "") for c in LEDGER_COLS])
        return True
