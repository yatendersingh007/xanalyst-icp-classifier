import csv, os


def run(ledger_path, output_csv):
    """Produce the final classified.csv from the ledger."""
    if not os.path.exists(ledger_path):
        raise SystemExit(f"No ledger found at {ledger_path}")

    with open(ledger_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    order = {"IN ICP": 0, "REVIEW": 1, "UNVERIFIED": 2, "NOT IN ICP": 3}
    rows.sort(key=lambda r: (order.get(r.get("Relevance", ""), 9), r.get("Category", "")))

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    if rows:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys())
            w.writeheader()
            w.writerows(rows)

    n_icp = sum(1 for r in rows if r.get("Relevance") == "IN ICP")
    print(f"Wrote {len(rows)} rows -> {output_csv}  ({n_icp} IN ICP)")


if __name__ == "__main__":
    import sys
    run(sys.argv[1], sys.argv[2])
