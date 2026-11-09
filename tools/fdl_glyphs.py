#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fdl_glyphs.py -- read-only extractor for Fujifilm "FDL Font" glyph outlines (X-T4 firmware).

Target : FWUP0024.DAT  (os=6, v2.12-derived, "二改")
Image  : out/fw/decoded.bin   (logical image = file[0:0x274] + ~file[0x274:])
Ref    : out/official/decoded.bin (official build, same layout, used for cross-checks)

WHAT IS IMPLEMENTED (all discovered/verified in this session; see
notes/16-fdl-glyph-extract.md for the evidence chain):

  FDL bundle #0  (decoded 0x1DA0274, length 0x980000)
    +0x00        "FDL Font\\0"
    +0x1C..0x40  28-byte descriptor: {u32 X}{u16}{[u16 pad, u32 off, u16 id] x3}
                 + {u16 0x0100, u32 info_end, u16 0}.  For bundle #0 the three
                 records all point at the glyph *blob* start 0x3DCED and the last
                 one at the info-payload end (0xA31C2+0x7C = 0xA323E).
    +0x40        "info" + {u32 payload_off, u32 size}
    +0x384D4     glyph offset table: 5638 x 4 bytes {u8 flag, u24 end_offset}
                 (monotone non-decreasing; equals the corpus of glyph sizes)
    +0x3DCED     glyph data blob (414,933 bytes) -- glyph i = [off[i-1], off[i])
    +0xA31C2     info payload (font name "ICON_NEW-UCS-CNS", base charset
                 "Standard\\Unicode\\UCS-CNS", version "0100", build 202212201341)
    +0xA323E     u16 metrics table (advance widths etc.)
    +0xC0000     8-byte label records {u16 style, u16 1, u32 text_off}
    +0xE9xxx..   shared UTF-16 text pools
    0x1E9E000    35 language blocks (0x40000 each)

  CHARACTER MAP: **glyph id = Unicode code point - 0xE120** for the PUA icon
  range.  The table has exactly 5638 entries and the PUA code points actually
  referenced by the simplified-Chinese UI pool are U+E120..U+F725 (max-min =
  5637 = n_entries-1); every one of the 394 used code points maps onto a
  data-bearing glyph.  (Validated: 394/394.)

  GLYPH RECORD (all little-endian, refs relative to blob start):
      simple : u16 0x00FA, u16 n, byte path[n]
      complex: u16 0x0000, u16 advance, u16 n1, u16 0x00FA, u16 n2, byte path[n2]
               (n1 == n2 + 4)
      empty  : u16 0x0000, u16 advance, u16 0, u16 0        (6 bytes)

  PATH BYTES: variable-length opcode stream.  Opcodes and payload forms:
      0xB5 / 0x92 / 0x96 : [op][arg][x][y]                (4 bytes, 1 point)
      0x9A 0x9B 0x9E 0x9F: [op][arg][count][ (x,y)*count ] (3+2*count)
      0x35               : [op][arg][u16][u16]            (6 bytes, rare)
      0x03 / 0x07 / 0x70 : [op][arg]                      (2 bytes)
  With this grammar 1161/1173 simple paths parse exactly (the 12 misses use the
  rare 0x35 form).  Contours start at 0xB5 00 and are terminated by 0x03, 0x07
  or 0x70.

  NOTE (uncertain): the *painting* semantics of the args (whether 0x92/0x96
  points are on-curve or control points, fill rule, point order inside a
  contour) are only 【推测】.  Both a filled and a stroked rendering are produced
  so the web UI can pick whichever looks right.

This tool only ever opens the two decoded.bin images read-only.  All output goes
to out/glyphs/ .

Usage:
    python tools/fdl_glyphs.py report
    python tools/fdl_glyphs.py export [--size 256] [--official]
"""
import argparse
import io
import json
import os
import struct
import sys
from collections import Counter, OrderedDict

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUR_BUILD = os.path.join(ROOT, "out", "fw", "decoded.bin")
OFFICIAL = os.path.join(ROOT, "out", "official", "decoded.bin")
OUTDIR = os.path.join(ROOT, "out", "glyphs")

MAGIC = b"FDL Font\x00"
BUNDLE0 = 0x1DA0274
BLOCK0 = 0x1E9E000
INFO_PAYLOAD = 0xA31C2          # current build
INFO_SIZE = 0x7C
GLYPH_BLOB = 0x3DCED            # == descriptor record offset
CMAP_BASE = 0xE120              # glyph id = codepoint - CMAP_BASE
NPUA = 394

OPCODE_FORM = {
    0xB5: "pt", 0x92: "pt", 0x96: "pt",
    0x9A: "cnt", 0x9B: "cnt", 0x9E: "cnt", 0x9F: "cnt",
    0x03: "cmd", 0x07: "cmd", 0x70: "cmd",
    0x35: "x6",
}


# ---------------------------------------------------------------- image / table
def load(path=CUR_BUILD):
    with open(path, "rb") as f:
        return f.read()


def find_bundle(buf):
    off = buf.find(MAGIC)
    if off < 0:
        raise SystemExit("FDL Font bundle not found")
    return off


def parse_header(buf, base=BUNDLE0):
    h = {"base": base, "magic": buf[base:base + 16]}
    if buf[base + 0x40:base + 0x44] == b"info":
        off, size = struct.unpack_from("<II", buf, base + 0x44)
        h["info_off"], h["info_size"] = off, size
    # 36-byte descriptor at +0x1C:
    #   {u32 X}{u16 pad} + {u32 off, u16 id, u16 pad} x3 + {u32 off, u16 id}
    d = buf[base + 0x1C:base + 0x40]
    recs = []
    for k in range(3):
        off, ident, pad = struct.unpack_from("<IHH", d, 6 + 8 * k)
        recs.append((off, ident, pad))
    off, ident = struct.unpack_from("<IH", d, 30)
    recs.append((off, ident, None))
    h["desc"] = d
    h["desc_recs"] = recs
    return h


def glyph_table(buf, base=BUNDLE0):
    """Return (table_start, blob_start, [(flag, end_off)], blob_size)."""
    # table starts at the first non-zero byte after the header/info area
    p = base + 0x80
    while p < base + 0x40000 and buf[p] == 0:
        p += 1
    tab = p - base
    # blob starts at the descriptor's offset (0x3DCED) and its size must equal the
    # last table entry
    h = parse_header(buf, base)
    blob = h["desc_recs"][0][0]
    n = (blob - 1 - tab) // 4
    ents = []
    for i in range(n):
        q = base + tab + 4 * i
        fl = buf[q]
        end = buf[q + 1] | (buf[q + 2] << 8) | (buf[q + 3] << 16)
        ents.append((fl, end))
    blob_size = ents[-1][1]
    # sanity: blob + blob_size must land exactly on the info payload
    assert base + blob + blob_size == base + h["info_off"], \
        "glyph blob does not end at the info payload (0x%X vs 0x%X)" % (
            base + blob + blob_size, base + h["info_off"])
    return tab, blob, ents, blob_size


# ---------------------------------------------------------------- glyph records
def glyph_record(buf, base, blob, ents, gid):
    a = ents[gid - 1][1] if gid > 0 else 0
    b = ents[gid][1]
    return buf[base + blob + a: base + blob + b]


def parse_chunks(rec, pos):
    """Glyph payload is a sequence of  u16 0x00FA / u16 n / n bytes  chunks."""
    out = bytearray()
    while pos < len(rec):
        if pos + 4 > len(rec):
            return None
        t, ln = struct.unpack_from("<HH", rec, pos)
        if t != 0x00FA or pos + 4 + ln > len(rec):
            return None
        out += rec[pos + 4:pos + 4 + ln]
        pos += 4 + ln
    return bytes(out)


def split_record(rec):
    """Return (kind, advance, path_bytes, flags).

    simple : u16 0x00FA, u16 n, data[n]            (chunks only)
    complex: u16 flags, u16 advance, u16 n_total, <chunks, n_total bytes>
    empty  : u16 flags, u16 advance, 0, 0         (6 bytes, no outline)
    """
    if not rec:
        return "empty", None, b"", None
    t, ln = struct.unpack_from("<HH", rec, 0)
    if t == 0x00FA:
        path = parse_chunks(rec, 0)
        if path is not None:
            return "simple", None, path, None
        return "unknown", None, b"", None
    if len(rec) == 6 and rec[4:6] == b"\x00\x00":
        fl, adv = struct.unpack_from("<HH", rec, 0)
        return "empty", adv, b"", fl
    if len(rec) >= 10:
        fl, adv, n1 = struct.unpack_from("<HHH", rec, 0)
        if n1 == len(rec) - 6:
            path = parse_chunks(rec, 6)
            if path is not None:
                return "complex", adv, path, fl
    return "unknown", None, b"", None


def parse_path(path):
    """Decode the path byte stream into instructions.

    Returns list of (op, arg, [points], offset) or None on parse failure.
    """
    i = 0
    ins = []
    n = len(path)
    while i < n:
        op = path[i]
        form = OPCODE_FORM.get(op)
        if form is None:
            return None
        if form == "cmd":
            if i + 1 >= n:
                return None
            ins.append((op, path[i + 1], [], i))
            i += 2
        elif form == "pt":
            if i + 3 >= n:
                return None
            ins.append((op, path[i + 1], [(path[i + 2], path[i + 3])], i))
            i += 4
        elif form == "x6":
            if i + 5 >= n:
                return None
            ins.append((op, path[i + 1], [], i))
            i += 6
        else:
            if i + 2 >= n:
                return None
            cnt = path[i + 2]
            if i + 3 + 2 * cnt > n:
                return None
            pts = [(path[i + 3 + 2 * k], path[i + 4 + 2 * k]) for k in range(cnt)]
            ins.append((op, path[i + 1], pts, i))
            i += 3 + 2 * cnt
    return ins


def build_contours(path):
    """Group path points into contours.  0xB5 00 starts a contour; 0x03/0x07/0x70
    terminate it.  Returns (contours, ok)."""
    ins = parse_path(path)
    if ins is None:
        return [], False
    contours = []
    cur = []
    for op, arg, pts, _ in ins:
        if op == 0xB5 and arg == 0x00:
            if len(cur) > 1:
                contours.append(cur)
            cur = list(pts)
        elif op in (0x03, 0x07, 0x70):
            if len(cur) > 1:
                contours.append(cur)
            cur = []
        elif op == 0x35:
            pass
        else:
            cur.extend(pts)
    if len(cur) > 1:
        contours.append(cur)
    return contours, True


# ---------------------------------------------------------------- rendering
def render(contours, mode="fill", canvas=256, flipy=False):
    im = Image.new("L", (canvas, canvas), 255)
    dr = ImageDraw.Draw(im)
    cts = contours
    if flipy:
        cts = [[(x, canvas - 1 - y) for x, y in c] for c in cts]
    if mode == "fill":
        for c in cts:
            if len(c) >= 3:
                dr.polygon(c, fill=0)
    else:  # stroke
        for c in cts:
            if len(c) >= 2:
                dr.line(c + [c[0]], fill=0, width=max(1, canvas // 128), joint="curve")
    return im


def content_bbox(contours, canvas=256, pad=1):
    xs = [p[0] for c in contours for p in c]
    ys = [p[1] for c in contours for p in c]
    if not xs:
        return None
    x0, x1 = max(0, min(xs) - pad), min(canvas - 1, max(xs) + pad)
    y0, y1 = max(0, min(ys) - pad), min(canvas - 1, max(ys) + pad)
    if x1 <= x0: x1 = min(canvas - 1, x0 + 1)
    if y1 <= y0: y1 = min(canvas - 1, y0 + 1)
    return x0, y0, x1, y1


# ---------------------------------------------------------------- PUA code points
def read_pua_codepoints():
    """All PUA code points referenced by the simplified-Chinese UI pools."""
    cps = set()
    for fn in ("ui_sc_pool_all.tsv", "ui_sc_strings.txt"):
        p = os.path.join(ROOT, "out", fn)
        if not os.path.exists(p):
            continue
        txt = io.open(p, encoding="utf-8", errors="replace").read()
        for ch in txt:
            o = ord(ch)
            if 0xE000 <= o <= 0xF8FF:
                cps.add(o)
    return sorted(cps)


# ---------------------------------------------------------------- commands
def cmd_report(buf, w):
    base = find_bundle(buf)
    h = parse_header(buf, base)
    tab, blob, ents, blob_size = glyph_table(buf, base)
    w("FDL bundle #0      : decoded 0x%08X" % base)
    w("descriptor +0x1C   : %s" % h["desc"].hex(" "))
    w("  desc records     : %r" % (h["desc_recs"],))
    w("info record        : +0x%X off=0x%X size=0x%X -> decoded 0x%X"
      % (0x40, h["info_off"], h["info_size"], base + h["info_off"]))
    w("info payload       : %r" % buf[base + h["info_off"]:
                                     base + h["info_off"] + h["info_size"]].decode("utf-16le", "replace"))
    w("glyph offset table : +0x%05X .. +0x%05X   %d entries (4B each)"
      % (tab, tab + 4 * len(ents), len(ents)))
    w("glyph blob         : +0x%05X size=%d (0x%X), ends at info payload"
      % (blob, blob_size, blob_size))
    w("flag byte          : %r" % dict(sorted(Counter(f for f, _ in ents).items())))
    w("")
    kinds = Counter()
    good = bad = 0
    advs = Counter()
    for gid in range(len(ents)):
        rec = glyph_record(buf, base, blob, ents, gid)
        kind, adv, path, flg = split_record(rec)
        kinds[kind] += 1
        if adv is not None:
            advs[adv] += 1
        if kind in ("simple", "complex"):
            cts, ok = build_contours(path)
            if ok and cts:
                good += 1
            else:
                bad += 1
    w("glyph record kinds : %r" % dict(kinds))
    w("advance widths     : %r" % dict(sorted(advs.items())))
    w("outline decode     : ok=%d fail/empty=%d" % (good, bad))
    cps = read_pua_codepoints()
    w("")
    w("PUA code points used by SC pools : %d  (U+%04X..U+%04X)"
      % (len(cps), cps[0], cps[-1]) if cps else "no PUA found")
    if cps:
        ids = [c - CMAP_BASE for c in cps]
        data = [i for i in range(len(ents))
                if i == 0 or ents[i][1] > ents[i - 1][1]]
        dset = set(data)
        ok = sum(1 for i in ids if i in dset)
        w("cmap hypothesis  id = cp - 0x%04X : ids %d..%d, data-bearing %d/%d"
          % (CMAP_BASE, ids[0], ids[-1], ok, len(ids)))
        w("n_entries-1      : %d  (cp span = %d)" % (len(ents) - 1, cps[-1] - cps[0]))


def cmd_export(buf, args):
    base = find_bundle(buf)
    h = parse_header(buf, base)
    tab, blob, ents, blob_size = glyph_table(buf, base)
    canvas = args.size
    cps = read_pua_codepoints()
    if not cps:
        raise SystemExit("no PUA code points found in out/ui_sc_pool_all.tsv")
    os.makedirs(OUTDIR, exist_ok=True)

    # collect glyph data
    records = []
    for cp in cps:
        gid = cp - CMAP_BASE
        rec = glyph_record(buf, base, blob, ents, gid) if 0 <= gid < len(ents) else b""
        kind, adv, path, flg = split_record(rec)
        cts, ok = build_contours(path) if path else ([], True)
        bb = content_bbox(cts, canvas=256)
        records.append({
            "cp": cp, "gid": gid, "kind": kind, "advance": adv,
            "ncontours": len(cts), "npoints": sum(len(c) for c in cts),
            "bbox256": bb, "ok": ok and bool(cts),
        })

    # per-glyph PNG + packed sprite for both painting modes
    for mode in ("fill", "stroke"):
        cells = []
        for r in records:
            cp, gid = r["cp"], r["gid"]
            path = split_record(glyph_record(buf, base, blob, ents, gid))[2] if 0 <= gid < len(ents) else b""
            cts, _ = build_contours(path) if path else ([], True)
            im = render(cts, mode, canvas=256)
            bb = r["bbox256"]
            fn = os.path.join(OUTDIR, "glyph_U%04X_%s.png" % (cp, mode))
            if bb:
                crop = im.crop((bb[0], bb[1], bb[2] + 1, bb[3] + 1))
            else:
                crop = Image.new("L", (1, 1), 255)
            crop.save(fn)
            cells.append((cp, crop, bb))
        # pack
        if cells:
            pad = 2
            cell_w = max(c.width for _, c, _ in cells) + pad * 2
            cell_h = max(c.height for _, c, _ in cells) + pad * 2
            cols = 20
            rows = (len(cells) + cols - 1) // cols
            sheet = Image.new("L", (cols * cell_w, rows * cell_h), 0)
            meta = OrderedDict()
            for n, (cp, crop, bb) in enumerate(cells):
                cx = (n % cols) * cell_w + pad
                cy = (n // cols) * cell_h + pad
                sheet.paste(crop, (cx, cy))
                meta["0x%04x" % cp] = {
                    "x": cx, "y": cy, "w": crop.width, "h": crop.height,
                    "cell_w": cell_w, "cell_h": cell_h,
                    "ox": (bb[0] if bb else 0), "oy": (bb[1] if bb else 0),
                }
            sheet.save(os.path.join(OUTDIR, "sprite_%s.png" % mode))
            with io.open(os.path.join(OUTDIR, "sprite_%s.json" % mode), "w",
                         encoding="utf-8") as f:
                json.dump(meta, f, indent=1)

    # summary tsv + json
    with io.open(os.path.join(OUTDIR, "glyph_index.tsv"), "w", encoding="utf-8") as f:
        f.write("codepoint\tglyph_id\tkind\tadvance\tncontours\tnpoints\tbbox_x0\tbbox_y0\tbbox_x1\tbbox_y1\tdecoded\n")
        for r in records:
            bb = r["bbox256"] or (0, 0, 0, 0)
            f.write("U+%04X\t%d\t%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%s\n" % (
                r["cp"], r["gid"], r["kind"], r["advance"], r["ncontours"],
                r["npoints"], bb[0], bb[1], bb[2], bb[3], "yes" if r["ok"] else "no"))
    with io.open(os.path.join(OUTDIR, "glyph_map.json"), "w", encoding="utf-8") as f:
        json.dump({("0x%04x" % r["cp"]): {
            "gid": r["gid"], "kind": r["kind"], "advance": r["advance"],
            "ncontours": r["ncontours"], "npoints": r["npoints"],
            "bbox": r["bbox256"], "decoded": r["ok"]} for r in records},
            f, indent=1)
    ok_n = sum(1 for r in records if r["ok"])
    print("exported %d/%d glyphs to %s (fill+stroke)" % (ok_n, len(records), OUTDIR))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="export", choices=["report", "export"])
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--official", action="store_true")
    a = ap.parse_args(argv)
    buf = load(OFFICIAL if a.official else CUR_BUILD)
    if a.cmd == "report":
        os.makedirs(OUTDIR, exist_ok=True)
        lines = []
        cmd_report(buf, lambda s="": lines.append(s))
        p = os.path.join(OUTDIR, "fdl_glyph_report.txt")
        with io.open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        sys.stdout.write("\n".join(l for l in lines if l.isascii()) + "\n")
        print("written " + p)
    else:
        cmd_export(buf, a)


if __name__ == "__main__":
    main()
