import json, os


def load(cache_path):
    """Return {uid: bundle} for previously successful TinyFish research, so a
    restart doesn't re-fetch rows that were researched but never made it past
    classification (e.g. a crashed prior run)."""
    cache = {}
    if not os.path.exists(cache_path):
        return cache
    with open(cache_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                b = json.loads(line)
            except json.JSONDecodeError:
                continue
            cache[b["uid"]] = b
    return cache


def append(cache_path, bundle):
    with open(cache_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(bundle) + "\n")
