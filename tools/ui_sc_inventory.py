#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Full inventory of the Simplified-Chinese UI string pool (all string types)."""
import io, collections
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEC = os.path.join(ROOT, "out", "decoded.bin")
OUT = os.path.join(ROOT, "out", "ui_sc_pool_all.tsv")
d = open(DEC, "rb").read()
START, END = 0x1FB3244, 0x1FC0600


def read_string(off):
    chars = []
    p = off
    while p + 1 < len(d):
        c = d[p] | (d[p + 1] << 8)
        if c == 0:
            return "".join(chr(x) for x in chars), (p - off) + 2
        ok = (0x20 <= c <= 0x7E) or (0x4E00 <= c <= 0x9FFF) or (0x3000 <= c <= 0x303F) \
             or (0xFF00 <= c <= 0xFFEF) or (0xE000 <= c <= 0xF8FF) or (0x2000 <= c <= 0x206F) \
             or (0x00A0 <= c <= 0x00FF) or (0x2460 <= c <= 0x24FF) or c in (0x00B0, 0x2103, 0x00D7)
        if not ok or len(chars) > 400:
            return None
        chars.append(c)
        p += 2
    return None


runs = []
off = START
while off < END - 1:
    r = read_string(off)
    if r is not None and r[0]:
        runs.append((off, r[0], r[1]))
        off += r[1]
    else:
        off += 2

rows = []
for i, (off, text, blen) in enumerate(runs):
    nxt = runs[i + 1][0] if i + 1 < len(runs) else off + blen
    slot = nxt - off
    cjk = sum(1 for ch in text if 0x4E00 <= ord(ch) <= 0x9FFF)
    pua = sum(1 for ch in text if 0xE000 <= ord(ch) <= 0xF8FF)
    ascii_n = sum(1 for ch in text if 0x20 <= ord(ch) <= 0x7E)
    if cjk >= 1 and len(text) >= 2:
        kind = "text-CJK"
    elif pua and cjk == 0 and len(text) == 1:
        kind = "glyph-ref"
    elif ascii_n == len(text):
        kind = "ascii"
    else:
        kind = "symbol"
    rows.append((off, slot, blen, kind, text))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("file_offset\tpayload_offset\tslot_bytes\tn_bytes\tkind\ttext\n")
    for off, slot, blen, kind, text in rows:
        f.write("0x%08X\t0x%08X\t%d\t%d\t%s\t%s\n" % (off, off - 0x274, slot, blen, kind, text.replace("\t", " ")))

c = collections.Counter(r[3] for r in rows)
print("SC pool 0x%08X..0x%08X" % (START, END))
print("total records:", len(rows), dict(c))
print("pool bytes   :", END - START)
print("ASCII-only strings:", sum(1 for r in rows if r[3] == "ascii"))
