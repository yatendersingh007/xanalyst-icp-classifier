"""Independent verification pass: a STRONGER model (Opus by default) re-checks
every already-classified row against the ICP rubric, using the evidence stored
in the ledger. It does NOT re-research the web — it audits whether the assigned
relevance/category is defensible given the recorded evidence.

Output: output/<batch>/audit_report.csv with one row per lead:
    uid, company, ledger_relevance, ledger_category, verdict (AGREE/DISAGREE),
    suggested_relevance, suggested_category, reason
Only DISAGREE rows carry suggestions. Run:  python -m scripts.audit family-offices
"""
import csv, json, os, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from filelock import FileLock

from config import CLAUDE_BIN, batch_paths, MAX_ATTEMPTS, RATE_LIMIT_BACKOFF
from scripts.prompt import RULES
from scripts.classify_batch import _extract_array, _kill_tree, _is_rate_limit, RateLimitError

AUDIT_MODEL   = os.environ.get("XICP_AUDIT_MODEL", "opus")
AUDIT_BATCH   = 25
AUDIT_WORKERS = 2
AUDIT_TIMEOUT = 420

REPORT_COLS = ["uid", "company", "ledger_relevance", "ledger_category", "verdict",
               "suggested_relevance", "suggested_category", "reason"]

_AUDIT_INSTRUCTIONS = """
You are now a SENIOR REVIEWER auditing classifications another analyst already made,
using the SAME rubric above. For each lead you are given the evidence that was gathered
and the relevance/category the analyst assigned. Decide whether that assignment is
DEFENSIBLE given the evidence and the rubric.

- verdict "AGREE"    = the assigned relevance AND category are the best reading of this evidence.
- verdict "DISAGREE" = the relevance or category is wrong, OR the evidence is too thin to
                       support an IN ICP / NOT IN ICP call that should have been UNVERIFIED.
  When you DISAGREE, give suggested_relevance and suggested_category (the corrected values;
  category empty unless suggested_relevance is "IN ICP"), and a one-sentence reason.
Do NOT invent new facts or assume web research beyond the evidence shown. Judge only whether
the label fits the evidence. Be strict about the SOURCE-OF-WEALTH TRAP and about
multi-family-office (LP wealth structure) vs multifamily real estate.

OUTPUT: return ONLY a JSON array, one object per lead, same order, no prose, no fences:
[{"uid":"..","verdict":"AGREE|DISAGREE","suggested_relevance":"..","suggested_category":"..","reason":".."}]
"""


def _build_audit_prompt(rows):
    leads = [{
        "uid": r["uid"],
        "company": r.get("company", ""),
        "industry": r.get("industry", ""),
        "hq": r.get("hq", ""),
        "website": r.get("website", ""),
        "assigned_relevance": r.get("Relevance", ""),
        "assigned_category": r.get("Category", ""),
        "assigned_category_primary": r.get("Category Primary", ""),
        "evidence": r.get("Evidence", ""),
    } for r in rows]
    return (RULES + _AUDIT_INSTRUCTIONS
            + "\n\nLEADS TO AUDIT:\n" + json.dumps(leads, ensure_ascii=False))


def _run_auditor(prompt):
    env = dict(os.environ, DISABLE_AUTOUPDATER="1", CLAUDE_CODE_ENABLE_TELEMETRY="0")
    proc = subprocess.Popen(
        [CLAUDE_BIN, "-p", "--output-format", "json", "--model", AUDIT_MODEL,
         "--allowedTools", "", "--max-turns", "1",
         "--no-session-persistence", "--exclude-dynamic-system-prompt-sections"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    timer = threading.Timer(AUDIT_TIMEOUT, _kill_tree, args=(proc,))
    timer.start()
    try:
        stdout, stderr = proc.communicate(input=prompt)
    finally:
        timer.cancel()
    if proc.returncode != 0:
        msg = f"auditor failed ({proc.returncode}): {(stderr or '')[:300]}"
        raise (RateLimitError if _is_rate_limit(stderr) else RuntimeError)(msg)
    envelope = json.loads(stdout)
    if envelope.get("is_error"):
        rt = str(envelope.get("result"))
        raise (RateLimitError if _is_rate_limit(rt) else RuntimeError)(f"auditor error: {rt[:300]}")
    return _extract_array(envelope.get("result", ""))


def _audit_batch(rows):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            arr = _run_auditor(_build_audit_prompt(rows))
            return {str(a.get("uid", "")).strip(): a for a in arr}
        except RateLimitError as e:
            if attempt == MAX_ATTEMPTS:
                return {"__error__": str(e)}
            print(f"  [rate limit] backing off {RATE_LIMIT_BACKOFF}s: {e}", flush=True)
            time.sleep(RATE_LIMIT_BACKOFF)
        except Exception as e:
            if attempt == MAX_ATTEMPTS:
                return {"__error__": str(e)}
            time.sleep(3 * attempt)


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def _already_audited(report_path):
    if not os.path.exists(report_path):
        return set()
    with open(report_path, newline="", encoding="utf-8") as f:
        return {r["uid"] for r in csv.DictReader(f) if r.get("uid")}


def _append_report(report_path, recs):
    """Incremental, crash-safe write: each finished batch is flushed to disk
    immediately (locked, like ledger_append) instead of buffering until the
    very end — a kill/sleep mid-run no longer loses completed audit work."""
    lock = FileLock(report_path + ".lock")
    with lock:
        is_new = not os.path.exists(report_path)
        with open(report_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=REPORT_COLS)
            if is_new:
                w.writeheader()
            for rec in recs:
                w.writerow(rec)


def main(batch_name):
    bp = batch_paths(batch_name)
    report_path = os.path.join(os.path.dirname(bp["ledger"]), "audit_report.csv")
    with open(bp["ledger"], newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    done = _already_audited(report_path)
    todo = [r for r in rows if r["uid"] not in done]
    print(f"{len(rows)} ledger rows | {len(done)} already audited | "
          f"{len(todo)} to audit with model={AUDIT_MODEL} "
          f"({AUDIT_BATCH}/batch, {AUDIT_WORKERS} workers)\n", flush=True)

    if not todo:
        print("Nothing to audit — report is already complete.")
        return _summarize(report_path, len(rows))

    batches = list(_chunks(todo, AUDIT_BATCH))
    errors = 0

    with ThreadPoolExecutor(max_workers=AUDIT_WORKERS) as ex:
        futs = {ex.submit(_audit_batch, b): b for b in batches}
        for j, fut in enumerate(as_completed(futs), 1):
            batch = futs[fut]
            out = fut.result() or {}
            if "__error__" in out:
                errors += 1
                print(f"  [batch {j}/{len(batches)}] ERROR: {out['__error__'][:120]}", flush=True)
                continue
            recs = []
            for r in batch:
                a = out.get(r["uid"])
                if not a:
                    continue
                verdict = str(a.get("verdict", "")).strip().upper()
                recs.append({
                    "uid": r["uid"], "company": r.get("company", ""),
                    "ledger_relevance": r.get("Relevance", ""), "ledger_category": r.get("Category", ""),
                    "verdict": verdict,
                    "suggested_relevance": str(a.get("suggested_relevance", "")).strip() if verdict == "DISAGREE" else "",
                    "suggested_category": str(a.get("suggested_category", "")).strip() if verdict == "DISAGREE" else "",
                    "reason": str(a.get("reason", "")).strip(),
                })
            _append_report(report_path, recs)
            print(f"  [batch {j}/{len(batches)}] audited + saved ({len(recs)} rows)", flush=True)

    _summarize(report_path, len(rows))


def _summarize(report_path, total_ledger_rows):
    with open(report_path, newline="", encoding="utf-8") as f:
        audited_rows = list(csv.DictReader(f))
    disagree = [r for r in audited_rows if r["verdict"] == "DISAGREE"]

    print(f"\n=== AUDIT SUMMARY ===")
    print(f"Ledger rows:     {total_ledger_rows}")
    print(f"Audited:         {len(audited_rows)}")
    print(f"Not audited:     {total_ledger_rows - len(audited_rows)}")
    print(f"AGREE:           {len(audited_rows) - len(disagree)}")
    print(f"DISAGREE:        {len(disagree)}")
    print(f"Report -> {report_path}")
    if disagree:
        print("\nDISAGREEMENTS:")
        for d in disagree:
            print(f"  {d['company'][:40]:<40} {d['ledger_relevance']}/{d['ledger_category']} "
                  f"-> {d['suggested_relevance']}/{d['suggested_category']}  | {d['reason'][:100]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "family-offices")
