import argparse, os, sys, time, traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (INPUT_DIR, TINYFISH_API_KEY, batch_paths, RESEARCH_WORKERS,
                    CLASSIFY_BATCH, CLASSIFY_WORKERS, MAX_ATTEMPTS, RATE_LIMIT_BACKOFF)
from scripts import ledger_append, select_rows, research as research_mod, research_cache, writeback
from scripts.classify_batch import classify_batch, RateLimitError


def _log(errors_path, uid, company, msg):
    with open(errors_path, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {uid} ({company}): {msg}\n")


def _research(row):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return research_mod.research(row), None
        except Exception as e:
            if attempt == MAX_ATTEMPTS:
                return None, str(e)
            time.sleep(2 * attempt)


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _report(ledger_path):
    import csv
    if not os.path.exists(ledger_path):
        return
    rel, cat = Counter(), Counter()
    with open(ledger_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rel[r["Relevance"]] += 1
            if r["Relevance"] == "IN ICP":
                cat[r["Category"]] += 1
    total = sum(rel.values())
    icp = rel.get("IN ICP", 0)
    print(f"\n=== SUMMARY ({total} total) ===")
    print("Relevance     :", dict(rel))
    print("Category (ICP):", dict(cat))
    print(f"IN ICP: {icp} ({100*icp/total:.0f}%) | NOT IN ICP: {rel.get('NOT IN ICP',0)} | UNVERIFIED: {rel.get('UNVERIFIED',0)}")


def _list_batches():
    print("Available batches (subfolders in input/):\n")
    for name in sorted(os.listdir(INPUT_DIR)):
        d = os.path.join(INPUT_DIR, name)
        if not os.path.isdir(d) or name.startswith("."):
            continue
        files = [f for f in os.listdir(d) if f.endswith((".csv", ".xlsx"))]
        bp = batch_paths(name)
        done = len(ledger_append.done_uids(bp["ledger"])) if os.path.exists(bp["ledger"]) else 0
        print(f"  {name:<25} {len(files)} file(s)  |  {done} already classified")
        for f in files[:5]:
            print(f"    - {f}")
        if len(files) > 5:
            print(f"    ... +{len(files)-5} more")
    print(f"\nUsage: python run.py --batch <name> --test 10")


def run_batch(batch_name, test_n, do_writeback):
    bp = batch_paths(batch_name)
    if not os.path.isdir(bp["input_dir"]):
        sys.exit(f"Batch folder not found: {bp['input_dir']}\n"
                 f"Create it and drop .csv / .xlsx files inside.")

    ledger_path = bp["ledger"]
    errors_path = bp["errors"]
    output_csv  = bp["output_csv"]

    print(f"=== Batch: {batch_name} ===")
    print(f"  Input:  {bp['input_dir']}")
    print(f"  Ledger: {ledger_path}")
    print(f"  Output: {output_csv}\n")

    # 1. Load + dedup + subtract done
    done = ledger_append.done_uids(ledger_path)
    all_rows = select_rows.load_all_inputs(bp["input_dir"], done)
    if not all_rows:
        print(f"Nothing to do ({len(done)} already in ledger).")
        _report(ledger_path)
        if do_writeback:
            writeback.run(ledger_path, output_csv)
        return

    # 2. Industry pre-filter
    to_research, auto_killed = select_rows.prefilter(all_rows)
    print(f"Loaded {len(all_rows) + len(done)} leads ({len(done)} already done)")
    print(f"  Pre-filtered NOT IN ICP: {len(auto_killed)}")
    print(f"  Need research:           {len(to_research)}")

    for r in auto_killed:
        ledger_append.append(ledger_path, {
            "uid": r["uid"], "source_file": r["source_file"],
            "company": r["company"], "contact_name": r["contact_name"],
            "title": r["title"], "email": r["email"], "linkedin": r["linkedin"],
            "industry": r["industry"], "hq": r["hq"], "website": r["website"],
            "Relevance": "NOT IN ICP", "Category": "", "Category Primary": "",
            "Evidence": r["_prefilter"],
        })

    if test_n:
        to_research = to_research[:test_n]

    if not to_research:
        print("No rows need research.")
        _report(ledger_path)
        if do_writeback:
            writeback.run(ledger_path, output_csv)
        return

    # 3. TinyFish research (reuse cached bundles from a prior crashed run)
    cache_path = bp["research_cache"]
    cached = research_cache.load(cache_path)
    to_fetch, bundles = [], []
    for r in to_research:
        cb = cached.get(r["uid"])
        if cb:
            cb = dict(cb)
            cb["_row"] = r
            bundles.append(cb)
        else:
            to_fetch.append(r)

    print(f"\nStep 1/2  TinyFish research  ({len(to_fetch)} to fetch, "
          f"{len(bundles)} from cache, {RESEARCH_WORKERS} workers)...")
    with ThreadPoolExecutor(max_workers=RESEARCH_WORKERS) as ex:
        futs = {ex.submit(_research, r): r for r in to_fetch}
        for i, fut in enumerate(as_completed(futs), 1):
            r = futs[fut]
            b, err = fut.result()
            if b:
                research_cache.append(cache_path, b)
                b["_row"] = r
                bundles.append(b)
            else:
                _log(errors_path, r["uid"], r["company"], f"research: {err}")
            if i % 25 == 0 or i == len(to_fetch):
                print(f"  researched {i}/{len(to_fetch)}")

    # 4. Claude Code classify
    row_lookup = {b["uid"]: b.pop("_row") for b in bundles if "_row" in b}
    batches = list(_chunks(bundles, CLASSIFY_BATCH))
    print(f"\nStep 2/2  Claude Code classify  ({len(batches)} batches of ~{CLASSIFY_BATCH})...")
    n_ok = 0

    def _do_batch(batch):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return classify_batch(batch)
            except Exception as e:
                if attempt == MAX_ATTEMPTS:
                    for b in batch:
                        _log(errors_path, b["uid"], b["company"], f"classify: {e}")
                    return {}
                if isinstance(e, RateLimitError):
                    print(f"  [rate limit] backing off {RATE_LIMIT_BACKOFF}s before retry: {e}")
                    time.sleep(RATE_LIMIT_BACKOFF)
                else:
                    time.sleep(3 * attempt)

    with ThreadPoolExecutor(max_workers=CLASSIFY_WORKERS) as ex:
        futs = {ex.submit(_do_batch, batch): batch for batch in batches}
        for j, fut in enumerate(as_completed(futs), 1):
            batch = futs[fut]
            results = fut.result() or {}
            for b in batch:
                rec = results.get(b["uid"])
                if not rec:
                    continue
                row = row_lookup.get(b["uid"], {})
                rec.update({
                    "uid": row.get("uid", b["uid"]),
                    "source_file": row.get("source_file", ""),
                    "company": row.get("company", b["company"]),
                    "contact_name": row.get("contact_name", ""),
                    "title": row.get("title", ""),
                    "email": row.get("email", ""),
                    "linkedin": row.get("linkedin", ""),
                    "industry": row.get("industry", ""),
                    "hq": row.get("hq", ""),
                    "website": row.get("website", ""),
                })
                rec.pop("Company", None)
                if ledger_append.append(ledger_path, rec):
                    n_ok += 1
                    print(f"  {rec.get('company','')[:34]:<34} {rec['Relevance']:<11} {rec['Category']}")
            print(f"  [batch {j}/{len(batches)} done]")

    print(f"\nClassified {n_ok} rows. Errored rows retry on next run.")
    _report(ledger_path)

    if do_writeback:
        writeback.run(ledger_path, output_csv)


def main():
    ap = argparse.ArgumentParser(description="ICP Gate + RE/Fund-Admin Classifier")
    ap.add_argument("--batch", type=str, help="batch name (subfolder in input/)")
    ap.add_argument("--list", action="store_true", help="list available batches")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--test", type=int, metavar="N", help="process first N un-done rows only")
    g.add_argument("--all", action="store_true", help="process every remaining row")
    ap.add_argument("--writeback", action="store_true", help="produce output classified.csv")
    args = ap.parse_args()

    if args.list:
        _list_batches()
        return

    if not args.batch:
        sys.exit("Specify --batch <name> or --list to see available batches.")
    if not (args.test or args.all):
        sys.exit("Specify --test N or --all.")
    if not TINYFISH_API_KEY:
        sys.exit("Set TINYFISH_API_KEY. Classification uses your logged-in Claude Code.")

    run_batch(args.batch, args.test, args.writeback)


if __name__ == "__main__":
    sys.exit(main())
