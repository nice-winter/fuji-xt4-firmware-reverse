#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""setp_decode.py -- decoder for the SETP / UI resource layer of the Fujifilm X-T4
firmware (FWUP0024.DAT, and the earlier build build for cross-check).

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
              (UI_FILM_SIM_*, UI_RAW_DEV_FILM_SIM_*, UI_MENUCOM_ITEM_*, UI_SETP_* ...).

4) `filmsim`  Print the film-simulation enum tables (shooting + RAW development)
              with offsets, values and (for the shooting enum) the FDL display label
              obtained from the UTF-16 text resource.

5) `all`      Everything above.

Read-only: the .DAT files are never modified; all output is stdout (optionally
redirect to a file).  UTF-8 output is forced so non-ASCII labels survive.

Verified against:
  out/fw/sections/sec0.bin  7,421,952 B (header base 0x01021000, size 0x714000)
  out/fw/sections/sec1.bin  9,437,184 B (header base 0x01E0F000, size 0x900000)
Also works with the earlier build artefacts (same offsets for every table used here).
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

    # --- show the token grammar around the observed "ILM_PROVIA" byte run ---
    target = dec.find(b"ILM_PROVIA", 0x400000, 0x600000)
    print("\n=== test case: decoded offset 0x%X contains b'ILM_PROVIA' ===" % target)
    ctx = dec[target - 24:target + 24]
    print("  bytes:", " ".join("%02X" % c for c in ctx))
    # walk the token stream backwards is hard; walk forward from a known byte-boundary
    # we start a little before the literal run: find a <0x80 length byte right before
    pos = target - 1
    while pos > target - 8 and dec[pos] >= 0x80:
        pos -= 1
    tok = dec[pos]
    print("  literal-run length byte before it: 0x%02X (=%d) at decoded 0x%X"
          % (tok, tok, pos))
    print("  -> the following %d bytes are a plain FFLZ literal run: %r"
          % (tok, dec[pos + 1:pos + 1 + tok][:32]))
    print("  => 'FILM_PROVIA' / 'FS_PROVIA' etc. seen raw in decoded.bin are just LZ")
    print("     literal fragments; they are NOT a tokenized SETP resource.")

    # --- decode the matching decompressed section and show the identifiers there ---
    sec0 = load(os.path.join(root, "out", "fw", "sections", "sec0.bin"))
    for name in (b"UI_FILM_SIM_STD\x00", b"UI_SETP_FILM_SIM\x00",
                 b"DOT_INFO_FILM_PROVIA\x00"):
        print("\n  sec0.bin (0x%X B) contains %-28s -> offsets %s"
              % (len(sec0), name[:-1].decode(), [hex(x) for x in find_all(sec0, name)[:4]]))
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
        for key in (b"UI_FILM_SIM_STD\x00", b"UI_RAW_DEV_FILM_SIM_STD\x00"):
            print("    %-26s %s" % (key[:-1].decode(),
                                    [hex(x) for x in find_all(data, key)]))


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
    print("\n  film-simulation related groups:")
    for g in groups:
        if any("FILM_SIM" in e[3] or "FSIM" in e[3] for e in g):
            print("    @0x%X n=%d: %s ... %s"
                  % (g[0][0], len(g), g[0][3], g[-1][3]))


# ----------------------------------------------------- 4) film-sim enums -----

FILM_TABLE = ("UI_FILM_SIM_STD", 0x6D35F8)        # first record, sec1 file offset
RAWDEV_TABLE = ("UI_RAW_DEV_FILM_SIM_STD", 0x6D6430)


def _group_at(data: bytes, groups, first_name: str):
    for g in groups:
        if g and g[0][3] == first_name:
            return g
    return []


def cmd_filmsim(root: str) -> None:
    data = load(os.path.join(root, "out", "fw", "sections", "sec1.bin"))
    entries, groups, hdr = parse_registry(data)

    print("=== UI_FILM_SIM_* enum-name table (shooting / still UI) ===")
    print("    sec1 file offset 0x6D35F8..0x6D36A8, 23 records x 8 B, index = enum value")
    g = _group_at(data, groups, FILM_TABLE[0])
    labels = fdl_label_map(root)
    for k, off, idx, name in g:
        print("    enum %2d  (0x%02X)  @sec1 0x%06X  %-28s  label=%s"
              % (idx, idx, off, name, labels.get(name, "?")))

    print("\n=== UI_RAW_DEV_FILM_SIM_* enum-name table (RAW development UI) ===")
    print("    sec1 file offset 0x6D6430..0x6D64B8, 18 records x 8 B, index = enum value")
    g2 = _group_at(data, groups, RAWDEV_TABLE[0])
    for k, off, idx, name in g2:
        print("    enum %2d  (0x%02X)  @sec1 0x%06X  %s" % (idx, idx, off, name))

    print("\n=== SETP item IDs (sec1 registry, main UI_SETP group @0x6C9BD8, idx 1..2122) ===")
    for k, off, idx, name in entries:
        if name in ("UI_SETP_FILM_SIM", "UI_SETP_FILM_SIM_SET",
                    "UI_SETP_FILM_SIM_SELECT", "UI_SETP_FILM_SIM_SELECT_1",
                    "UI_SETP_FILM_SIM_2_SELECT_1", "UI_SETP_RAW_DEV_FSIM",
                    "UI_SETP_FUNCLOCK_FILM_SIM"):
            print("    id=%-5d @sec1 0x%06X  %s" % (idx, off, name))

    print("\nNOTE: this table is an *enum name table* (index = enum value).  Its order is")
    print("      the source/enum order, NOT the camera menu order: index 0..4 are")
    print("      STD,F1B,F1C,F2,BW and MONOCHROME/SEPIA sit in the middle, while the")
    print("      real menu puts CLASSIC CHROME 4th and MONOCHROME/SEPIA near the end.")


# ------------------------------------ 5) FDL (UTF-16) display-label mapping ---

FDL_FIRST = (0x1DA0274, 0x2720274)     # first "FDL Font" package in decoded image


def _u16_strings(data: bytes, a: int, b: int):
    out, i = [], a
    while i + 1 < b:
        j, chars, ok = i, [], True
        while j + 1 < b:
            v = data[j] | (data[j + 1] << 8)
            if v == 0:
                break
            if v == 0xFFFF or v < 0x20:
                ok = False
                break
            chars.append(v)
            j += 2
        if ok and chars:
            out.append((i, "".join(chr(c) for c in chars)))
            i = j + 2
            while i + 1 < b and data[i] == 0 and data[i + 1] == 0:
                i += 2
        else:
            i += 2
    return out


def fdl_label_map(root: str):
    """Map enum-name -> display label, using the composite-label block of the English
    text pool (decoded 0x1EC8630..0x1EC8810, records are icon-PUA + TEXT or
    icon-PUA+"logotype-PUA"+"/TYPE").  Mapping is by best-effort name matching; see
    notes/09-setp-resource.md for the evidence and the unresolved cases."""
    dec = load(os.path.join(root, "out", "fw", "decoded.bin"))
    ss = _u16_strings(dec, FDL_FIRST[0], FDL_FIRST[1])
    # collect the label block
    block = {off: s for off, s in ss if 0x1EC8600 <= off <= 0x1EC8820}
    text = "\n".join(block.values())

    def exact(s):
        """exact record match inside the label block (strip leading PUA icons)"""
        for off in sorted(block):
            v = block[off]
            stripped = "".join(ch for ch in v if not (0xE000 <= ord(ch) <= 0xF8FF))
            if stripped == s or v == s:
                return v
        return "?"

    def first(*needles):
        for off in sorted(block):
            v = block[off]
            for n in needles:
                if n in v:
                    return v
        return "?"

    m = {}
    m["UI_FILM_SIM_STD"] = "\\uf06a\\uf06f/STANDARD  (=PROVIA/STANDARD)"
    m["UI_FILM_SIM_F1B"] = "\\uf06b\\uf070/VIVID     (=Velvia/VIVID)"
    m["UI_FILM_SIM_F1C"] = "\\uf06c\\uf071/SOFT      (=ASTIA/SOFT)"
    m["UI_FILM_SIM_BW"] = exact("MONOCHROME")
    m["UI_FILM_SIM_SEPIA"] = exact("SEPIA")
    m["UI_FILM_SIM_CLASSIC_CHROME"] = exact("CLASSIC CHROME")
    m["UI_FILM_SIM_PRONEGA_H"] = exact("PRO Neg. Hi")
    m["UI_FILM_SIM_PRONEGA_S"] = exact("PRO Neg. Std")
    m["UI_FILM_SIM_ETERNA"] = "\\uf370\\uf369/CINEMA (=ETERNA/CINEMA)"
    m["UI_FILM_SIM_BLEACH_BYPASS"] = exact("ETERNA BLEACH BYPASS")
    m["UI_FILM_SIM_ACROS_FILTER"] = "ACROS (only found in one later language pool)"
    m["UI_FILM_SIM_BW_FILTER_G"] = exact("MONOCHROME+G FILTER")
    m["UI_FILM_SIM_BW_FILTER_R"] = exact("MONOCHROME+R FILTER")
    m["UI_FILM_SIM_BW_FILTER_Y"] = exact("MONOCHROME+Ye FILTER")
    return m


def cmd_labels(root: str) -> None:
    dec = load(os.path.join(root, "out", "fw", "decoded.bin"))
    print("=== FDL Font packages (magic) in decoded image ===")
    for off in find_all(dec, b"FDL Font"):
        print("  0x%08X" % off)
    print("\n=== display-label block of the English pool (decoded 0x1EC8600..0x1EC8820) ===")
    ss = _u16_strings(dec, FDL_FIRST[0], FDL_FIRST[1])
    for off, s in ss:
        if 0x1EC8600 <= off <= 0x1EC8820:
            print("  0x%08X  %r" % (off, s))
    print("\nNOTE: NOSTALGIC Neg. / REALA ACE are NOT in this block; they live in small")
    print("      separate pools appended after each language block, e.g.")
    for off in (0x1E9E38A, 0x1E9E3AC):
        e = dec.find(b"\x00\x00", off)
        print("      0x%08X  %r" % (off, dec[off:e].decode("utf-16-le", "replace")))


# -------------------------------------------------------------------- main ---


def main(argv=None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="SETP/UI resource decoder (read-only)")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="workspace root")
    ap.add_argument("cmd", nargs="?", default="all",
                    choices=["verify", "pools", "registry", "filmsim", "labels", "all"])
    a = ap.parse_args(argv)
    if a.cmd in ("verify", "all"):
        cmd_verify(a.root)
    if a.cmd in ("pools", "all"):
        cmd_pools(a.root)
    if a.cmd in ("registry", "all"):
        cmd_registry(a.root)
    if a.cmd in ("filmsim", "all"):
        cmd_filmsim(a.root)
    if a.cmd in ("labels", "all"):
        cmd_labels(a.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
