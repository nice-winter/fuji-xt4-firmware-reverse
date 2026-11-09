#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trace FFLZ provenance: which compressed-stream bytes produce each sec0 byte.

Used to find in-place patchable sites in the compressed stream.
"""
import io, struct, os
import os

ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
raw = open(os.path.join(ROOT, "FWUP0024.DAT"), "rb").read()
HDR = 0x274
logical = raw[:HDR] + bytes(b ^ 0xFF for b in raw[HDR:])
pay = logical[HDR:]

# locate sec0 section
sec_off = 0x260000
u, pk, pages, psz, tag = struct.unpack_from("<IIIII", pay, sec_off)
p = pay[sec_off + 20: sec_off + 20 + pk]
print("sec0: unpacked=%d packed=%d pages=%d psz=0x%X" % (u, pk, pages, psz))

out = bytearray()
src = []   # for each output byte: ('L', stream_index) or ('C', source_output_index)
i = 0
while i < len(p):
    tok = p[i]; i += 1
    if tok < 0x80:
        for k in range(tok):
            out.append(p[i + k])
            src.append(("L", i + k))
        i += tok
    else:
        b = p[i]; i += 1
        d = ((tok & 0x7F) << 4) | (b >> 4)
        n = b & 0x0F
        for _ in range(n):
            out.append(out[len(out) - d])
            src.append(("C", len(out) - 1 - d))
print("decoded %d bytes (expect %d)" % (len(out), u))

# stream base in logical image
stream_base = HDR + sec_off + 20

def report(out_off, n, label):
    print("\n### %s  sec0 0x%08X ###" % (label, out_off))
    for k in range(n):
        o = out_off + k
        kind, ref = src[o]
        if kind == "L":
            print("  out+%d 0x%02X  literal  stream_off=0x%08X  LOGICAL=0x%08X  FILE=0x%08X  raw_byte=%02X"
                  % (k, out[o], ref, stream_base + ref, stream_base + ref, raw[stream_base + ref]))
        else:
            print("  out+%d 0x%02X  copy     from_out=0x%08X (0x%02X)"
                  % (k, out[o], ref, out[ref]))

report(0x4F4110, 8, "parent table entry value=7 / ptr")
report(0x4F43A0, 8, "sub value-table entry value=10 (P2 target)")
report(0x4F4114, 4, "ptr field")
report(0x4F4658, 12, "movie table entry")

