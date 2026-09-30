#!/usr/bin/env python3
"""Validate the JSON export consumed by the NewsExplorer website."""
from __future__ import annotations

import argparse
import calendar
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

MONTHS = {
    name: number
    for number, name in enumerate(
        ("January", "February", "March", "April", "May", "June",
         "July", "August", "September", "October", "November", "December"),
        1,
    )
}
MONTHS.update({name[:3]: number for name, number in list(MONTHS.items())})

TOPIC_FILE_RE = re.compile(r"^topic_(-?\d+)\.json$")
TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?$", re.I)


class Log:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0

    def ok(self, message: str) -> None:
        print(f"  \033[92m✓\033[0m {message}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"  \033[93m!\033[0m {message}")

    def err(self, message: str) -> None:
        self.errors += 1
        print(f"  \033[91m✗\033[0m {message}")

    def section(self, title: str) -> None:
        print(f"\n\033[1m{title}\033[0m")


def load_json(path: Path, log: Log) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.err(f"{path.name}: {exc}")
        return None


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_date(value: Any, monthly: bool) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split("-")
    expected = 2 if monthly else 3
    if len(parts) != expected or any(not part.isdigit() for part in parts):
        return False
    year, month = int(parts[0]), int(parts[1])
    if not 1 <= month <= 12:
        return False
    if monthly:
        return len(parts[0]) == 4 and len(parts[1]) == 2 and year > 0
    day = int(parts[2])
    return (
        len(parts[0]) == 4 and len(parts[1]) == 2 and len(parts[2]) == 2
        and year > 0 and 1 <= day <= calendar.monthrange(year, month)[1]
    )


def validate_metadata(data_dir: Path, log: Log) -> None:
    """Metadata is not read by the current server, but should remain valid JSON."""
    log.section("metadata.json")
    path = data_dir / "metadata.json"
    if not path.is_file():
        log.warn("metadata.json missing (not required by the website)")
        return
    data = load_json(path, log)
    if isinstance(data, (dict, list)):
        log.ok(f"{type(data).__name__}")
    elif data is not None:
        log.err("root must be an object")


def validate_topics(data_dir: Path, log: Log) -> tuple[set[int], dict[int, int]]:
    log.section("topics.json")
    path = data_dir / "topics.json"
    if not path.is_file():
        log.err("topics.json missing")
        return set(), {}
    data = load_json(path, log)
    if not isinstance(data, list):
        log.err("root must be an array")
        return set(), {}

    topic_ids: set[int] = set()
    topic_counts: dict[int, int] = {}
    for index, topic in enumerate(data):
        label = f"topics[{index}]"
        if not isinstance(topic, dict):
            log.err(f"{label}: must be an object")
            continue

        topic_id = topic.get("Topic")
        if not isinstance(topic_id, int) or isinstance(topic_id, bool):
            log.err(f"{label}.Topic must be an integer")
            continue
        if topic_id in topic_ids:
            log.err(f"{label}: duplicate Topic id {topic_id}")
        topic_ids.add(topic_id)

        count = topic.get("Count", 0)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            log.err(f"{label}.Count must be a non-negative integer")
        else:
            topic_counts[topic_id] = count

        name = topic.get("Name", f"{topic_id}_topic")
        if not isinstance(name, str):
            log.err(f"{label}.Name must be a string when present")

        representation = topic.get("Representation", [])
        if not isinstance(representation, list) or not all(isinstance(word, str) for word in representation):
            log.err(f"{label}.Representation must be an array of strings")

        percentage = topic.get("perc", 0.0)
        if not is_number(percentage) or percentage < 0:
            log.err(f"{label}.perc must be a non-negative number")

        weights = topic.get("word_weight", [])
        if not isinstance(weights, list):
            log.err(f"{label}.word_weight must be an array")
        else:
            for word_index, pair in enumerate(weights):
                if not (isinstance(pair, list) and len(pair) == 2
                        and isinstance(pair[0], str) and is_number(pair[1])
                        and pair[1] >= 0):
                    log.err(f"{label}.word_weight[{word_index}] must be [string, non-negative number]")

        representatives = topic.get("Representative_Docs", [])
        if not isinstance(representatives, list) or not all(isinstance(doc, str) for doc in representatives):
            log.err(f"{label}.Representative_Docs must be an array of strings when present")

    if not log.errors:
        log.ok(f"{len(topic_ids)} topic entries")
    return topic_ids, topic_counts


def validate_frequency_file(
    data_dir: Path, log: Log, topic_ids: set[int], filename: str, monthly: bool
) -> dict[int, int]:
    log.section(filename)
    path = data_dir / filename
    if not path.is_file():
        log.err(f"{filename} missing")
        return {}
    data = load_json(path, log)
    if not isinstance(data, list):
        log.err("root must be an array")
        return {}

    totals: dict[int, int] = {}
    seen: set[tuple[str, int]] = set()
    for index, row in enumerate(data):
        label = f"{filename}[{index}]"
        if not isinstance(row, dict):
            log.err(f"{label}: must be an object")
            continue
        date = row.get("date")
        if not validate_date(date, monthly):
            log.err(f"{label}.date must be {'YYYY-MM' if monthly else 'YYYY-MM-DD'}")
        topic_id = row.get("topic_id")
        if not isinstance(topic_id, int) or isinstance(topic_id, bool):
            log.err(f"{label}.topic_id must be an integer")
        elif topic_id not in topic_ids:
            log.err(f"{label}.topic_id {topic_id} is not in topics.json")
        frequency = row.get("frequency")
        if not isinstance(frequency, int) or isinstance(frequency, bool) or frequency < 0:
            log.err(f"{label}.frequency must be a non-negative integer")
        elif isinstance(topic_id, int) and isinstance(date, str):
            key = (date, topic_id)
            if key in seen:
                log.err(f"{label}: duplicate date/topic row {key}")
            seen.add(key)
            totals[topic_id] = totals.get(topic_id, 0) + frequency

    if not log.errors:
        log.ok(f"{len(data)} rows")
    return totals


def validate_documents(data_dir: Path, log: Log, topic_ids: set[int]) -> dict[int, int]:
    log.section("documents/")
    directory = data_dir / "documents"
    if not directory.is_dir():
        log.err("documents/ missing")
        return {}

    found: set[int] = set()
    counts: dict[int, int] = {}
    for path in sorted(directory.glob("*.json")):
        match = TOPIC_FILE_RE.fullmatch(path.name)
        if not match:
            log.err(f"{path.name}: filename must be topic_<id>.json")
            continue
        topic_id = int(match.group(1))
        if topic_id not in topic_ids:
            log.err(f"{path.name}: topic id {topic_id} is not in topics.json")
            continue
        found.add(topic_id)
        documents = load_json(path, log)
        if not isinstance(documents, list):
            log.err(f"{path.name}: root must be an array")
            continue
        counts[topic_id] = len(documents)

        for index, document in enumerate(documents):
            label = f"{path.name}[{index}]"
            if not isinstance(document, dict):
                log.err(f"{label}: must be an object")
                continue
            text = document.get("text")
            headline = document.get("headline")
            if not isinstance(text, str) and not isinstance(headline, str):
                log.err(f"{label}: requires a string headline or text")
            if text is not None and not isinstance(text, str):
                log.err(f"{label}.text must be a string when present")
            if headline is not None and not isinstance(headline, str):
                log.err(f"{label}.headline must be a string when present")
            if document.get("url") is not None and not isinstance(document.get("url"), str):
                log.err(f"{label}.url must be a string when present")
            if document.get("category") is not None and not isinstance(document.get("category"), str):
                log.err(f"{label}.category must be a string when present")
            if document.get("topic_id") != topic_id:
                log.err(f"{label}.topic_id must equal its filename topic id {topic_id}")
            probability = document.get("probability")
            if not is_number(probability) or not 0 <= probability <= 1:
                log.err(f"{label}.probability must be a number in [0, 1]")
            validate_document_date(document, label, log)
            validate_document_time(document.get("published_time"), label, log)

    missing = topic_ids - found
    if missing:
        log.err(f"missing document files for topic ids: {sorted(missing)}")
    if not log.errors:
        log.ok(f"{len(found)} document files present")
    return counts


def validate_document_date(document: dict[str, Any], label: str, log: Log) -> bool:
    year, month, day = document.get("year"), document.get("month"), document.get("day")
    if not isinstance(year, int) or isinstance(year, bool) or year <= 0:
        log.err(f"{label}.year must be a positive integer")
        return False
    if isinstance(month, str):
        month_number = MONTHS.get(month)
    elif isinstance(month, int) and not isinstance(month, bool):
        month_number = month
    else:
        month_number = None
    if not isinstance(month_number, int) or not 1 <= month_number <= 12:
        log.err(f"{label}.month must be a full name, 3-letter name, or number 1-12")
        return False
    if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= calendar.monthrange(year, month_number)[1]:
        log.err(f"{label}.day is not valid for the supplied year and month")
        return False
    return True


def validate_document_time(value: Any, label: str, log: Log) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        log.err(f"{label}.published_time must be a string or null")
        return
    match = TIME_RE.fullmatch(value.strip())
    if not match:
        log.err(f"{label}.published_time is not a supported time")
        return
    hour, minute = int(match.group(1)), int(match.group(2))
    second = int(match.group(3) or 0)
    meridiem = match.group(4)
    max_hour = 12 if meridiem else 23
    min_hour = 1 if meridiem else 0
    if not min_hour <= hour <= max_hour or minute > 59 or second > 59:
        log.err(f"{label}.published_time has an invalid hour, minute, or second")


def compare_counts(
    log: Log, topic_counts: dict[int, int], document_counts: dict[int, int], monthly_totals: dict[int, int]
) -> None:
    for topic_id, expected in topic_counts.items():
        documents = document_counts.get(topic_id)
        if documents is not None and documents != expected:
            log.err(f"topic {topic_id}: Count={expected}, but documents contain {documents} rows")
        frequency = monthly_totals.get(topic_id)
        if frequency is not None and frequency != expected:
            log.err(f"topic {topic_id}: Count={expected}, but monthly frequencies sum to {frequency}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate NewsExplorer JSON data")
    parser.add_argument("--data", default="data", help="data directory (default: data)")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    args = parser.parse_args()

    data_dir = Path(args.data).resolve()
    print(f"Validating: {data_dir}")
    log = Log()
    if not data_dir.is_dir():
        print(f"\033[91m✗ Data folder not found: {data_dir}\033[0m")
        return 1

    validate_metadata(data_dir, log)
    topic_ids, topic_counts = validate_topics(data_dir, log)
    validate_frequency_file(data_dir, log, topic_ids, "dailytopicfreq.json", monthly=False)
    monthly_totals = validate_frequency_file(data_dir, log, topic_ids, "monthlytopicfreq.json", monthly=True)
    document_counts = validate_documents(data_dir, log, topic_ids)
    compare_counts(log, topic_counts, document_counts, monthly_totals)
    return summary(log, args.strict)


def summary(log: Log, strict: bool) -> int:
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
