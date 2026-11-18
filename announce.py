#!/usr/bin/env python3
"""List trips in the new scrape that the published file did not have.

Run: python3 announce.py <published.json> <candidate.json>

Prints a Markdown list for a GitHub issue, or nothing when there is nothing
new — including when there is no published file yet, so a first run does not
announce every trip. Descriptions are never included: they carry leaders'
names and emails.
"""
import json
import sys


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def main(published_path, candidate_path):
    published = load(published_path)
    if not published:
        return
    seen = {e["id"] for e in published}
    new = [e for e in load(candidate_path) if e["id"] not in seen]
    for e in new:
        details = " · ".join(x for x in (e.get("when"), e.get("location")) if x)
        print(f"- [{e['title']}]({e['url']})" + (f" — {details}" if details else ""))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
