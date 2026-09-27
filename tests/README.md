# SnitchList tests

Functional tests for the SnitchList app. They extract the `<script>` from
`../index.html` at runtime, run it in Node under a minimal DOM stub, and
exercise the real analysis pipeline end to end — no browser needed.

## Run

```bash
npm test
# or
node tests/snitchlist.test.js
```

Requires only Node.js (no dependencies).

## Coverage (33 checks)

1. **Realistic mixed log** — known trackers flagged with company/category,
   clean domains land in unknowns, summary cards count correctly
2. **Suffix matching** — `sub.foo.doubleclick.net` matches `doubleclick.net`;
   `evil-doubleclick.net` correctly does *not* (not a true subdomain)
3. **Functional domains** — `functional`-category DB entries go to the clean table
4. **User verdicts** — mark snitch / mark clean / forget, localStorage persistence
5. **Parser edge cases** — IPv4 skipped, file extensions skipped,
   uppercase normalized, trailing dots handled
6. **Empty input** — prompts to paste log lines
7. **Sample + export** — sample button fills and analyzes; export downloads a
   markdown report
8. **HTML escaping** — no raw `<script>` in rendered table output

If you change `index.html`, run `npm test` before pushing. The test reads the
current `index.html`, so it always tests what's actually shipped.
