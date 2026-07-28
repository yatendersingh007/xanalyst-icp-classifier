import json, os, re, subprocess, threading
from config import CLAUDE_BIN, CLAUDE_MODEL, CLASSIFY_TIMEOUT
from scripts.prompt import build_batch_prompt

_VALID_REL = {"IN ICP", "NOT IN ICP", "UNVERIFIED", "REVIEW"}

_RATE_LIMIT_MARKERS = ("rate limit", "usage limit", "429", "overloaded", "quota")


class RateLimitError(RuntimeError):
    """Raised when the CLI reports a rate/usage-limit condition — callers
    should back off much longer than a normal transient-error retry."""


def _is_rate_limit(text):
    t = (text or "").lower()
    return any(m in t for m in _RATE_LIMIT_MARKERS)


def _extract_array(text):
    text = re.sub(r"```(?:json)?", "", text).strip()
    a, b = text.find("["), text.rfind("]")
    if a == -1 or b == -1 or b < a:
        raise ValueError(f"no JSON array in classifier output: {text[:200]!r}")
    return json.loads(text[a:b + 1])


def _kill_tree(proc):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.kill()


def _run_claude(prompt):
    """subprocess.run(timeout=...) can hang well past its deadline on Windows:
    claude.exe spawns its own child processes that inherit the stdout/stderr
    pipes, so killing only the immediate process never closes those handles
    and communicate() blocks forever waiting for EOF. Run a watchdog timer
    that force-kills the whole process tree instead of relying on the
    built-in timeout."""
    env = dict(os.environ, DISABLE_AUTOUPDATER="1", CLAUDE_CODE_ENABLE_TELEMETRY="0")
    proc = subprocess.Popen(
        [CLAUDE_BIN, "-p", "--output-format", "json",
         "--model", CLAUDE_MODEL, "--allowedTools", "", "--max-turns", "1",
         "--no-session-persistence", "--exclude-dynamic-system-prompt-sections"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", env=env,
    )
    timer = threading.Timer(CLASSIFY_TIMEOUT, _kill_tree, args=(proc,))
    timer.start()
    try:
        stdout, stderr = proc.communicate(input=prompt)
    finally:
        timer.cancel()
    return proc.returncode, stdout, stderr


def classify_batch(bundles):
    """Run one headless claude -p over a batch of evidence bundles.
    Returns {uid: record}."""
    prompt = build_batch_prompt(bundles)
    returncode, stdout, stderr = _run_claude(prompt)
    if returncode != 0:
        msg = f"claude -p failed ({returncode}): {(stderr or '')[:300]}"
        if _is_rate_limit(stderr):
            raise RateLimitError(msg)
        raise RuntimeError(msg)

    envelope = json.loads(stdout)
    if envelope.get("is_error"):
        result_text = str(envelope.get("result"))
        msg = f"claude reported error: {result_text[:300]}"
        if envelope.get("api_error_status") in (429, "429") or _is_rate_limit(result_text):
            raise RateLimitError(msg)
        raise RuntimeError(msg)
    rows = _extract_array(envelope.get("result", ""))

    by_uid = {b["uid"]: b for b in bundles}
    out = {}
    for r in rows:
        uid = str(r.get("uid", "")).strip()
        if uid not in by_uid:
            continue
        rel = str(r.get("relevance", "")).strip().upper()
        rel = rel if rel in _VALID_REL else "UNVERIFIED"
        cat = str(r.get("category", "")).strip()
        catp = str(r.get("category_primary", "")).strip().upper()
        if rel != "IN ICP":
            cat, catp = "", ""
        out[uid] = {
            "uid": uid,
            "Company": by_uid[uid]["company"],
            "Relevance": rel,
            "Category": cat,
            "Category Primary": catp,
            "Evidence": str(r.get("evidence", "")).strip(),
        }
    return out
