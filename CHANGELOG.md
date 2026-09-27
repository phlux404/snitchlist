# Changelog

## 2026-09-26 — First test suite
- Added `tests/snitchlist.test.js`: 34 functional checks run via `npm test`
  (Node only, no dependencies, no browser). Covers tracker flagging, suffix
  matching, user verdicts + localStorage, parser edge cases, sample/export,
  and HTML escaping. The suite extracts the script from the current
  `index.html` at runtime, so it always tests what's shipped.
- README: new Tests section.

## 2026-09-24 — Initial public release
- Published to GitHub (GPL-3.0) with GitHub Pages hosting.
- Paste NextDNS, TrackerControl, or DNS logs; flag snitch domains with company and category.
- Local verdict memory: mark unknown domains snitch or clean, remembered on-device (localStorage).
- Markdown report export.
- README credit line: built with assistance from Muse.
