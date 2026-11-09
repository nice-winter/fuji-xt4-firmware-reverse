#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract Simplified-Chinese UI strings from the decoded X-T4 firmware image.

Verified layout (see notes/07-ui-text-sc.md):
  * localisation data lives in the big "FDL Font" bundle at decoded 0x1DA0274;
  * inside it each language occupies one block of NUL-terminated UTF-16LE
    strings (4-byte aligned records, 2-6 bytes of 0x00 separator/padding);
  * Simplified Chinese block: first string "自动对焦模式" @0x1FB3244.
"""
import io
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEC = os.path.join(ROOT, "out", "decoded.bin")
TSV = os.path.join(ROOT, "out", "ui_sc_strings.tsv")
TXT = os.path.join(ROOT, "out", "ui_sc_strings.txt")
REPORT = os.path.join(ROOT, "out", "ui_lang_report.txt")

POOL_START = 0x1FB3244
POOL_END = 0x1FC2000

d = open(DEC, "rb").read()


def read_string(off, limit=400):
    chars = []
    p = off
    while p + 1 < len(d) and len(chars) <= limit:
        c = d[p] | (d[p + 1] << 8)
        if c == 0:
            return "".join(chr(x) for x in chars), (p - off) + 2
        ok = (0x20 <= c <= 0x7E) or (0x4E00 <= c <= 0x9FFF) or (0x3000 <= c <= 0x303F) \
             or (0xFF00 <= c <= 0xFFEF) or (0xE000 <= c <= 0xF8FF) or (0x2000 <= c <= 0x206F) \
             or (0x00A0 <= c <= 0x00FF) or (0x2460 <= c <= 0x24FF) or c in (0x00B0, 0x2103, 0x00D7)
        if not ok:
            return None
        chars.append(c)
        p += 2
    return None


def scan(lo, hi):
    out = []
    off = lo
    while off < hi - 1:
        r = read_string(off)
        if r is not None and r[0]:
            out.append((off, r[0], r[1]))
            off += r[1]
        else:
            off += 2
    return out


def has_cjk(s):
    return any(0x4E00 <= ord(ch) <= 0x9FFF for ch in s)


def pua_only(s):
    return all(0xE000 <= ord(ch) <= 0xF8FF for ch in s)


runs = scan(POOL_START, POOL_END)
rows = []
for i, (off, text, blen) in enumerate(runs):
    nxt = runs[i + 1][0] if i + 1 < len(runs) else min(POOL_END, off + blen)
    rows.append((off, nxt - off, blen, text))

ui = [(o, s, b, t) for (o, s, b, t) in rows if has_cjk(t) and not pua_only(t) and len(t) >= 2]

with io.open(TSV, "w", encoding="utf-8") as f:
    f.write("file_offset\tpayload_offset\tslot_bytes\tn_bytes\ttext\n")
    for off, slot, blen, text in ui:
        f.write("0x%08X\t0x%08X\t%d\t%d\t%s\n" % (off, off - 0x274, slot, blen, text.replace("\t", " ")))

with io.open(TXT, "w", encoding="utf-8") as f:
    f.write("# Simplified-Chinese UI strings — FWUP0024.DAT\n")
    f.write("# decoded_offset  slot_bytes  text\n")
    for off, slot, blen, text in ui:
        f.write("0x%08X  slot=%4d  %s\n" % (off, slot, text))

n_cjk = sum(1 for (o, s, b, t) in ui for ch in t if 0x4E00 <= ord(ch) <= 0x9FFF)
# language block vicinity summary
def blockinfo(name, lo, hi, pred):
    n = m = 0
    for (o, s, b, t) in rows:
        if lo <= o < hi and pred(t):
            n += 1
    return n

with io.open(REPORT, "w", encoding="utf-8") as f:
    f.write("pool scanned          : 0x%08X .. 0x%08X\n" % (POOL_START, POOL_END))
    f.write("total UTF-16 runs     : %d\n" % len(runs))
    f.write("SC strings (CJK>=2ch) : %d\n" % len(ui))
    f.write("CJK chars total       : %d\n" % n_cjk)
    f.write("first SC string       : 0x%08X %s\n" % (ui[0][0], ui[0][3]))
    f.write("last  SC string       : 0x%08X %s\n" % (ui[-1][0], ui[-1][3]))
    f.write("bytes of pool covered : %d\n" % sum(r[1] for r in rows))

print(io.open(REPORT, encoding="utf-8").read())
print("first 10:")
for off, slot, blen, text in ui[:10]:
    print("   0x%08X slot=%-4d %s" % (off, slot, text))
print("last 5:")
for off, slot, blen, text in ui[-5:]:
    print("   0x%08X slot=%-4d %s" % (off, slot, text))
