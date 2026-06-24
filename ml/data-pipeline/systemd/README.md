# Scheduled runner — `mlecu-corpus` (systemd user timer)

A **daily** (04:30 + ≤15 min jitter) user-level timer that runs one ingestion pass: git-pulls the
def/theory repos, re-scrapes the forum seeds (catching new posts), runs bounded forum **discovery**
(new tuning threads), and ingests any dropped PDFs. Lets the corpus accumulate passively while the
2nd GPU is being set up. Modeled on the Hardware Parser oneshot+timer pattern.

**Why daily:** the git sources (defs/theory) change over weeks, forum threads accrue slowly, and a
daily bounded browser crawl is gentle on legacygt's WAF. Plenty for "gather at a minimum."

## Install (one-time)
```bash
DP=~/Shared/Computing\ Projects/MLECU/ml/data-pipeline
mkdir -p ~/.local/bin ~/.config/systemd/user
cp "$DP/systemd/mlecu-corpus.sh" ~/.local/bin/mlecu-corpus-run.sh && chmod +x ~/.local/bin/mlecu-corpus-run.sh
cp "$DP/systemd/mlecu-corpus.service" "$DP/systemd/mlecu-corpus.timer" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now mlecu-corpus.timer
sudo loginctl enable-linger "$USER"     # one sudo line — lets the timer run while logged out
```

## Operate
- `systemctl --user list-timers mlecu-corpus.timer`   — next scheduled run
- `systemctl --user start mlecu-corpus.service`       — run a pass NOW (foreground-equivalent)
- `journalctl --user -u mlecu-corpus.service -f`      — watch / tail a run
- The service reads `inactive` between passes — that's correct (timer-fired oneshot; check the *timer*).

## Change the cadence
Edit `OnCalendar=` in `mlecu-corpus.timer` (e.g. `OnCalendar=*-*-* 0/6:00:00` for every 6 h), then
`systemctl --user daemon-reload && systemctl --user restart mlecu-corpus.timer`.
