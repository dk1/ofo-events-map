#!/usr/bin/env python3
"""Refuse a scrape that looks broken, so automation cannot deploy a blank map.

`scrape.py` finds events by matching anchors in the page HTML. If the markup
changes, or the site serves an error page, it matches nothing and exits 0 with
an empty list — so the guard is here, not there.

Run: python3 check.py <candidate.json> [committed.json]

Exits non-zero, and explains itself, if the candidate is empty, structurally
wrong, or has lost more than SHRINK of the published events that have not
happened yet. Past events are expected to drop off, so they don't count —
otherwise the end of a season reads as a parse failure.
"""
import json
import sys
from datetime import date

SHRINK = 0.3  # a fall of more than 30% is a parse failure, not a quiet week
MAX_FIELD = 150  # a longer title/location means the description bled in


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fail(msg):
    sys.exit(f"check: {msg}\ncheck: refusing to publish; keeping the last good data.")


def main(candidate_path, committed_path=None):
    try:
        events = load(candidate_path)
    except (OSError, json.JSONDecodeError) as e:
        fail(f"cannot read {candidate_path}: {e}")

    if not isinstance(events, list):
        fail(f"expected a list of events, got {type(events).__name__}")
    if not events:
        fail("scraped 0 events — the page layout probably changed")

    missing = [e for e in events if not e.get("id") or not e.get("title")]
    if missing:
        fail(f"{len(missing)} of {len(events)} events have no id or title")

    # The descriptions carry leaders' names and emails and are never published.
    # If one leaks into a short field, stop here rather than commit it.
    for e in events:
        for k in ("title", "location", "when"):
            v = e.get(k) or ""
            if len(v) > MAX_FIELD or "@" in v:
                fail(f"event {e['id']} {k} looks like description text: {v[:60]!r}...")

    # Compare against what is already published, when there is one to compare to.
    try:
        previous = load(committed_path) if committed_path else []
    except (OSError, json.JSONDecodeError):
        previous = []

    today = date.today().isoformat()
    upcoming = [e for e in previous if (e.get("end") or e.get("start") or today) >= today]
    if upcoming:
        floor = len(upcoming) * (1 - SHRINK)
        if len(events) < floor:
            fail(f"scraped {len(events)} events, but {len(upcoming)} published ones "
                 f"are still upcoming — below the floor of {floor:.0f}")
        print(f"check: {len(events)} events ({len(upcoming)} published still upcoming) — ok")
    else:
        print(f"check: {len(events)} events, nothing to compare against — ok")


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
