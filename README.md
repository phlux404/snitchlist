# SnitchList

**Whose phone is it anyway.**

Paste a NextDNS, TrackerControl, or DNS log. Find out who's snitching.

*Built with assistance from [Muse](https://muse.ai) — Meta's personal AI.*

## Privacy

100% client-side. The whole thing is a single HTML file — no server, no analytics,
no network calls, no trackers (obviously). Nothing you paste ever leaves the page.
Download it and run it air-gapped if you like. That property is the point, and any
hosted copy should preserve it: this is a static file, not a service.

## Use

1. Open `index.html` in any browser (or visit the hosted page).
2. Paste log lines, or drop a `.txt` / `.csv` / `.log` / `.json` file.
3. Hit **Analyze**.

Flagged domains show company, category, and hit counts. Unknown domains are yours
to judge — mark them snitch or clean and SnitchList remembers your verdicts on that
device (localStorage, never leaves the browser). Export a markdown report when done.

## The database

`DB` at the top of the `<script>` in `index.html`:

```js
["domain-suffix.example", "Company", "category"],
```

Categories: `ads`, `analytics`, `tracking`, `crash`, `consent`, `social`, `functional`.
Suffix matching is automatic — `["example.com", ...]` also catches `sub.example.com`.

The database is a starting point, not gospel. Runtime evidence beats static claims:
verify, then mark.

## Contribute

Caught a snitch in the wild? Add it:

1. Add one line to `DB` in `index.html`.
2. Open a PR with the domain, the company behind it, and what you caught it doing —
   a log snippet or a short write-up of your runtime catch.

## Host it

It's a static file. On GitHub Pages: push to a repo, Settings → Pages → deploy from
branch. Done. No build step, no backend, nothing to maintain.

## License

GPL-3.0 — free software, keep it that way. See `LICENSE`.
