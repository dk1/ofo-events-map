# OFO events map

A map of [Ontario Field Ornithologists](https://ofo.ca) field trips, built from
their public [events page](https://ofo25.wildapricot.org/events).

**→ [View the map](https://dk1.github.io/ofo-events-map/)**

Pins carry the trip's date, location, spaces left and a link to register.
Filter by month, or hide the trips that are already full.

Unofficial, and not affiliated with OFO.

## Refreshing the data

```bash
python3 scrape.py > events.json   # one request to the events page
python3 geocode.py                # adds coordinates, in place
```

Both are stdlib-only — no dependencies to install. `geocode.py` caches every
lookup in `cache.json`, so a re-run only geocodes locations it has not seen.

Commit the changed `events.json` and the page is up to date. There is no
scheduled refresh: this is run by hand.

## Why the data is a file and not a live fetch

The page cannot fetch OFO's site itself. `ofo25.wildapricot.org` sends no
`Access-Control-Allow-Origin` header, so a browser blocks the request, and the
Wild Apricot API authenticates with credentials that cannot live in a public
page. Anything live needs a server of some kind. `NOTES.md` has the
measurements and the three options.

So "28 spaces left" is as fresh as the last commit — check the linked event
page before relying on it.

## Pins are approximate

Trip locations are free text typed by leaders — usually a town or a park
("Brighton", "Algonquin Provincial Park"), occasionally a set of coordinates,
sometimes a region. They are geocoded through
[Nominatim](https://nominatim.openstreetmap.org/), so a pin is the general area
and **never the meeting point**; the meeting point is in the trip description
on the event page.

Four events are hand-placed in `overrides.json`, either because the location
field is empty or because geocoding put them somewhere wrong. Add to that file,
keyed by event id, to correct another.

## Files

| | |
|---|---|
| `index.html` | the whole page — Leaflet from a CDN, no build step |
| `events.json` | what the page loads |
| `scrape.py` | events page → `events.json` |
| `geocode.py` | adds coordinates, applies `overrides.json`, caches |
| `overrides.json` | hand-placed coordinates, keyed by event id |
| `NOTES.md` | what was measured about the source, and what the parse still misses |

Trip descriptions are scraped but deliberately not published: they carry
leaders' names and contact emails, and the map has no use for them. They are
written to `events.full.json`, which is gitignored.
