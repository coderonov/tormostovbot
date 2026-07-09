import json
import os
import random
import re

POOL_FILE = os.path.join(os.path.dirname(__file__), "bridge_pool.json")

FP_RE = re.compile(r"\b([0-9a-fA-F]{40})\b")
ENDPOINT_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}:\d{1,5})")


def _load():
    if not os.path.exists(POOL_FILE):
        return {}
    try:
        with open(POOL_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data):
    with open(POOL_FILE, "w") as f:
        json.dump(data, f)


def parse_line(line):
    fp_match = FP_RE.search(line)
    ep_match = ENDPOINT_RE.search(line)
    if not fp_match or not ep_match:
        return None
    return fp_match.group(1).upper(), ep_match.group(1)


def add_lines(transport, lines):
    data = _load()
    bucket = data.setdefault(transport, {})
    added = 0
    for line in lines:
        parsed = parse_line(line)
        if not parsed:
            continue
        fingerprint, endpoint = parsed
        key = f"{fingerprint}@{endpoint}"
        if key not in bucket:
            bucket[key] = {"fp": fingerprint, "endpoint": endpoint, "line": line}
            added += 1
    _save(data)
    return added


def pool_size(transport):
    data = _load()
    return len(data.get(transport, {}))


def random_sample(transport, count=20):
    data = _load()
    bucket = data.get(transport, {})
    entries = list(bucket.values())
    if not entries:
        return []
    k = min(count, len(entries))
    return random.sample(entries, k)


def get_lines(transport, count=40):
    entries = random_sample(transport, count)
    lines = []
    for e in entries:
        line = e.get("line")
        if line:
            lines.append(line)
    return lines


def format_entries(entries):
    lines = []
    for e in entries:
        line = e.get("line")
        if line:
            lines.append(line)
        else:
            lines.append(e["fp"])
            lines.append(e["endpoint"])
    return "\n".join(lines)
