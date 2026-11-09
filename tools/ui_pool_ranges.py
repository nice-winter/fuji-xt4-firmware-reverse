#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Measure the extent of the JP / SC / TC text pools by character statistics."""
import numpy as np
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(os.path.join(ROOT, "out", "decoded.bin"), "rb").read()


def pool_range(lo, hi, pred, thresh=0.15):
    seg = d[lo:hi - (hi - lo) % 2]
    u = np.frombuffer(seg, dtype="<u2")
    W = 2048
    n = len(u) // W
    hits = np.zeros(n, dtype=np.int32)
    for i in range(n):
        hits[i] = pred(u[i * W:(i + 1) * W])
    dens = hits / W
    good = dens > thresh
    # first/last window with density above threshold
    idx = np.flatnonzero(good)
    if len(idx) == 0:
        return None
    return lo + int(idx[0]) * W * 2, lo + int(idx[-1] + 1) * W * 2


kana = lambda a: int(((a >= 0x3040) & (a <= 0x30FF)).sum())
han = lambda a: int(((a >= 0x4E00) & (a <= 0x9FFF)).sum())
hangul = lambda a: int(((a >= 0xAC00) & (a <= 0xD7AF)).sum())
cyr = lambda a: int(((a >= 0x0400) & (a <= 0x04FF)).sum())
arab = lambda a: int(((a >= 0x0600) & (a <= 0x06FF)).sum())
thai = lambda a: int(((a >= 0x0E00) & (a <= 0x0E7F)).sum())

checks = [
    ("JP (kana)", 0x1E60000, 0x1E90000, kana),
    ("SC (han)", 0x1FA0000, 0x1FD0000, han),
    ("TC (han)", 0x20A0000, 0x20D0000, han),
    ("KO (hangul)", 0x2020000, 0x2050000, hangul),
    ("RU (cyr)", 0x20E0000, 0x2110000, cyr),
    ("TH (thai)", 0x2060000, 0x2090000, thai),
    ("AR (arab)", 0x23E0000, 0x2410000, arab),
]
for name, lo, hi, pred in checks:
    r = pool_range(lo, hi, pred)
    print("%-14s %s" % (name, "0x%08X .. 0x%08X  (%d bytes)" % (r[0], r[1], r[1] - r[0]) if r else "not found"))
