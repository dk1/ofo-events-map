#!/usr/bin/env python3
"""Add coordinates to events.json, in place.

Nominatim, one request a second (their usage policy), results cached in
cache.json so a re-run only geocodes what is new. Ontario is appended to the
query and results are bounded to the province, because a bare "Brighton" or
"Waterloo" resolves to England otherwise.

    python3 scrape.py > events.json && python3 geocode.py
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache.json")
OVERRIDES = os.path.join(HERE, "overrides.json")
EVENTS = os.path.join(HERE, "events.json")
FULL = os.path.join(HERE, "events.full.json")
UA = "ofo-events-map/0.1 (https://github.com/dk1/ofo-events-map)"
ONTARIO = (-95.2, 41.6, -74.3, 56.9)  # west, south, east, north
# Webinars have a location of "Zoom", which Nominatim will happily pin to a
# business of that name somewhere in Ontario.
ONLINE = re.compile(r"\b(zoom|online|virtual|webinar|teams)\b", re.I)


def parse_dms(text):
    """Return (lat, lng) if the location is literal coordinates, else None."""
    m = re.match(
        r"""\s*(\d+)°\s*(\d+)'\s*([\d.]+)"?\s*([NS])[,\s]+(\d+)°\s*(\d+)'\s*([\d.]+)"?\s*([EW])""",
        text,
    )
    if not m:
        return None
    d1, m1, s1, h1, d2, m2, s2, h2 = m.groups()
    lat = (int(d1) + int(m1) / 60 + float(s1) / 3600) * (-1 if h1 == "S" else 1)
    lng = (int(d2) + int(m2) / 60 + float(s2) / 3600) * (-1 if h2 == "W" else 1)
    return round(lat, 6), round(lng, 6)


def nominatim(query):
    params = urllib.parse.urlencode({
        "q": f"{query}, Ontario, Canada",
        "format": "json",
        "limit": 1,
        "viewbox": ",".join(str(v) for v in ONTARIO),
        "bounded": 1,
    })
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{params}", headers={"User-Agent": UA}
    )
    try:
        with urllib.request.urlopen(req) as r:
            hits = json.load(r)
    except urllib.error.HTTPError as e:
        # A 400 is this query being unusable ("Query is too long."): leave it
        # unplaced rather than lose every other update. Anything else may be
        # transient, and a miss is cached for good, so fail and retry tomorrow.
        if e.code != 400:
            raise
        print(f"nominatim: HTTP 400 for {query[:80]!r}: {e.read()[:200]!r}", file=sys.stderr)
        return None
    if not hits:
        return None
    return round(float(hits[0]["lat"]), 6), round(float(hits[0]["lon"]), 6)


def main():
    events = json.load(open(EVENTS))
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    overrides = json.load(open(OVERRIDES)) if os.path.exists(OVERRIDES) else {}

    for ev in events:
        # A hand-placed point wins over anything derivable, and is the only fix
        # for an event whose Location field is empty — there is no text to
        # geocode and no cache key to correct.
        if ev["id"] in overrides:
            ev["lat"] = overrides[ev["id"]]["lat"]
            ev["lng"] = overrides[ev["id"]]["lng"]
            ev["geocode_source"] = "override"
            continue
        loc = ev.get("location")
        if not loc or ONLINE.search(loc):
            ev["lat"] = ev["lng"] = None
            ev["geocode_source"] = "online" if loc else None
            continue
        if loc not in cache:
            point = parse_dms(loc)
            if point:
                cache[loc] = {"lat": point[0], "lng": point[1], "source": "dms"}
            else:
                # A leader's free text is often several places ("Grimsby
                # Wetlands: Biggar Lagoons"); try the whole string, then the
                # first clause, before giving up.
                for attempt in (loc, re.split(r"[:;(]| and | near ", loc)[0].strip()):
                    hit = nominatim(attempt)
                    time.sleep(1)
                    if hit:
                        cache[loc] = {"lat": hit[0], "lng": hit[1], "source": f"nominatim:{attempt}"}
                        break
                else:
                    cache[loc] = {"lat": None, "lng": None, "source": "unresolved"}
                    print(f"unresolved: {loc}")
        ev["lat"] = cache[loc]["lat"]
        ev["lng"] = cache[loc]["lng"]
        ev["geocode_source"] = cache[loc]["source"]

    json.dump(cache, open(CACHE, "w"), indent=2, sort_keys=True)

    # The full text stays on this machine and is gitignored. It carries trip
    # leaders' names, meeting points and contact emails — all of it already
    # public on OFO's own site, but republishing other people's contact details
    # in a file that is not the map's to show is a different act from linking
    # to the page that holds them. It is kept locally because it is where the
    # meeting points for overrides.json are read from.
    json.dump(events, open(FULL, "w"), indent=2)
    published = [{k: v for k, v in ev.items() if k != "description"} for ev in events]
    json.dump(published, open(EVENTS, "w"), indent=2)

    placed = sum(1 for e in events if e.get("lat"))
    print(f"{placed} of {len(events)} events placed")


if __name__ == "__main__":
    main()
