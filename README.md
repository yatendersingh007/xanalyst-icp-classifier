# Xanalyst — ICP Gate + RE / Fund-Admin Classifier

**Multi-file. Separate batches. No Anthropic API key.**

Each subfolder in `input/` is a separate batch with its own ledger and output. Drop files,
name the folder, run it — batches never cross-contaminate.

```
input/
  family-offices/           ← 1000+ Family Offices xlsx
  navigator-leads/          ← Sales Navigator CSVs (drop as many as you want)
  <any-new-batch>/          ← create a folder, drop files, run

output/
  family-offices/
    icp_ledger.csv          ← append-only source of truth
    classified.csv          ← final output, IN ICP sorted first
  navigator-leads/
    icp_ledger.csv
    classified.csv
```

Two decisions per lead, **no scoring**:

1. **Relevance** — `IN ICP` / `NOT IN ICP` / `UNVERIFIED` / `REVIEW`
2. **Category** (IN-ICP only) — `RE` / `FUND ADMIN-GP` / `FUND ADMIN-LP` / `BOTH (primary: RE|FUND)`

## Architecture

```
[1] LOAD + DEDUP (by LinkedIn URL or name+company hash)
[2] INDUSTRY PRE-FILTER  → instant NOT IN ICP (Software, Healthcare, Education...)
[3] TINYFISH RESEARCH     → Search + Fetch (FREE endpoints, 8 concurrent)
[4] CLAUDE CODE CLASSIFY  → headless `claude -p` (your subscription, batches of ~15)
[5] LEDGER + OUTPUT CSV
```

## Setup

```bash
pip install -r requirements.txt
export TINYFISH_API_KEY=tf-...        # Search + Fetch are free tier
claude auth status                    # must be logged in (Pro Max subscription)
```

## Run

```bash
# List available batches:
python run.py --list

# Process the family offices (test first, then all):
python run.py --batch family-offices --test 10
python run.py --batch family-offices --all --writeback

# Process the navigator leads separately:
python run.py --batch navigator-leads --test 10
python run.py --batch navigator-leads --all --writeback
```

## Adding more files / batches

**Same batch, more files:** drop new CSVs into the existing folder and re-run. The ledger
skips already-done leads automatically.

**New batch:** create a subfolder under `input/`, drop files, run with `--batch <folder-name>`.

## Current batches

| Batch | Files | Leads | Pre-filtered | Need research |
|-------|-------|-------|-------------|---------------|
| `family-offices` | 1 xlsx | 906 | 0 (no industry col) | 906 |
| `navigator-leads` | 6 CSVs | 790 (deduped) | 225 | 565 |

The industry pre-filter kills ~225 Navigator leads instantly (Software, Healthcare,
Education, Advertising, Staffing, etc.) — zero TinyFish calls, zero Claude calls.

## Supported input formats

| Format | Auto-detected by |
|--------|------------------|
| Sales Navigator CSV | `.csv`, "Company Name" column |
| Family Office XLSX | `.xlsx`, "Family Office Name" column |

## Tuning (config.py)

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `RESEARCH_WORKERS` | 8 | TinyFish concurrent searches (free) |
| `CLASSIFY_BATCH` | 15 | Rows per `claude -p` call |
| `CLASSIFY_WORKERS` | 2 | Concurrent `claude -p` processes |
| `DISQUALIFIED_INDUSTRIES` | ~60 | Instant NOT IN ICP set — edit as needed |

## Files
```
config.py               batch_paths(), TinyFish + Claude settings, industry pre-filter
run.py                  orchestrator: --batch, --list, --test/--all, --writeback
icp_model.md            v2.2 rubric (ICP gate + Service Track)
input/
  family-offices/       1000 Family Offices xlsx
  navigator-leads/      6 Sales Navigator CSVs
scripts/
  select_rows.py        multi-format loader, dedup, industry pre-filter
  tinyfish.py           Search + Fetch client (free tier, backoff)
  research.py           per-row Search+Fetch → evidence bundle
  prompt.py             ICP-gate + category rules, JSON-array output
  classify_batch.py     headless `claude -p` batch classifier
  ledger_append.py      lock-serialized idempotent appender
  writeback.py          ledger → sorted output CSV
output/                 per-batch: ledger + classified.csv
```
