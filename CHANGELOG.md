# Changelog

## 2026-10-12 — Zero-day detection
- Added offline zero-day tracker detection: calibrated Shannon entropy flags
  (threshold 3.5 bits, 3.0% measured FP rate on 33 labeled benign domains,
  catches 100% of synthetic DGA domains), 21 SDK signature patterns
  (Firebase, Crashlytics, AppsFlyer, Branch, etc.), static ASN database for
  known tracker infrastructure, and TLS cert org reputation database.
- Unknown domains now show detection signals with checkable reasons and
  confidence levels; export report includes a "Flagged unknowns" section.
- Still 100% offline — no network calls added.
- Test suite: 53 passing (34 pre-existing + 19 new covering entropy math,
  calibration FP rate, SDK matching, ASN lookups, signal rendering, export).

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
