# Harvesting ROM binaries from forum attachments

Stock/tuned ROMs live as phpBB **attachments**. The thread text is public (we already scrape it),
but the attachment *download* needs a logged-in session. RomRaider returns **403** to guests
(verified 2026-07-03). This is not an unbreakable wall; it's a one-time cookie. With your own free
account's session cookie, the harvester downloads ROMs exactly like your browser does, same threads
we already crawl, just targeting the `download/file.php?id=N` links.

ROMs are **car-side data** (they feed the `car/ecu` ROM-value reader + a reference library of
stock/tuned calibrations), NOT the LLM text corpus; they land as files under `data/raw/roms/`
(gitignored) with a `manifest.json`, never as corpus Documents.

## One-time setup (per board)

1. Register a free account on the board (e.g. romraider.com) and log in.
2. Export your session cookie for that domain. Easiest: browser DevTools →
   **Application/Storage → Cookies → the board domain** → copy the phpBB cookies
   (`phpbb3_*_sid`, `phpbb3_*_u`, `phpbb3_*_k`). Or the Network tab: copy any request's
   `Cookie:` header value.
3. Save it to `data/raw/.cookies/<board>.txt` as **either**:
   - a raw `Cookie:` header string: `phpbb3_abc_sid=...; phpbb3_abc_u=...; phpbb3_abc_k=...`
   - or `<board>.json` as `{"phpbb3_abc_sid": "...", "phpbb3_abc_u": "..."}`

   For the default board that path is `data/raw/.cookies/romraider.txt`.

## Run

```
cd ml/data-pipeline && PYTHONPATH=. .venv/bin/python -m corpus_pipeline.cli --harvest-roms
```

It downloads ROM-extension attachments (`.srf/.hex/.bin/.rom` always; `.zip/.7z` only when the
filename hints a ROM) from the configured `rom_harvest.boards` threads + ROM-titled threads in the
configured subforums, dedups against the manifest, and skips anything already fetched. Re-run anytime;
it only fetches new attachments. A stale/expired cookie shows up as `blocked` (the download returns
the login HTML instead of a binary), refresh the cookie.

## Notes

- **The 2005 FXT 4EAT stock ROM** (`3B12504206`, file `05 FXT 4EAT ...srf.zip`) is attached to the
  seeded thread; that's your platform's factory calibration; grab it first.
- `.srf` is the RomRaider/ECUFlash ROM image format; the future ROM-value reader resolves it against
  the ingested SubaruDefs (via the semantic-table adapters) to extract real calibration values.
- Respect the boards: conservative `rate_limit_per_min`, and this is your own logged-in account.
