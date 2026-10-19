# OFO events map — notes

What was measured about the source, and what the parse still misses. The
scraper is stdlib-only and has no dependencies.

## How the data is retrieved

**One unauthenticated GET of the events list view returns every event in
full:** `https://ofo25.wildapricot.org/events?EventViewMode=1&EventListViewMode=1`.
The site is Wild Apricot. Findings from probing it on 2026-08-14:

- The list page is 1.5MB of server-rendered HTML holding **all 34 upcoming
  events**, each with title, date/time, location string, spaces left,
  registration state and the *complete* trip description — the same text the
  per-event page shows. So there is no need to fetch 34 event pages.
- **There is no JSON endpoint to use.** No embedded event JSON, no XHR the
  calendar view calls (`/OFO-Event-Calendar` is another server-rendered page),
  no iCal export (`?format=ical` returns the same HTML), and
  `/Sys/Website/Modules/Events/…` 302s to login.
- **The Wild Apricot public API (`api.wildapricot.org`) needs an API key issued
  from OFO's admin account.** If OFO will provide one, it returns proper
  structured events and this scraper becomes unnecessary. Worth asking before
  hardening any of this.
- Event ids are stable and public: `/event-6431965`.
- **Bare `/events` serves whichever view OFO has set as the default.** In
  late Sept 2026 that became a calendar, with no spaces-left or registration
  state, and the scrape returned 0 events until it was pointed at the list
  view explicitly.

`scrape.py` parses the list page into `events.json` (checked in as a sample).

## The hard part is location, not retrieval

Locations are **free text typed by trip leaders**, with no coordinates:

- Mostly a town or park name — "Brighton", "Algonquin Provincial Park".
- One is literal DMS coordinates: `45°27'22.2"N 76°08'19.5"W`.
- Some are vague regions — "Ontario", "North Bay area", "Point Pelee and
  Surrounding Area".
- Some leak the field label: `Location : Toronto` (a leader typed it twice).
- The *actual meeting point* is usually only in the prose ("Meet 9:00 am at
  entrance to mine site at north end of County Road #6"), which is not
  machine-readable.

So the map pin is a geocode of a town name, i.e. roughly right and never the
meeting point. Any UI has to say so.

## Can the browser fetch it directly? No.

Asked because live registration counts ("28 spaces left") go stale in a
committed JSON. Measured, not assumed:

- `https://ofo25.wildapricot.org/events` returns **no
  `Access-Control-Allow-Origin` header**, so a `fetch` from the page is blocked
  by CORS. Confirmed by running it in a real browser on this page:
  `TypeError: Failed to fetch`. Nothing in the page can work around that —
  CORS is the server's decision, and `no-cors` gives an opaque response the
  script cannot read.
- **The Wild Apricot API cannot be called from a browser either**, and not
  only for CORS: it authenticates with OAuth client credentials, which would
  have to be in the page — i.e. published.

So live data needs *something* server-side. Three ways, cheapest first:

1. **A scheduled re-scrape.** A cron (GitHub Action) runs `scrape.py` +
   `geocode.py` and commits `events.json`. Page stays a static file, no
   runtime, no server to break; data is as fresh as the schedule. Spaces-left
   would be up to a day old.
2. **A tiny CORS proxy** — a Cloudflare Worker or a Lambda Function URL that
   fetches, parses and returns JSON with `Access-Control-Allow-Origin`. Data is
   live on every page load. ~30 lines, but it is a service to own, and it puts
   OFO's page behind a request every visitor makes.
3. **Ask OFO to enable CORS or issue an API key**, and pair the key with (2).
   Removes the scraping, not the server.

Geocoding, unlike the events, *can* move into the browser: Nominatim sends
CORS headers. It is rate-limited to 1 request/second though, so ~30 locations
is a 30-second wait on first load — which is why it stays a build step here,
with results cached in `cache.json`.

## Known gaps in the parse

- Trips not yet open for sign-up show no registration control, so their
  `registration` is null.
- Online events (location "Zoom") are deliberately left unplaced.
- `description` is the whole flattened block, including the registration
  furniture; it is not yet split into description / accessibility / contact.
