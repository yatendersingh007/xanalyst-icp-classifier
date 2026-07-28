"""Apply DISAGREE corrections from audit_report.csv onto the ledger, then
regenerate classified.csv and dashboard.html. Idempotent: safe to re-run.

Run:  python -m scripts.apply_audit family-offices
"""
import csv, os, sys

from config import batch_paths
from scripts import writeback, ledger_append

_CATEGORY_PRIMARY = {
    "RE": "RE",
    "FUND ADMIN-GP": "FUND",
    "FUND ADMIN-LP": "FUND",
    "BOTH (primary: RE)": "RE",
    "BOTH (primary: FUND)": "FUND",
}


def _primary_for(category):
    return _CATEGORY_PRIMARY.get(category, "")


def main(batch_name):
    bp = batch_paths(batch_name)
    report_path = os.path.join(os.path.dirname(bp["ledger"]), "audit_report.csv")

    with open(report_path, newline="", encoding="utf-8") as f:
        corrections = {r["uid"]: r for r in csv.DictReader(f) if r["verdict"] == "DISAGREE"}
    print(f"{len(corrections)} correction(s) to apply from {report_path}")

    with open(bp["ledger"], newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    applied = 0
    for r in rows:
        c = corrections.get(r["uid"])
        if not c:
            continue
        new_rel = c["suggested_relevance"].strip()
        new_cat = c["suggested_category"].strip() if new_rel == "IN ICP" else ""
        new_primary = _primary_for(new_cat) if new_rel == "IN ICP" else ""
        note = f" [Audit-corrected (opus), was {c['ledger_relevance']}/{c['ledger_category'] or '-'}: {c['reason']}]"
        r["Relevance"] = new_rel
        r["Category"] = new_cat
        r["Category Primary"] = new_primary
        r["Evidence"] = (r["Evidence"] or "") + note
        applied += 1

    with open(bp["ledger"], "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=ledger_append.LEDGER_COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in ledger_append.LEDGER_COLS})

    print(f"Applied {applied} correction(s) to {bp['ledger']}")
    writeback.run(bp["ledger"], bp["output_csv"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "family-offices")
