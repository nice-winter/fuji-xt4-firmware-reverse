#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch: remove the +R/+Ye/+G right column for the REALA ACE slot.

The left-column table (SETP 1070 @sec0 0x4F40C0) has 12 entries {u32 value, u32 sub-SETP ptr}.
Only value=7 (the slot that now displays REALA ACE) and value=18 (ACROS) carry a ptr.
We clear BOTH copies of the value=7 ptr (still + movie tables) in place.

Compressed-stream literal sites (verified by tools/fflz_trace.py):
  FILE 0x4BB45C..0x4BB45F : raw 17 AA AE FE (logical E8 55 51 01 = 0x015155E8) -> FF FF FF FF
      -> clears still table  sec0 0x4F4114 .. 0x4F4117
      -> also clears 3 high bytes of movie table ptr (sec0 0x4F465D..0x4F465F)
  FILE 0x4BB606           : raw 37 (logical C8)  -> FF
      -> clears movie table ptr low byte (sec0 0x4F465C)
  => both still and movie table entries value=7 now have ptr = 0

Main checksum recomputed.  Verification: decompress sec0 from the patched DAT and make sure
ONLY sec0 0x4F4114..0x4F4117 and 0x4F465C..0x4F465F changed; sec1/2/3 byte-identical.
"""
import hashlib
import os
import struct

ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "FWUP0024.DAT")
DST = os.path.join(ROOT, "out", "patch_no_reala_rightcol.DAT")
SEC_DIR = os.path.join(ROOT, "out", "fw", "sections")
HDR = 0x274
MAIN = 0x2FC0020

PATCHES = [
    (0x4BB45C, bytes.fromhex("E8555101"), b"\x00\x00\x00\x00", "still+movie ptr high bytes"),
    (0x4BB606, bytes.fromhex("C8"), b"\x00", "movie ptr low byte"),
]


def decode_sections(pay):
    out = []
    off = 0
    while off + 20 < len(pay):
        u, pk, pages, psz, tag = struct.unpack_from("<IIIII", pay, off)
        if tag in (1, 2, 3, 4, 5) and psz in (0x1000, 0x2000, 0x4000, 0x8000) \
                and u > 0 and pk > 0 and pages == (pk + psz - 1) // psz:
            data = bytearray()
            p = pay[off + 20: off + 20 + pk]
            i = 0
            while i < len(p):
                t = p[i]; i += 1
                if t < 0x80:
                    data += p[i:i + t]; i += t
                else:
                    b = p[i]; i += 1
                    d = ((t & 0x7F) << 4) | (b >> 4)
                    for _ in range(b & 0x0F):
                        data.append(data[-d])
            out.append(bytes(data))
            off += 20 + pk
            if off & 1:
                off += 1
        else:
            off += 2
            if off & 1:
                off += 1
    return out


def ck(seg):
    return (0xFFFFFFFF - (sum(seg) & 0xFFFFFFFF)) & 0xFFFFFFFF


raw = bytearray(open(SRC, "rb").read())
logical = bytearray(raw[:HDR]) + bytearray(b ^ 0xFF for b in raw[HDR:])

print("-- pre-patch sanity --")
for off, old, new, what in PATCHES:
    cur = bytes(logical[off:off + len(old)])
    print("  0x%08X %-28s cur=%s expect=%s %s"
          % (off, what, cur.hex().upper(), old.hex().upper(), "OK" if cur == old else "MISMATCH"))
    assert cur == old, "unexpected bytes at 0x%08X" % off

for off, old, new, what in PATCHES:
    logical[off:off + len(old)] = new

ckv = ck(logical[HDR:HDR + MAIN])
struct.pack_into("<I", logical, 0x20C, ckv)
print("\nnew main checksum: 0x%08X" % ckv)

out = bytearray(logical[:HDR]) + bytearray(b ^ 0xFF for b in logical[HDR:])
open(DST, "wb").write(out)
print("written", DST, len(out))

print("\n-- verification --")
chk = open(DST, "rb").read()
log2 = bytearray(chk[:HDR]) + bytearray(b ^ 0xFF for b in chk[HDR:])
print("size unchanged:", len(chk) == len(raw))
diffs = [i for i in range(len(raw)) if raw[i] != chk[i]]
print("DAT bytes changed:", len(diffs), [hex(x) for x in diffs])

secs = decode_sections(bytes(log2[HDR:]))
print("sections: %d sizes=%s" % (len(secs), [len(s) for s in secs]))
for k in range(4):
    orig = open(os.path.join(SEC_DIR, "sec%d.bin" % k), "rb").read()
    nd = [i for i in range(min(len(secs[k]), len(orig))) if secs[k][i] != orig[i]]
    same = hashlib.sha256(secs[k]).hexdigest() == hashlib.sha256(orig).hexdigest()
    print("  sec%d size %d/%d  differing=%d %s  sha_same=%s"
          % (k, len(secs[k]), len(orig), len(nd), [hex(x) for x in nd[:8]], same))

s0 = secs[0]
print("still table entry value=7 : value=%d ptr=0x%08X"
      % (struct.unpack_from("<I", s0, 0x4F4110)[0], struct.unpack_from("<I", s0, 0x4F4114)[0]))
print("movie table entry value=7 : value=%d ptr=0x%08X"
      % (struct.unpack_from("<I", s0, 0x4F4658)[0], struct.unpack_from("<I", s0, 0x4F465C)[0]))

stored = struct.unpack_from("<I", chk, 0x20C)[0]
print("main checksum: stored=0x%08X recomputed=0x%08X -> %s"
      % (stored, ck(log2[HDR:HDR + MAIN]), "OK" if stored == ck(log2[HDR:HDR + MAIN]) else "MISMATCH"))
pay2 = bytes(log2[HDR:])
for name, oo, so, co in [("R0", 0x248, 0x250, 0x210), ("R1", 0x254, 0x258, 0x214),
                         ("R4", 0x220, 0x224, 0x21C), ("R5", 0x22C, 0x230, 0x228),
                         ("R2", 0x25C, 0x260, 0x264), ("R3", 0x268, 0x26C, 0x270)]:
    off = struct.unpack_from("<I", chk, oo)[0]
    ln = struct.unpack_from("<I", chk, so)[0]
    fld = struct.unpack_from("<I", chk, co)[0]
    val = ck(chk[HDR + off:HDR + off + ln]) if name in ("R2", "R3") else ck(pay2[off:off + ln])
    print("%s: %s" % (name, "OK" if val == fld else "BAD 0x%08X/0x%08X" % (fld, val)))
