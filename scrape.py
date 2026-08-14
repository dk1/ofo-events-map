#!/usr/bin/env python3
"""Pull every OFO event off the public /events page into JSON.

No auth, no API key, one request. Stdlib only.
Run: python3 scrape.py > events.json
"""
import html
import json
import re
import sys
import urllib.request
from datetime import date

URL = "https://ofo25.wildapricot.org/events"


def fetch(url=URL):
    req = urllib.request.Request(url, headers={"User-Agent": "ofo-events-map/0.1 (https://github.com/dk1/ofo-events-map)"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8", "replace")


def text_of(fragment):
    t = re.sub(r"<script.*?</script>", " ", fragment, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def parse(page):
    # Each event's block starts at its /event-<id> anchor and runs to the next one.
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'/event-(\d+)"', page)]
    seen, blocks = set(), []
    for i, (pos, eid) in enumerate(marks):
        if eid in seen:
            continue
        seen.add(eid)
        end = next((p for p, e in marks[i + 1:] if e != eid), len(page))
        raw = page[pos:end]
        blocks.append((eid, raw, text_of(raw)))

    events = []
    for eid, raw, body in blocks:
        # The block starts at the details anchor, whose text is the event title.
        anchor = re.match(r'/event-\d+"[^>]*>(.*?)</a>', raw)
        title = text_of(anchor.group(1)) if anchor else None
        fields = split_fields(body)

        # Single-day events carry "When"; multi-day ones carry "Start"/"End".
        when = fields.get("When")
        if not when and fields.get("Start"):
            when = f"{fields['Start']} – {fields.get('End', '')}".strip()

        # Some leaders type the label into the field: "Location : Toronto".
        loc = re.sub(r"^(Location)?\s*:\s*", "", fields.get("Location", "")).strip(" .") or None

        start = parse_date(fields.get("Start") or fields.get("When"))
        end = parse_date(fields.get("End")) or start
        spaces = fields.get("Spaces left")
        events.append({
            "id": eid,
            "url": f"https://ofo25.wildapricot.org/event-{eid}",
            "title": title,
            "when": when,
            "start": start,
            "end": end,
            # A span of months is a registration window, not a trip that runs
            # for months: the conventions are three days in October but are
            # listed as Start 27 May / End 20 Sep. So the dates on those events
            # do not say when they happen, and a month filter must not pretend
            # they do. The threshold is 14 days rather than a week because the
            # young birders' camp genuinely runs for eight.
            "ongoing": bool(start and end and (date.fromisoformat(end) - date.fromisoformat(start)).days > 14),
            "location": loc,
            "spaces_left": int(spaces) if spaces and spaces.isdigit() else None,
            "registration": fields.get("_action"),
            "description": fields.get("_body"),
        })
    return events


# The rendered block is a run of labelled fields, then a registration control,
# then the free-text description. Splitting on the labels is what lets one
# parse serve both the single-day and multi-day layouts.
LABELS = ("When", "Start", "End", "Location", "Spaces left", "Registered")
ACTIONS = ("Register", "Join waitlist", "Registration is closed", "Already registered")


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def parse_date(text):
    """'23 Aug 2026 8:00 AM - 12:30 PM' -> '2026-08-23'. None if unparseable."""
    if not text:
        return None
    m = re.match(r"\s*(\d{1,2}) (%s) (\d{4})" % "|".join(MONTHS), text)
    if not m:
        return None
    day, mon, year = m.groups()
    return f"{year}-{MONTHS.index(mon) + 1:02d}-{int(day):02d}"


def split_fields(body):
    # The registration control ends the header. Every one of these words also
    # occurs in the prose below it, so the *first* occurrence is the boundary
    # and anything after it is description, not a field.
    action = re.search(r"\b(" + "|".join(ACTIONS) + r")\b", body)
    head, tail = (body[:action.start()], body[action.end():]) if action else (body, "")

    out = {"_action": action.group(1) if action else None}
    marks = list(re.finditer(r"\b(" + "|".join(LABELS) + r")\b", head))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(head)
        out[m.group(1)] = head[m.end():end].strip()
    out["_body"] = tail.strip()
    return out


if __name__ == "__main__":
    evs = parse(fetch())
    print(json.dumps(evs, indent=2), file=sys.stdout)
    print(f"{len(evs)} events", file=sys.stderr)
