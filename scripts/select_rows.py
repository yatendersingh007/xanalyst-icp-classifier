import os, glob, hashlib
import pandas as pd
from config import DISQUALIFIED_INDUSTRIES

NORM_COLS = [
    "uid", "source_file", "company", "contact_name", "title", "email",
    "email_status", "linkedin", "hq", "state", "country",
    "website", "domain", "industry", "company_type", "employee_range",
    "source_of_wealth", "family_founder", "aum", "re_classes",
    "investment_style", "recent_activity", "notes",
]

def _s(v):
    return "" if pd.isna(v) else str(v).strip()

def _uid(row):
    li = _s(row.get("linkedin"))
    if li and li.lower() not in ("nan", ""):
        return li.lower().rstrip("/")
    key = (_s(row.get("contact_name")) + "|" + _s(row.get("company"))).lower()
    return "hash:" + hashlib.md5(key.encode()).hexdigest()[:12]

def _load_xlsx(path):
    df = pd.read_excel(path, sheet_name=0)
    rows = []
    for _, r in df.iterrows():
        row = {c: "" for c in NORM_COLS}
        row["source_file"] = os.path.basename(path)
        row["company"] = _s(r.get("Family Office Name"))
        dm = _s(r.get("Key Decision Maker(s)"))
        if dm.lower() not in ("undisclosed", "n/a", "unknown"):
            row["contact_name"] = dm.split(";")[0].strip()
        row["linkedin"] = _s(r.get("LinkedIn"))
        row["email"] = _s(r.get("Company Email"))
        row["hq"] = f'{_s(r.get("HQ City"))}, {_s(r.get("HQ State"))}'.strip(", ")
        row["state"] = _s(r.get("HQ State"))
        row["country"] = "United States"
        row["website"] = _s(r.get("Website / Source"))
        row["source_of_wealth"] = _s(r.get("Source of Wealth"))
        row["family_founder"] = _s(r.get("Family / Founder"))
        row["aum"] = _s(r.get("Est. AUM / Net Worth"))
        row["re_classes"] = _s(r.get("RE Asset Classes"))
        row["investment_style"] = _s(r.get("Investment Style"))
        row["recent_activity"] = _s(r.get("Recent Activity (2023-2025)"))
        row["notes"] = _s(r.get("Notes"))
        row["uid"] = _uid(row)
        rows.append(row)
    return rows

def _load_csv(path):
    df = pd.read_csv(path, on_bad_lines="skip")
    rows = []
    for _, r in df.iterrows():
        row = {c: "" for c in NORM_COLS}
        row["source_file"] = os.path.basename(path)
        row["company"] = _s(r.get("Company Name"))
        row["contact_name"] = _s(r.get("Name"))
        row["title"] = _s(r.get("Title"))
        row["email"] = _s(r.get("Email"))
        row["email_status"] = _s(r.get("Email Status"))
        row["linkedin"] = _s(r.get("Linkedin"))
        city = _s(r.get("City")); state = _s(r.get("State"))
        row["hq"] = f"{city}, {state}".strip(", ") or _s(r.get("Location"))
        row["state"] = state
        row["country"] = _s(r.get("Country"))
        row["domain"] = _s(r.get("Company Domain"))
        row["website"] = _s(r.get("Company Website"))
        row["industry"] = _s(r.get("Company Industry"))
        row["company_type"] = _s(r.get("Company Type"))
        row["employee_range"] = _s(r.get("Company Employee Count Range"))
        row["uid"] = _uid(row)
        rows.append(row)
    return rows

def load_all_inputs(input_dir, done_uids):
    """Scan input_dir for .xlsx and .csv, normalize, dedup, subtract done."""
    all_rows = []
    for f in sorted(glob.glob(os.path.join(input_dir, "*.xlsx"))):
        all_rows.extend(_load_xlsx(f))
    for f in sorted(glob.glob(os.path.join(input_dir, "*.csv"))):
        all_rows.extend(_load_csv(f))
    seen = set()
    deduped = []
    for r in all_rows:
        if r["uid"] in seen or r["uid"] in done_uids:
            continue
        seen.add(r["uid"])
        deduped.append(r)
    return deduped

def prefilter(rows):
    research, killed = [], []
    for r in rows:
        ind = r["industry"].lower()
        if ind and ind in DISQUALIFIED_INDUSTRIES:
            r["_prefilter"] = f"Industry '{r['industry']}' is outside ICP sectors"
            killed.append(r)
        else:
            research.append(r)
    return research, killed
