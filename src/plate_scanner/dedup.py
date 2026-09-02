"""Avoids logging the same passing vehicle multiple times.

A plate stays in view across several frames as the car drives by, and OCR
noise means consecutive readings of the same plate aren't always
byte-identical. We treat two readings within ``window_seconds`` of each
other as the same sighting if they're within ``max_edit_distance`` of each
other, and only the first one gets stored.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

try:
    from Levenshtein import distance as _levenshtein_distance
except ImportError:  # pure-python fallback if python-Levenshtein isn't installed

    def _levenshtein_distance(a: str, b: str) -> int:
        if a == b:
            return 0
        if not a:
            return len(b)
        if not b:
            return len(a)
        previous_row = list(range(len(b) + 1))
        for i, ca in enumerate(a, start=1):
            current_row = [i]
            for j, cb in enumerate(b, start=1):
                insert_cost = current_row[j - 1] + 1
                delete_cost = previous_row[j] + 1
                replace_cost = previous_row[j - 1] + (ca != cb)
                current_row.append(min(insert_cost, delete_cost, replace_cost))
            previous_row = current_row
        return previous_row[-1]


@dataclass
class _Entry:
    text: str
    last_seen: float


class RecentPlateCache:
    def __init__(self, window_seconds: float = 30.0, max_edit_distance: int = 1):
        self._window_seconds = window_seconds
        self._max_edit_distance = max_edit_distance
        self._entries: list[_Entry] = []

    def is_duplicate(self, text: str, now: float | None = None) -> bool:
        """Returns True (and refreshes the match) if `text` was recently seen."""
        now = now if now is not None else time.time()
        self._prune(now)

        for entry in self._entries:
            if _levenshtein_distance(text, entry.text) <= self._max_edit_distance:
                entry.last_seen = now
                return True

        self._entries.append(_Entry(text=text, last_seen=now))
        return False

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_seconds
        self._entries = [e for e in self._entries if e.last_seen >= cutoff]
