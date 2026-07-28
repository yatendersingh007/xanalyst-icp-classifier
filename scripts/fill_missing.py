"""One-off: classify rows that never got TinyFish research (persistent 503s)
by letting Claude Code do its OWN web research (WebSearch/WebFetch) instead.

Reuses the exact ICP RULES and ledger format so output is identical in shape
to the normal pipeline. Run:  python -m scripts.fill_missing family-offices
"""
import json, os, re, subprocess, sys, threading, time

from config import (CLAUDE_BIN, batch_paths, MAX_ATTEMPTS)
from scripts import ledger_append, select_rows, writeback
from scripts.prompt import RULES
from scripts.classify_batch import _extract_array, _kill_tree, _is_rate_limit, RateLimitError

# web research needs real turns + time; and we want the stronger model here
FILL_MODEL   = os.environ.get("XICP_FILL_MODEL", "opus")
FILL_TURNS   = 40
FILL_TIMEOUT = 600
FILL_BACKOFF = 900


def _prior_evidence(row):
    """Everything the sheet already knows — Claude uses this as a starting
    point and then verifies/expands it with its own web research."""
    return {k: row.get(k, "") for k in (
        "company", "contact_name", "linkedin", "website", "hq",
        "source_of_wealth", "family_founder", "aum", "re_classes",
        "investment_style", "recent_activity", "notes",
    )}


def _build_prompt(row):
    lead = {"uid": row["uid"], "sheet_priors": _prior_evidence(row)}
    return (
        RULES
        + "\n\nThere is NO pre-gathered web evidence for this lead. USE your WebSearch and "
          "WebFetch tools to research the CURRENT entity yourself: find what it operates/owns/"
          "manages today, direct real estate, and whether it runs its own funds. The sheet_priors "
          "below are UNVERIFIED hints — confirm them against live sources, do not just echo them. "
          "When done, output ONLY the JSON array (one object) as specified above.\n\n"
        + "LEAD:\n" + json.dumps(lead, ensure_ascii=False)
    )


def _run_claude_web(prompt):
    env = dict(os.environ, DISABLE_AUTOUPDATER="1", CLAUDE_CODE_ENABLE_TELEMETRY="0")
    proc = subprocess.Popen(
        [CLAUDE_BIN, "-p", "--output-format", "json", "--model", FILL_MODEL,
         "--allowedTools", "WebSearch,WebFetch", "--max-turns", str(FILL_TURNS),
         "--no-session-persistence", "--exclude-dynamic-system-prompt-sections"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    timer = threading.Timer(FILL_TIMEOUT, _kill_tree, args=(proc,))
    timer.start()
    try:
        stdout, stderr = proc.communicate(input=prompt)
    finally:
        timer.cancel()
    if proc.returncode != 0:
        msg = f"claude -p failed ({proc.returncode}): {(stderr or '')[:300]}"
        raise (RateLimitError if _is_rate_limit(stderr) else RuntimeError)(msg)
    envelope = json.loads(stdout)
    if envelope.get("is_error"):
        rt = str(envelope.get("result"))
        raise (RateLimitError if _is_rate_limit(rt) else RuntimeError)(f"claude error: {rt[:300]}")
    return _extract_array(envelope.get("result", ""))


_VALID_REL = {"IN ICP", "NOT IN ICP", "UNVERIFIED", "REVIEW"}


def _classify_one(row):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            arr = _run_claude_web(_build_prompt(row))
            rec = next((r for r in arr if str(r.get("uid", "")).strip() == row["uid"]), None)
            if rec is None and arr:
                rec = arr[0]
            if rec is None:
                raise ValueError("no object returned")
            rel = str(rec.get("relevance", "")).strip().upper()
            rel = rel if rel in _VALID_REL else "UNVERIFIED"
            cat = str(rec.get("category", "")).strip()
            catp = str(rec.get("category_primary", "")).strip().upper()
            if rel != "IN ICP":
                cat, catp = "", ""
            return {"relevance": rel, "category": cat, "category_primary": catp,
                    "evidence": str(rec.get("evidence", "")).strip()}
        except RateLimitError as e:
            if attempt == MAX_ATTEMPTS:
                raise
            print(f"    [rate limit] backing off {FILL_BACKOFF}s: {e}")
            time.sleep(FILL_BACKOFF)
        except Exception:
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(5 * attempt)


def main(batch_name):
    bp = batch_paths(batch_name)
    done = ledger_append.done_uids(bp["ledger"])
    all_rows = select_rows.load_all_inputs(bp["input_dir"], set())
    missing = [r for r in all_rows if r["uid"] not in done]
    print(f"{len(missing)} row(s) missing from ledger — classifying via Claude web research "
          f"(model={FILL_MODEL})\n")

    n_ok = 0
    for i, row in enumerate(missing, 1):
        print(f"[{i}/{len(missing)}] {row['company'][:50]} ...", flush=True)
        try:
            res = _classify_one(row)
        except Exception as e:
            with open(bp["errors"], "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {row['uid']} ({row['company']}): fill: {e}\n")
            print(f"    FAILED: {e}")
            continue
        rec = {
            "uid": row["uid"], "source_file": row["source_file"], "company": row["company"],
            "contact_name": row["contact_name"], "title": row["title"], "email": row["email"],
            "linkedin": row["linkedin"], "industry": row["industry"], "hq": row["hq"],
            "website": row["website"], "Relevance": res["relevance"], "Category": res["category"],
            "Category Primary": res["category_primary"], "Evidence": res["evidence"],
        }
        if ledger_append.append(bp["ledger"], rec):
            n_ok += 1
            print(f"    {res['relevance']:<11} {res['category']}  | {res['evidence'][:90]}")

    print(f"\nFilled {n_ok}/{len(missing)}. Refreshing classified.csv ...")
    writeback.run(bp["ledger"], bp["output_csv"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "family-offices")
