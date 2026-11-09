#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independently verify the .DAT produced by the JS tool (out/patched_1108_js.DAT)."""
import io, struct
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(ROOT, "FWUP0024_affix_1108.DAT")
PATCH = os.path.join(ROOT, "out", "patched_1108_js.DAT")
HDR = 0x274

a = open(ORIG, "rb").read()
b = open(PATCH, "rb").read()
out = io.open(os.path.join(ROOT, "out", "js_patch_verify.txt"), "w", encoding="utf-8")
def w(s=""): out.write(s + "\n"); print(s)

w("orig size %d / patched size %d  -> %s" % (len(a), len(b), "same" if len(a) == len(b) else "DIFFERENT"))
ck_o = struct.unpack_from("<I", a, 0x20C)[0]
ck_n = struct.unpack_from("<I", b, 0x20C)[0]
pay = bytes(x ^ 0xFF for x in b[HDR:])
w("checksum field: orig 0x%08X  patched 0x%08X" % (ck_o, ck_n))
body = pay[:0x2FC0020]
calc = (0xFFFFFFFF - (sum(body) & 0xFFFFFFFF)) & 0xFFFFFFFF
w("recomputed main-body checksum = 0x%08X  -> %s" % (calc, "OK" if calc == ck_n else "MISMATCH"))

# region checksums R0..R5
regs = [("R0", 0x248, 0x250, 0x210), ("R1", 0x254, 0x258, 0x214), ("R4", 0x220, 0x224, 0x21C),
        ("R5", 0x22C, 0x230, 0x228), ("R2", 0x25C, 0x260, 0x264), ("R3", 0x268, 0x26C, 0x270)]
def ck(seg): return (0xFFFFFFFF - (sum(seg) & 0xFFFFFFFF)) & 0xFFFFFFFF
allok = True
for name, oo, so, co in regs:
    off = struct.unpack_from("<I", b, oo)[0]
    ln = struct.unpack_from("<I", b, so)[0]
    field = struct.unpack_from("<I", b, co)[0]
    val = ck(b[HDR + off: HDR + off + ln]) if name in ("R2", "R3") else ck(pay[off:off + ln])
    ok = (val == field)
    allok &= ok
    w("  %s field 0x%08X calc 0x%08X %s" % (name, field, val, "OK" if ok else "BAD"))
w("all region checksums: %s" % ("OK" if allok else "PROBLEM"))

# diff summary
diffs = []
inrun = False
for i in range(len(a)):
    if a[i] != b[i]:
        if not inrun:
            diffs.append([i, 0]); inrun = True
        diffs[-1][1] += 1
    else:
        inrun = False
w("changed bytes: %d in %d runs" % (sum(d[1] for d in diffs), len(diffs)))
for s, l in diffs:
    w("   0x%08X len=%d" % (s, l))

# read edited strings back (UTF-16LE NUL terminated)
def read_str(buf, off):
    chars = []; p = off
    while p + 1 < len(buf):
        c = buf[p] | (buf[p + 1] << 8)
        if c == 0:
            return "".join(chr(x) for x in chars)
        chars.append(c); p += 2
    return None
w("edited strings in patched file:")
for off in (0x1FB3244, 0x1FB3254, 0x1FB32B4, 0x1FB332C):
    w("   0x%08X  %r" % (off, read_str(pay, off - HDR)))

# untouched pool bytes outside the edited slots?
pool_lo, pool_hi = 0x1FB3244 - HDR, 0x1FC05F8 - HDR
same = sum(1 for i in range(pool_lo, pool_hi) if pay[i] == (a[HDR + i] ^ 0xFF))
w("pool bytes identical to original: %d / %d" % (same, pool_hi - pool_lo))
out.close()
