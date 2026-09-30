#!/usr/bin/env python3
"""Validate BERTopic-native export for the visualizer."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

MONTHS = {"January","February","March","April","May","June",
          "July","August","September","October","November","December"}
MONTHS |= {m[:3] for m in MONTHS}

DATE_RE      = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOPIC_FILE_RE = re.compile(r"^topic_(-?\d+)\.json$")


class Log:
    def __init__(self): self.errors = 0; self.warnings = 0
    def ok(self, m):   print(f"  \033[92m✓\033[0m {m}")
    def warn(self, m): self.warnings += 1; print(f"  \033[93m!\033[0m {m}")
    def err(self, m):  self.errors   += 1; print(f"  \033[91m✗\033[0m {m}")
    def section(self, t): print(f"\n\033[1m{t}\033[0m")


def load_json(path: Path, log: Log):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        log.err(f"{path.name}: {e}")
        return None


# ---------------------------------------------------------------------------

def validate_topics(data_dir: Path, log: Log) -> set[int] | None:
    log.section("topics.json")
    p = data_dir / "topics.json"
    if not p.is_file():
        log.err("topics.json missing"); return None

    data = load_json(p, log)
    if not isinstance(data, list):
        log.err("root must be an array"); return None

    ids: set[int] = set()
    required = ("Topic", "Count", "Name", "Representation", "word_weight", "perc")

    for i, t in enumerate(data):
        lbl = f"topics[{i}]"
        if not isinstance(t, dict):
            log.err(f"{lbl}: not an object"); continue
        for k in required:
            if k not in t:
                log.err(f"{lbl}: missing '{k}'")
        tid = t.get("Topic")
        if not isinstance(tid, int):
            log.err(f"{lbl}.Topic must be int"); continue
        if tid in ids:
            log.err(f"{lbl}: duplicate Topic id {tid}")
        ids.add(tid)

        if not isinstance(t.get("Count"), int):
            log.err(f"{lbl}.Count must be int")
        if not isinstance(t.get("Name"), str):
            log.err(f"{lbl}.Name must be string")
        if not isinstance(t.get("Representation"), list):
            log.err(f"{lbl}.Representation must be list")

        ww = t.get("word_weight")
        if not isinstance(ww, list):
            log.err(f"{lbl}.word_weight must be list")
        else:
            for j, w in enumerate(ww):
                if not (isinstance(w, list) and len(w) == 2
                        and isinstance(w[0], str)
                        and isinstance(w[1], (int, float))):
                    log.err(f"{lbl}.word_weight[{j}] malformed (expected [word, prob])")

        if not isinstance(t.get("perc"), (int, float)):
            log.err(f"{lbl}.perc must be number")

    if not log.errors:
        log.ok(f"{len(ids)} topic entries (incl. outlier -1 if present)")
    return ids


def validate_time_freq(data_dir: Path, log: Log, topic_ids: set[int]) -> None:
    log.section("dailytopicfreq.json")
    p = data_dir / "dailytopicfreq.json"
    if not p.is_file():
        log.err("dailytopicfreq.json missing"); return

    data = load_json(p, log)
    if not isinstance(data, list):
        log.err("root must be an array"); return

    unknown: set[int] = set()
    for i, r in enumerate(data):
        lbl = f"[{i}]"
        if not isinstance(r, dict):
            log.err(f"{lbl}: not an object"); continue
        for k in ("date", "topic_id", "frequency"):
            if k not in r:
                log.err(f"{lbl}: missing '{k}'")
        d = r.get("date")
        if not isinstance(d, str) or not DATE_RE.match(d):
            log.err(f"{lbl}.date must be YYYY-MM-DD (got {d!r})")
        tid = r.get("topic_id")
        if not isinstance(tid, int):
            log.err(f"{lbl}.topic_id must be int")
        elif tid not in topic_ids:
            unknown.add(tid)
        if not isinstance(r.get("frequency"), int):
            log.err(f"{lbl}.frequency must be int")

    if unknown and unknown - {-1}:
        log.err(f"unknown topic ids: {sorted(unknown - {-1})}")

    if not log.errors:
        log.ok(f"{len(data)} rows")


def validate_documents(data_dir: Path, log: Log, topic_ids: set[int]) -> None:
    log.section("documents/")
    docs_dir = data_dir / "documents"
    if not docs_dir.is_dir():
        log.err("documents/ missing"); return

    found: set[int] = set()
    for f in sorted(docs_dir.glob("*.json")):
        m = TOPIC_FILE_RE.match(f.name)
        if not m:
            log.err(f"{f.name}: filename must be 'topic_<id>.json'")
            continue
        tid = int(m.group(1))
        if tid not in topic_ids:
            log.err(f"{f.name}: topic id {tid} not in topics.json")
            continue
        found.add(tid)

        docs = load_json(f, log)
        if not isinstance(docs, list):
            log.err(f"{f.name}: root must be array"); continue

        required = ("text", "topic_id", "probability",
                    "category", "year", "month", "day")

        bad = 0
        for i, doc in enumerate(docs):
            lbl = f"{f.name}[{i}]"
            if not isinstance(doc, dict):
                log.err(f"{lbl}: not object"); bad += 1; continue
            for k in required:
                if k not in doc:
                    log.err(f"{lbl}: missing '{k}'"); bad += 1
            if doc.get("topic_id") != tid:
                log.err(f"{lbl}.topic_id ({doc.get('topic_id')}) != filename ({tid})")
                bad += 1
            if not isinstance(doc.get("text"), str):
                log.err(f"{lbl}.text must be string")
            mo = doc.get("month")
            if isinstance(mo, str) and mo not in MONTHS:
                log.err(f"{lbl}.month unrecognized: {mo!r}")
            if not isinstance(doc.get("year"), int):
                log.err(f"{lbl}.year must be int")
            if not isinstance(doc.get("day"), int):
                log.err(f"{lbl}.day must be int")
            pt = doc.get("published_time")
            if pt is not None and not isinstance(pt, str):
                log.err(f"{lbl}.published_time must be string or null")
            pr = doc.get("probability")
            if not isinstance(pr, (int, float)):
                log.err(f"{lbl}.probability must be number")
            elif not 0 <= pr <= 1:
                log.warn(f"{lbl}.probability outside [0,1] ({pr})")
            if bad > 20:
                log.err(f"{f.name}: too many errors, stopping per-file checks")
                break

    missing = topic_ids - found - {-1}
    if missing:
        log.err(f"missing documents/topic_<id>.json for ids: {sorted(missing)}")

    if not log.errors:
        log.ok(f"{len(found)} document files present")


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Validate BERTopic-native export")
    ap.add_argument("--data", default="data")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data).resolve()
    print(f"Validating: {data_dir}")

    log = Log()
    if not data_dir.is_dir():
        print(f"\033[91m✗ Data folder not found: {data_dir}\033[0m")
        return 1

    topic_ids = validate_topics(data_dir, log)
    if topic_ids is None:
        return _summary(log, args.strict)

    validate_time_freq(data_dir, log, topic_ids)
    validate_documents(data_dir, log, topic_ids)

    return _summary(log, args.strict)


def _summary(log: Log, strict: bool) -> int:
    print("\n" + "=" * 60)
    print(f"Errors: {log.errors}  Warnings: {log.warnings}")
    print("=" * 60)
    if log.errors or (strict and log.warnings):
        print("\033[91mVALIDATION FAILED\033[0m")
        return 1
    print("\033[92mVALIDATION PASSED\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())