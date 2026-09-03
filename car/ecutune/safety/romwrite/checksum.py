"""SH7058 ROM checksum, derive, verify, and repair the Subaru checksum block.

DERIVED 2026-08-27, not documented anywhere upstream. `docs/ROADMAP.md` Phase E.4(c) left this
open ("verify at build time whether ECUFlash auto-fixes Subaru checksums at flash (believed
yes) or we implement checksum correction ourselves"), and the repo had zero checksum content.
The pointer came from the ECUFlash defs: every 1 MB Subaru ROM declares a `Checksum Fix` table
at storageaddress 0xFFB80, and its `ChecksumFix` scaling is never defined anywhere in the tree
-- a dead reference marking the block's location and nothing else. The format below was
reverse-engineered from that address.

SCOPE, STATED HONESTLY. The block offset below is validated for OUR ROM family (1 MB SH7058,
`3B12504206` / A2WC411D). Foreign ROMs on disk do NOT parse at the same offset -- several put
unrelated data there -- so `read_records` refuses rather than guessing, and callers get
`UnknownChecksumLayout` instead of a plausible-looking wrong answer. Do not extend the offset
table to another family without validating it on real images of that family first.

FORMAT. At `BLOCK_OFFSET` sits an array of 12-byte big-endian records:

    struct { uint32 start; uint32 end_inclusive; uint32 stored; }

INVARIANT, verified on both copies of our own ROM (the car read and the harvested stock
reference), and on a synthetic corruption round-trip (flip a byte in a covered region -> the
record fails -> repair -> it passes, with only the `stored` field touched):

    ( sum of BE-uint32 words over data[start .. end_inclusive]  +  stored )  mod 2**32
        ==  0x5AA5A55A

so repairing a record is `stored = (MAGIC - running_sum) mod 2**32`. Unused slots read
`start=end=0, stored=MAGIC` -- the magic standing in for "no region" -- and are skipped. The
array is terminated by 0xFFFFFFFF filler.

WHY THE REPAIR IS ONE PASS. The block sits OUTSIDE every region it covers (our ROM's only
active record spans 0x2000..0xFFAF7, and the block is at 0xFFB80), so rewriting `stored` cannot
change any sum. It is a fixed point: compute once, write once, done. A block that covered
itself would need iteration to converge, and might not.

We compute this ourselves rather than trusting ECUFlash to fix it on save, because "believed
yes" is not a verification and a ROM that flashes with a bad checksum is a brick.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = 0x5AA5A55A
RECORD_SIZE = 12
MASK32 = 0xFFFFFFFF
_FILLER = 0xFFFFFFFF


class UnknownChecksumLayout(ValueError):
    """The bytes at the expected block offset are not a checksum array we recognise.

    Raised instead of returning a partial answer: a checksum module that guesses is worse than
    one that refuses, because the failure mode is a ROM that flashes and bricks."""

# 1 MB ROMs put the block here; 512 KB ROMs at 0x7FB80. Keyed by ROM size so a caller cannot
# apply the wrong one to the wrong image.
BLOCK_OFFSET = {1024 * 1024: 0xFFB80, 512 * 1024: 0x7FB80}


@dataclass(frozen=True)
class ChecksumRecord:
    index: int
    offset: int          # absolute file offset of this record
    start: int
    end: int             # INCLUSIVE
    stored: int
    computed: int        # the sum over [start, end]

    @property
    def ok(self) -> bool:
        return (self.computed + self.stored) & MASK32 == MAGIC

    @property
    def expected(self) -> int:
        """The `stored` value that would satisfy the invariant."""
        return (MAGIC - self.computed) & MASK32


def block_offset(data: bytes | bytearray) -> int:
    try:
        return BLOCK_OFFSET[len(data)]
    except KeyError:
        raise ValueError(f"no known checksum block offset for a {len(data)}-byte ROM "
                         f"(known: {sorted(BLOCK_OFFSET)})") from None


def _sane_region(data: bytes | bytearray, start: int, end_inclusive: int) -> bool:
    """Could this record plausibly describe a region of THIS image?"""
    span = end_inclusive - start + 1
    return (start < end_inclusive < len(data)) and span % 4 == 0


def _sum_region(data: bytes | bytearray, start: int, end_inclusive: int) -> int:
    """Sum big-endian uint32 words over [start, end_inclusive], mod 2**32."""
    if not _sane_region(data, start, end_inclusive):
        raise UnknownChecksumLayout(
            f"region 0x{start:X}..0x{end_inclusive:X} is not a whole number of 32-bit words "
            f"inside a {len(data)}-byte ROM")
    n_words = (end_inclusive - start + 1) // 4
    return sum(struct.unpack_from(">%dI" % n_words, data, start)) & MASK32


def read_records(data: bytes | bytearray) -> list[ChecksumRecord]:
    """Every ACTIVE record in the block. Empty slots and the 0xFFFFFFFF filler are skipped.

    Raises UnknownChecksumLayout if the first active record does not describe a sane region -
    that means the bytes here are not our checksum array at all.
    """
    base = block_offset(data)
    out: list[ChecksumRecord] = []
    for i in range((len(data) - base) // RECORD_SIZE):
        off = base + i * RECORD_SIZE
        if off + RECORD_SIZE > len(data):
            break
        start, end, stored = struct.unpack_from(">III", data, off)
        if start == _FILLER:                      # end of array
            break
        if start == 0 and end == 0:               # unused slot (stored == MAGIC)
            continue
        out.append(ChecksumRecord(i, off, start, end, stored, _sum_region(data, start, end)))
    return out


def verify(data: bytes | bytearray) -> list[ChecksumRecord]:
    """Return the records that FAIL the invariant (empty list == ROM is internally consistent)."""
    return [r for r in read_records(data) if not r.ok]


def repair(data: bytearray) -> list[ChecksumRecord]:
    """Rewrite every failing record's `stored` field in place. Returns the records repaired.

    One pass is provably enough: the block lies outside every covered region, so writing here
    cannot perturb any sum. Asserted, not assumed -- a ROM whose block covered itself would
    raise rather than silently converge on nothing.
    """
    base = block_offset(data)
    repaired: list[ChecksumRecord] = []
    for r in read_records(data):
        if r.start <= base <= r.end:
            raise ValueError(f"checksum record {r.index} covers the checksum block itself "
                             f"(0x{r.start:X}..0x{r.end:X} contains 0x{base:X}), a one-pass "
                             "repair is not valid for this ROM layout")
        if not r.ok:
            struct.pack_into(">I", data, r.offset + 8, r.expected)
            repaired.append(r)
    return repaired
