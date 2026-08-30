# rom write/ — CANDIDATE images. Nothing here has been flashed.

Only the candidate currently awaiting review lives at this level. Everything superseded — and
every intermediate of a chained build — moves to `superseded/`.

| file | what it is |
|---|---|
| `CANDIDATE_B_maf-plus-timing_2026-08-30.bin` | **AWAITING SYED'S REVIEW.** MAF plateau extrapolation + the re-shaped timing map. Built by chaining: `POSTFLASH3 → (--tune-maf --extrapolate-maf) → candidate A → (--tune-timing) → candidate B`. |

## The chained-build convention

The ECU holds ONE calibration image, so "two changes" never means two files to flash — it means
one image containing both. Each stage runs under its own clamps (`targets_kind` routes a
`"sensor"` proposal and a `"timing"` proposal down deliberately disjoint paths), so they are
applied as two proposals stacked onto one image, never merged into one.

Each step is audited **against its own base**, which keeps `--verify-flash`'s "exactly one
semantic table changed" rule intact with no loosening:

    --verify-flash A --rom POSTFLASH3 --expect maf      -> 1 table (sensor.maf_transfer)
    --verify-flash B --rom A          --expect timing   -> 1 table (ignition.base_timing)

and the composition is cross-checked separately with `--rom-diff POSTFLASH3 B`, which must
report exactly the tables you intended and no others.

**Flash only the LAST image in a chain.** Intermediates exist so each step could be audited
alone; flashing them in sequence would work but buys nothing and costs a flash cycle.

The `.bin` files are gitignored (a flashable image in version control invites someone flashing an
unreviewed one). The change reports and `SHA256SUMS.txt` are committed, so a candidate is always
reproducible from the stock ROM plus the committed logs.
