#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fdl_bundle.py -- read-only parser for the Fujifilm "FDL Font" resource bundle.

Target: FWUP0024.DAT (X-T4, os=6, v2.12-derived) logical image
        out/fw/decoded.bin   (official reference: out/official/decoded.bin)

What this tool knows (all verified from the two logical images):

  * The file contains several "FDL Font\\0" bundles.  Bundle #0 starts at
    decoded 0x1DA0274 and is 0x980000 bytes long (next magic at 0x2720274).
  * Bundle #0 header:  16-byte magic, 12 zero bytes, 28 bytes of small
    descriptor records, then a named "info" record at +0x40:
        "info" + u32 payload_offset + u32 payload_size   (payload at +0xA31C2,
        size 0x7C in the modified build; +0xA2FE5 in the official build).
  * Bundle #0 body: 0xFDD8C bytes of shared font/glyph/label data, followed by
    35 language blocks of 0x40000 bytes each, on the decoded grid
        0x1E9E000 + k*0x40000   (k = 0..34, last one truncated at 0x2720274).
  * Inside the language blocks three record kinds occur (all little-endian):
        str        : NUL-terminated UTF-16LE text.  Text may begin with a PUA
                     code point (U+F000..U+F8FF) that acts as an embedded icon /
                     substring reference.  '\\uf3ee' -> NOSTALGIC icon,
                     '\\uf445' -> REALA icon in the modified build.
        12B entry  : {u32 ref, u16 w, u16 h, u32 flags}   (w=h=100 typical;
                     flags observed 0 and 2, 2 only in RTL locales)
        8B message : {u32 text_offset, u16 style, u16 count}  (style 0x0190,
                     0x0208, 0x0244, 0x021C, 0x0154, 0x0168 seen; count 1..3)
                     text_offset is a 24-bit-ish offset; in the official build
                     B+off decodes to real localized strings for many records,
                     so the offset is *pool relative*, not language-local.
  * The mod ("二改") wrote, in *every* language block, a new block of data at
    +0x274..+0x4xx (official bytes there are 0xFF):
        - localized NOSTALGIC Neg. description (3 lines)
        - 3 x 12B entries
        - localized REALA ACE description (3 lines)
        - 3 x 12B entries
        - 4 x (label string, 12B entry) pairs; labels are
              "\uf445", "\uf3ee", "\uf445REALA ACE", "\uf3eeNOSTALGIC Neg."
    plus, at +0x2174 / +0x21B4, the shared texts "NOSTALGIC Neg." / "REALA ACE".

This tool never writes to the .DAT; output goes to out/fdl_bundle_report.txt.

Usage:
    python tools/fdl_bundle.py report
    python tools/fdl_bundle.py header
    python tools/fdl_bundle.py blocks
    python tools/fdl_bundle.py labels  --block 0
    python tools/fdl_bundle.py entries --block 0
    python tools/fdl_bundle.py film
    python tools/fdl_bundle.py patchmap --block 0
"""
import argparse
import io
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUR_BUILD = os.path.join(ROOT, "out", "fw", "decoded.bin")
OFFICIAL = os.path.join(ROOT, "out", "official", "decoded.bin")
REPORT = os.path.join(ROOT, "out", "fdl_bundle_report.txt")

MAGIC = b"FDL Font\x00"
BUNDLE0 = 0x1DA0274
BUNDLE0_END = 0x2720274
BLOCK0 = 0x1E9E000
BLOCK_STRIDE = 0x40000
NBLOCKS = 35
HEAD_END = BLOCK0                       # shared font/glyph/label area of bundle #0

# style values found in 8-byte message records (observed, not exhaustive)
MSG_STYLES = {0x0050, 0x012C, 0x0154, 0x0168, 0x0190, 0x01B8,
              0x0208, 0x021C, 0x0244}


def load(path=CUR_BUILD):
    with open(path, "rb") as f:
        return f.read()


# ----------------------------------------------------------------------------
# bundle / block layout
# ----------------------------------------------------------------------------
def find_bundles(buf):
    """Return [(offset, size)] for every FDL Font magic, sizes = distance to next
    magic or to end of image for the last one."""
    offs = []
    i = 0
    while True:
        j = buf.find(MAGIC, i)
        if j < 0:
            break
        offs.append(j)
        i = j + 1
    out = []
    for n, off in enumerate(offs):
        nxt = offs[n + 1] if n + 1 < len(offs) else len(buf)
        out.append((off, nxt - off))
    return out


def bundle0_size(buf):
    for off, size in find_bundles(buf):
        if off == BUNDLE0:
            return size
    raise SystemExit("FDL bundle not found at 0x%X" % BUNDLE0)


def block_bases(buf):
    end = BUNDLE0 + bundle0_size(buf)
    out = []
    for k in range(NBLOCKS):
        lo = BLOCK0 + k * BLOCK_STRIDE
        if lo >= end:
            break
        out.append((k, lo, min(BLOCK_STRIDE, end - lo)))
    return out


def parse_header(buf, base=BUNDLE0):
    h = {
        "magic": buf[base:base + 16],
        "desc28": buf[base + 0x1C:base + 0x1C + 0x24],
        "info": None,
    }
    if buf[base + 0x40:base + 0x44] == b"info":
        off, size = struct.unpack_from("<II", buf, base + 0x44)
        h["info"] = (off, size, base + off)
    return h


# ----------------------------------------------------------------------------
# tokenizers
# ----------------------------------------------------------------------------
def read_ustr(buf, off, maxlen=400):
    """NUL-terminated UTF-16LE string at absolute decoded offset `off`."""
    out = []
    p = off
    while p + 1 < len(buf) and len(out) < maxlen:
        c = buf[p] | (buf[p + 1] << 8)
        if c == 0:
            return "".join(out)
        if c < 0x20 and c not in (0x09, 0x0A):
            return None
        out.append(chr(c))
        p += 2
    return None


def read_rec12(buf, p):
    """12-byte layout entry {u32 ref, u16 w, u16 h, u32 flags}."""
    if p + 12 > len(buf):
        return None
    ref, w, h, flags = struct.unpack_from("<IHHI", buf, p)
    if not (0x780000 <= ref <= 0x980000):
        return None
    if not (1 <= w <= 600 and 1 <= h <= 600):
        return None
    if flags > 8:
        return None
    if w not in (32, 48, 64, 72, 96, 100, 120, 128, 200, 256) and \
       h not in (32, 48, 64, 72, 96, 100, 120, 128, 200, 256):
        return None
    if ref % 4:
        return None
    return (ref, w, h, flags)


def read_msg8(buf, p):
    """8-byte message/menu record {u32 text_off, u16 style, u16 count}."""
    if p + 8 > len(buf):
        return None
    off, style, count = struct.unpack_from("<IHH", buf, p)
    if not (0x800000 <= off <= 0x980000):
        return None
    if style not in MSG_STYLES:
        return None
    if not (1 <= count <= 64):
        return None
    if off % 2:
        return None
    return (off, style, count)


def tokenize(buf, lo, hi, want=("rec12", "msg8", "str")):
    """Greedy tokenizer over [lo,hi): tries 12B entry, 8B message record, UTF-16
    string, else advances 2 bytes.  Returns list of dicts."""
    toks = []
    p = lo
    while p < hi:
        if "rec12" in want:
            r = read_rec12(buf, p)
            if r:
                toks.append({"kind": "rec12", "off": p, "v": r})
                p += 12
                continue
        if "msg8" in want:
            m = read_msg8(buf, p)
            if m:
                toks.append({"kind": "msg8", "off": p, "v": m})
                p += 8
                continue
        if "str" in want:
            s = read_ustr(buf, p, 400)
            if s is not None and len(s) > 0:
                toks.append({"kind": "str", "off": p, "v": s})
                p += (len(s) + 1) * 2
                continue
        p += 2
    return toks


def find_diff_runs(a, o, lo, hi, gap=1):
    runs = []
    p = lo
    while p < hi:
        if a[p] != o[p]:
            s = p
            while p < hi and a[p] != o[p]:
                p += 1
            runs.append((s, p))
        else:
            p += 1
    merged = []
    for s, e in runs:
        if merged and s - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


# ----------------------------------------------------------------------------
# domain helpers
# ----------------------------------------------------------------------------
def pua_label_strings(buf, lo, hi):
    """Strings whose first code unit is a PUA icon (F000..F8FF)."""
    out = []
    p = lo
    while p < hi - 2:
        s = read_ustr(buf, p, 200)
        if s and len(s) > 1 and 0xF000 <= ord(s[0]) <= 0xF8FF:
            out.append((p, s))
            p += (len(s) + 1) * 2
        else:
            p += 2
    return out


def film_filter_labels(buf, base, blen):
    """Composite B&W / ACROS filter labels inside one language block."""
    return [(p, s) for p, s in pua_label_strings(buf, base, base + blen)
            if ("FILTER" in s or "MONOCHROME" in s or "ACROS" in s)]


def mod_area(buf, base):
    """Tokenize the mod-inserted +0x274..+0x4A0 group of one language block."""
    lo = base + 0x274
    hi = min(base + 0x4A0, len(buf))
    return tokenize(buf, lo, hi)


# ----------------------------------------------------------------------------
# commands
# ----------------------------------------------------------------------------
def cmd_header(buf, w):
    w("FDL bundles found:")
    for off, size in find_bundles(buf):
        w("  0x%08X  size=0x%X" % (off, size))
    h = parse_header(buf)
    w("")
    w("bundle #0 @0x%08X: magic=%r" % (BUNDLE0, h["magic"]))
    w("  descriptor bytes +0x1C..+0x40: %s" % h["desc28"].hex(" "))
    if h["info"]:
        off, size, addr = h["info"]
        w("  info record: name='info' off=0x%X size=0x%X -> decoded 0x%X"
          % (off, size, addr))
        body = buf[addr:addr + size]
        w("  info payload hex: %s" % body.hex(" "))
        w("  info payload utf16: %r" % body.decode("utf-16le", "replace"))


def cmd_blocks(buf, w):
    w("bundle0 size = 0x%X; shared head = 0x%X..0x%X" %
      (bundle0_size(buf), BUNDLE0, HEAD_END))
    w("language blocks (decoded grid 0x%X + k*0x%X):" % (BLOCK0, BLOCK_STRIDE))
    for k, lo, blen in block_bases(buf):
        w("  blk%-2d  0x%08X .. 0x%08X  len=0x%X  bytes=0x%08X"
          % (k, lo, lo + blen, blen, BUNDLE0 and lo))


def cmd_labels(buf, w, block):
    k, base, blen = block_bases(buf)[block]
    w("PUA composite labels in block %d (0x%08X..0x%08X):"
      % (k, base, base + blen))
    for p, s in pua_label_strings(buf, base, base + blen):
        w("  0x%08X  %r" % (p, s))


def cmd_entries(buf, w, block):
    k, base, blen = block_bases(buf)[block]
    for lo, hi, tag in ((base, base + min(blen, 0x600), "+0x000..+0x600"),
                        (base + 0x2900, base + min(blen, 0x2A00), "+0x2900..+0x2A00"),
                        (base + 0x1B400, base + min(blen, 0x1B700), "+0x1B400..+0x1B700")):
        if lo >= base + blen:
            continue
        hi = min(hi, base + blen)
        w("")
        w("block %d %s" % (k, tag))
        for t in tokenize(buf, lo, hi):
            if t["kind"] == "rec12":
                w("  0x%08X REC12 ref=0x%06X w=%d h=%d flags=%d"
                  % (t["off"], *t["v"]))
            elif t["kind"] == "msg8":
                off, style, count = t["v"]
                w("  0x%08X MSG8  off=0x%06X style=0x%04X count=%d"
                  % (t["off"], off, style, count))
            else:
                w("  0x%08X STR   %r" % (t["off"], t["v"][:90]))


def cmd_film(buf, w):
    """Report the film-simulation related FDL structures in every block."""
    w("=== per-block film-simulation label pool (B&W / ACROS filter labels) ===")
    for k, base, blen in block_bases(buf):
        labs = film_filter_labels(buf, base, blen)
        if not labs:
            continue
        w("blk%-2d 0x%08X  (%d labels)" % (k, base, len(labs)))
        for p, s in labs[:14]:
            w("     0x%08X  %r" % (p, s))
    w("")
    w("=== per-block mod new area (+0x274..+0x4A0) ===")
    for k, base, blen in block_bases(buf):
        if blen < 0x4A0:
            continue
        w("blk%-2d base=0x%08X" % (k, base))
        for t in mod_area(buf, base):
            if t["kind"] == "rec12":
                w("   +0x%05X REC12 ref=0x%06X w=%d h=%d flags=%d"
                  % (t["off"] - base, *t["v"]))
            elif t["kind"] == "str":
                w("   +0x%05X STR   %r" % (t["off"] - base, t["v"][:90]))
    w("")
    w("=== +0x2174 (NOSTALGIC) / +0x21B4 (REALA) texts ===")
    for k, base, blen in block_bases(buf):
        if blen < 0x21C8:
            continue
        n = read_ustr(buf, base + 0x2174, 40)
        r = read_ustr(buf, base + 0x21B4, 40)
        w("blk%-2d 0x%08X  +0x2174=%r  +0x21B4=%r" % (k, base, n, r))


def cmd_patchmap(buf, w, block):
    o = load(OFFICIAL)
    k, base, blen = block_bases(buf)[block]
    runs = find_diff_runs(buf, o, base, base + blen)
    w("official vs modified-build diff, block %d (0x%08X, len=0x%X): %d runs"
      % (k, base, blen, len(runs)))
    for s, e in runs:
        w("  +0x%05X..+0x%05X len=%-4d aff=%r" %
          (s - base, e - base, e - s, read_ustr(buf, s, 24)))


def cmd_report(buf):
    with io.open(REPORT, "w", encoding="utf-8") as f:
        def w(s=""):
            f.write(s + "\n")
        cmd_header(buf, w)
        w()
        cmd_blocks(buf, w)
        w()
        cmd_film(buf, w)
        w()
        cmd_patchmap(buf, w, 0)
        w()
        cmd_patchmap(buf, w, 1)
        w()
        cmd_labels(buf, w, 0)
        w()
        cmd_entries(buf, w, 0)
    print("written " + REPORT)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["report", "header", "blocks", "labels",
                                    "entries", "film", "patchmap"])
    ap.add_argument("--block", type=int, default=0)
    ap.add_argument("--official", action="store_true",
                    help="read out/official/decoded.bin instead of the modified build")
    ns = ap.parse_args(argv)
    buf = load(OFFICIAL if ns.official else CUR_BUILD)
    if ns.cmd == "report":
        cmd_report(buf)
        return
    w = lambda s="": sys.stdout.write(s + "\n")
    if ns.cmd == "header":
        cmd_header(buf, w)
    elif ns.cmd == "blocks":
        cmd_blocks(buf, w)
    elif ns.cmd == "labels":
        cmd_labels(buf, w, ns.block)
    elif ns.cmd == "entries":
        cmd_entries(buf, w, ns.block)
    elif ns.cmd == "film":
        cmd_film(buf, w)
    elif ns.cmd == "patchmap":
        cmd_patchmap(buf, w, ns.block)


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    main()
