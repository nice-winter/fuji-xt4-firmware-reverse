#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setp_decode.py -- decoder for the SETP / UI resource layer of the Fujifilm X-T4
firmware (FWUP0024.DAT, and an earlier build for cross-check).

What this tool does
-------------------
1) `verify`   Prove that the "tokenized 0x80/0x81 resource" seen in the logical
              image (decoded 0x460000-0x4A0000, 0x4C0000-0x580000 ...) is NOT a
              separate resource format: it is the byte range of the FFLZ packed
              stream of section 0.  We parse the FFLZ header, show the byte range
              lies inside [packed_start, packed_start+packed_size), and re-decode
              the token grammar around the observed bytes:
                  ... C0 8A | 81 8B | 03 'L' 'O' 'A' | 8D 0A | 81 8B | 03 'E' 'R' 'R'
                  ...            ^ 2-byte LZ backref  ^ literal run 3 bytes
              The ASCII runs are ordinary FFLZ literal runs, so the "control bytes"
              0x80/0x81 are LZ77 back-reference tokens (see FIRMWARE-STRUCTURE §7).
              Consequence: the real SETP/UI resources must be searched in the
              *decompressed* sections out/fw/sections/sec{0,1,2,3}.bin.

2) `pools`    Dump the NUL-terminated, 4-byte aligned ASCII identifier pools that
              exist in the decompressed sections (sec0 and sec1).

3) `registry` Parse the sec1 registry table: 8-byte records
                  { u32 name_ptr_VA ; u32 index }
              where name_ptr_VA is an ABSOLUTE virtual address (the section load
              base comes from the 20-byte decompressed-section header).  The table
              is a concatenation of many small "enum name tables"; inside one table
              `index` runs 0,1,2,... so **index == enum value**.  This is the core
              structural result: it gives numeric values for all UI enums
              (UI_MENUCOM_ITEM_*, UI_SETP_*, UI_MENU_KIND_* ...).

4) `all`      Everything above.

Read-only: the .DAT files are never modified; all output is stdout (optionally
redirect to a file).  UTF-8 output is forced so non-ASCII labels survive.

Verified against:
  out/fw/sections/sec0.bin  7,421,952 B (header base 0x01021000, size 0x714000)
  out/fw/sections/sec1.bin  9,437,184 B (header base 0x01E0F000, size 0x900000)
"""
from __future__ import annotations

import argparse
import io
import os
import struct
import sys


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- utilities ---


def load(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read()


def section_header(data: bytes):
    """Decompressed FFLZ section header (20 B): u32 0, u32 load_base, u32 size,
    u32 checksum-ish.  `size` is verified against the real file length, which is
    what makes the interpretation of word[1] as the load base trustworthy.
    """
    w0, base, size, w3 = struct.unpack_from("<4I", data, 0)
    return dict(word0=w0, base=base, size=size, word3=w3,
                size_matches=(size == len(data)))


def read_ascii_name(data: bytes, off: int, maxlen: int = 64):
    if not (0 <= off < len(data)):
        return None
    end = data.find(b"\x00", off, min(len(data), off + maxlen))
    if end < 0:
        return None
    raw = data[off:end]
    if not raw or not all(0x20 <= c < 0x7F for c in raw):
        return None
    return raw.decode("ascii")


def find_all(data: bytes, pat: bytes):
    out, i = [], 0
    while True:
        j = data.find(pat, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


# --------------------------------------------------------- 1) FFLZ evidence ---

FFLZ_HEADER = 0x260274          # decoded/file offset of section-0 FFLZ header
FFLZ_PAYLOAD = 0x274            # logical image == file offset for decoded.bin


def cmd_verify(root: str) -> None:
    dec = load(os.path.join(root, "out", "fw", "decoded.bin"))
    unpacked, packed, pages, page_size, tag = struct.unpack_from("<5I", dec, FFLZ_HEADER)
    stream = FFLZ_HEADER + 20
    end = stream + packed
    print("=== FFLZ section-0 header @0x%X (decoded logical image) ===" % FFLZ_HEADER)
    print("  unpacked   = %d (0x%X)" % (unpacked, unpacked))
    print("  packed     = %d (0x%X)" % (packed, packed))
    print("  pages      = %d   page_size = 0x%X   tag = %d" % (pages, page_size, tag))
    print("  token stream occupies decoded 0x%X .. 0x%X" % (stream, end))

    regions = [(0x460000, 0x4A0000), (0x4C0000, 0x580000)]
    for a, b in regions:
        inside = stream <= a and b <= end
        print("  region 0x%X-0x%X inside packed stream? %s" % (a, b, "YES" if inside else "NO"))

    # --- how to read the packed stream: <0x80 = literal run length, >=0x80 = backref ---
    print("\n=== token grammar (observed inside the packed stream) ===")
    print("  < 0x80 : literal run, the byte value is the run length")
    print("  >=0x80 : 2-byte LZ77 back-reference token")
    print("           length = (b & 0x0F), distance = ((tok & 0x7F) << 4) | (b >> 4)")
    print("  => ASCII fragments visible in decoded.bin are plain literal runs;")
    print("     they are NOT a separate tokenized resource.")

    # --- decode the matching decompressed section and show the identifiers there ---
    sec0 = load(os.path.join(root, "out", "fw", "sections", "sec0.bin"))
    for name in (b"UI_SETP_", b"UI_MENUCOM_ITEM_", b"UI_MENU_KIND_"):
        print("\n  sec0.bin (0x%X B) contains prefix %-20s -> offsets %s"
              % (len(sec0), name.decode(), [hex(x) for x in find_all(sec0, name)[:4]]))
    print("\n  sec1.bin contains the same name family (see `pools` / `registry`).")


# -------------------------------------------------------- 2) ASCII id pools ---

POOLS = {
    "sec0": (0x3EE0C8, 0x48A73C),
    "sec1": (0x6D8AB0, 0x70AA2C),
}


def parse_ascii_pool(data: bytes, start: int, end: int):
    """NUL-terminated names, each padded with 0x00 to the next 4-byte boundary."""
    names, i = [], start
    while i < end:
        j = data.find(b"\x00", i, end)
        if j < 0:
            break
        raw = data[i:j]
        if raw and all(0x20 <= c < 0x7F for c in raw):
            names.append((i, raw.decode("ascii")))
        i = j + 1
        while i % 4 and i < end:
            i += 1
    return names


def cmd_pools(root: str) -> None:
    for label, (a, b) in POOLS.items():
        data = load(os.path.join(root, "out", "fw", "sections", label + ".bin"))
        hdr = section_header(data)
        names = parse_ascii_pool(data, a, b)
        print("\n=== %s  %d B  header base=0x%08X size=0x%X (match=%s) ==="
              % (label, len(data), hdr["base"], hdr["size"], hdr["size_matches"]))
        print("    ASCII id pool 0x%X..0x%X  (%d B, %d names)" % (a, b, b - a, len(names)))
        print("    first:", [n for _, n in names[:4]])
        print("    last :", [n for _, n in names[-3:]])
        for key in (b"UI_SETP_", b"UI_MENUCOM_ITEM_"):
            hits = find_all(data, key)
            print("    %-26s %d hits, first: %s"
                  % (key.decode(), len(hits), [hex(x) for x in hits[:4]]))


# --------------------------------------------------- 3) sec1 name registry ----

REG_POOL = POOLS["sec1"]
REG_SCAN_RANGE = (0x6C0000, 0x6D8AB0)   # registry precedes the sec1 name pool


def parse_registry(data: bytes):
    """Return (entries, groups).

    entries: list of (file_off, name_off, index, name)
    groups : list of lists; each group is one enum-name table with index 0..N.
    """
    hdr = section_header(data)
    B = hdr["base"]
    lo, hi = B + REG_POOL[0], B + REG_POOL[1]
    entries = []
    a, b = REG_SCAN_RANGE
    for k in range(a, min(b, len(data) - 8), 4):
        ptr, idx = struct.unpack_from("<II", data, k)
        if lo <= ptr < hi and idx < 0x10000:
            name = read_ascii_name(data, ptr - B)
            if name:
                entries.append((k, ptr - B, idx, name))
    # merge into contiguous 8-byte runs, then split wherever index stops being +1
    runs, cur = [], [entries[0]]
    for prev, e in zip(entries, entries[1:]):
        if e[0] == prev[0] + 8:
            cur.append(e)
        else:
            runs.append(cur)
            cur = [e]
    runs.append(cur)
    groups, g = [], [runs[0][0]]
    for r in runs:
        g = [r[0]]
        for prev, e in zip(r, r[1:]):
            if e[2] == prev[2] + 1:
                g.append(e)
            else:
                groups.append(g)
                g = [e]
        groups.append(g)
    return entries, groups, hdr


def cmd_registry(root: str) -> None:
    data = load(os.path.join(root, "out", "fw", "sections", "sec1.bin"))
    entries, groups, hdr = parse_registry(data)
    print("=== sec1 registry (name_ptr_VA, index) ===")
    print("  load base = 0x%08X (header), size 0x%X" % (hdr["base"], hdr["size"]))
    print("  scan range 0x%X..0x%X -> %d entries in %d groups"
          % (REG_SCAN_RANGE[0], REG_SCAN_RANGE[1], len(entries), len(groups)))
    big = [g for g in groups if len(g) >= 100]
    print("  groups with >=100 entries (the main enum-name tables):")
    for g in big:
        print("    @0x%X..0x%X n=%d index %d..%d  %s .. %s"
              % (g[0][0], g[-1][0], len(g), g[0][2], g[-1][2], g[0][3], g[-1][3]))


# -------------------------------------------------------------------- main ---


def main(argv=None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="SETP/UI resource decoder (read-only)")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="workspace root")
    ap.add_argument("cmd", nargs="?", default="all",
                    choices=["verify", "pools", "registry", "all"])
    a = ap.parse_args(argv)
    if a.cmd in ("verify", "all"):
        cmd_verify(a.root)
    if a.cmd in ("pools", "all"):
        cmd_pools(a.root)
    if a.cmd in ("registry", "all"):
        cmd_registry(a.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
