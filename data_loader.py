"""Load and normalize BERTopic-native export for the visualizer."""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Optional

MONTHS: dict[str, int] = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June",
     "July", "August", "September", "October", "November", "December"], 1)}
MONTHS.update({m[:3]: n for m, n in list(MONTHS.items())})

TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?", re.I)
TOPIC_FILE_RE = re.compile(r"topic_(-?\d+)\.json$")


class DataStore:
    """In-memory store for BERTopic output. Outliers (topic -1) are skipped."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._topics: Optional[list[dict]] = None
        self._time_freq: Optional[dict[int, list[dict]]] = None
        self._doc_cache: dict[int, list[dict]] = {}

    # -- public ----------------------------------------------------------

    @property
    def topics(self) -> list[dict]:
        if self._topics is None:
            self._topics = self._load_topics()
        return self._topics

    def get_topic(self, topic_id: int) -> Optional[dict]:
        return next((t for t in self.topics if t["id"] == topic_id), None)

    def get_time_frequency(self, topic_id: int) -> list[dict]:
        if self._time_freq is None:
            self._time_freq = self._load_time_frequency()
        return self._time_freq.get(topic_id, [])

    def get_documents(self, topic_id: int) -> list[dict]:
        if topic_id not in self._doc_cache:
            self._doc_cache[topic_id] = self._load_documents(topic_id)
        return self._doc_cache[topic_id]

    @property
    def total_documents(self) -> int:
        return sum(t["frequency"] for t in self.topics)

    # -- loaders ---------------------------------------------------------

    def _load_topics(self) -> list[dict]:
        raw = json.loads((self.data_dir / "topics.json").read_text(encoding="utf-8"))
        out = []
        for t in raw:
            tid = t.get("Topic")
            if tid is None:
                continue
            name = t.get("Name", f"{tid}_topic")
            out.append({
                "id": tid,
                "name": name,
                "display_name": t.get("Custom Name") or self._display_name(name),
                "representation": t.get("Representation") or [],
                "frequency": int(t.get("Count", 0)),
                "percentage": round(float(t.get("perc", 0.0)), 4),
                "representative_text": self._first_representative(t),
                "words": [
                    {"word": str(w), "weight": float(p)}
                    for w, p in (t.get("word_weight") or [])
                    if isinstance(w, str) and isinstance(p, (int, float))
                ],
            })
        out.sort(key=lambda x: x["frequency"], reverse=True)
        return out

    def _load_time_frequency(self) -> dict[int, list[dict]]:
        raw = json.loads((self.data_dir / "dailytopicfreq.json").read_text(encoding="utf-8"))
        grouped: dict[int, list[dict]] = {}
        for r in raw:
            tid = r.get("topic_id")
            if tid is None or tid == -1:
                continue
            grouped.setdefault(tid, []).append({
                "date": r["date"],
                "frequency": int(r["frequency"]),
            })
        for rows in grouped.values():
            rows.sort(key=lambda x: x["date"])
        return grouped

    def _load_documents(self, topic_id: int) -> list[dict]:
        path = self.data_dir / "documents" / f"topic_{topic_id}.json"
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [self._normalize_doc(d, i, topic_id) for i, d in enumerate(raw)]

    # -- normalization helpers ------------------------------------------

    @staticmethod
    def _display_name(name: str) -> str:
        """`29_navy_ship_naval_port` → `Navy Ship Naval Port`."""
        m = re.match(r"^-?\d+_(.+)$", name)
        body = m.group(1) if m else name
        return body.replace("_", " ").title()

    @staticmethod
    def _first_representative(t: dict) -> str:
        docs = t.get("Representative_Docs") or []
        return docs[0] if docs else ""

    @staticmethod
    def _parse_date(d: dict) -> str:
        y = d.get("year")
        m = d.get("month")
        day = d.get("day")
        if isinstance(m, str):
            m = MONTHS.get(m) or MONTHS.get(m[:3]) or 1
        try:
            return f"{int(y):04d}-{int(m):02d}-{int(day):02d}"
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _parse_time(t) -> str:
        if not t:
            return ""
        m = TIME_RE.search(str(t).strip())
        if not m:
            return ""
        h, mi = int(m.group(1)), int(m.group(2))
        sec = int(m.group(3) or 0)
        ap = (m.group(4) or "").lower()
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mi:02d}:{sec:02d}"

    def _normalize_doc(self, d: dict, idx: int, topic_id: int) -> dict:
        return {
            "id": f"topic{topic_id}_doc{idx}",
            "headline": str(d.get("headline", d.get("text", ""))),
            "text": str(d.get("text", "")),
            "date": self._parse_date(d),
            "time": self._parse_time(d.get("published_time")),
            "url": d.get("url") or "",           # absent in your export → ""
            "category": str(d.get("category", "")),
            "topic_id": int(d.get("topic_id", topic_id)),
            "probability": float(d.get("probability", 0.0)),
        }