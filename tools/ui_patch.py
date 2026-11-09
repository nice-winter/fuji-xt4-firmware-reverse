#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Patch Simplified-Chinese UI strings inside FWUP0024*.DAT (in-place, no re-pack).

Model of the file (verified, see FIRMWARE-STRUCTURE.md / notes/07-ui-text-sc.md):
    file[0x000 .. 0x274)  plaintext container header
    file[0x274 .. EOF)    firmware payload, bit-inverted (XOR 0xFF)
    payload[0 .. 0x2FC0020)  "main body", protected by checksum @0x20C

The SC UI text lives at decoded (logical) offset 0x1FB3244 .. 0x1FC05F8,
which is inside the main body, so editing a string only requires recomputing
the single main-body checksum @0x20C:
        checksum = 0xFFFFFFFF - (sum of all logical bytes) & 0xFFFFFFFF

Constraint used here: the replacement may not be longer than the original slot
(slot = distance to the next string start; always >= n_bytes + 2, the last two
bytes being the 0x0000 terminator).  Unused slot bytes are filled with 0x0000.
Everything after the edited string keeps its original offset, so no index/table
needs to be updated.

Usage
    python ui_patch.py --list                     # show first extracted strings
    python ui_patch.py --demo out/demo.DAT        # apply a demo patch
    python ui_patch.py --patch patches.json out/patched.DAT
        patches.json = [{"offset":"0x1FB3244","old":"自动对焦模式","new":"自动对焦模式"},
                        ...]
"""
import argparse, io, json, sys, struct, hashlib
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT = os.path.join(ROOT, "FWUP0024.DAT")
TSV = os.path.join(ROOT, "out", "ui_sc_strings.tsv")
HDR = 0x274
MAIN_BODY = 0x2FC0020
CK_OFF = 0x20C


def load():
    raw = open(DAT, "rb").read()
    logical = bytearray(raw[:HDR]) + bytearray(b ^ 0xFF for b in raw[HDR:])
    return raw, logical


def main_checksum(logical):
    body = logical[HDR:HDR + MAIN_BODY]
    return (0xFFFFFFFF - (sum(body) & 0xFFFFFFFF)) & 0xFFFFFFFF


def save(logical, out_path):
    raw = bytearray(logical[:HDR]) + bytearray(b ^ 0xFF for b in logical[HDR:])
    open(out_path, "wb").write(raw)
    return raw


def load_slots():
    """offset -> (slot_bytes, original_text)   supports 5- and 6-column TSVs"""
    slots = {}
    with io.open(TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 6:
                slots[int(p[0], 16)] = (int(p[2]), p[5])
            elif len(p) >= 5:
                slots[int(p[0], 16)] = (int(p[2]), p[4])
    return slots


def apply_patch(logical, entries, slots):
    """entries: list of dict(offset=new...). Returns list of applied reports."""
    reports = []
    for e in entries:
        off = int(e["offset"], 16) if isinstance(e["offset"], str) else int(e["offset"])
        new_text = e["new"]
        old_text = e.get("old", "")
        slot, orig = slots.get(off, (0, None))
        if slot == 0:
            # allow explicit slot in the patch file
            slot = int(e.get("slot", 0))
            orig = e.get("old")
        enc = new_text.encode("utf-16le")
        if not enc:
            reports.append((off, "ERROR: empty replacement", 0, 0))
            continue
        if len(enc) + 2 > slot:
            reports.append((off, "ERROR: %d bytes needed, slot only %d (max %d bytes = %d chars)"
                            % (len(enc) + 2, slot, slot - 2, (slot - 2) // 2), len(enc) + 2, slot))
            continue
        if old_text and orig is not None and orig != old_text:
            reports.append((off, "WARN: current text %r != expected old %r (still patching)" % (orig, old_text), len(enc), slot))
        # write string + terminator, rest of the slot zeroed
        logical[off:off + slot] = enc + b"\x00\x00" + b"\x00" * (slot - len(enc) - 2)
        reports.append((off, "OK: %r -> %r (slot %d B, used %d B)" % (orig, new_text, slot, len(enc) + 2),
                        len(enc) + 2, slot))
    return reports


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--demo", metavar="OUT")
    ap.add_argument("--patch", nargs=2, metavar=("JSON", "OUT"))
    args = ap.parse_args()

    raw, logical = load()
    slots = load_slots()
    print("file          : %s" % DAT)
    print("size          : %d" % len(raw))
    print("main checksum : @0x%X = 0x%08X (recomputed 0x%08X)"
          % (CK_OFF, struct.unpack_from("<I", raw, CK_OFF)[0], main_checksum(logical)))
    print("SC strings    : %d" % len(slots))

    if args.list:
        for i, (off, (slot, text)) in enumerate(sorted(slots.items())[:20]):
            print("  0x%08X slot=%-4d %s" % (off, slot, text))
        return

    if args.demo:
        entries = [
            {"offset": "0x1FB3244", "old": "自动对焦模式", "new": "自动对焦模式"},   # 0 length change
            {"offset": "0x1FB3254", "old": "传感器清洁", "new": "传感器除尘"},       # same length, new words
            {"offset": "0x1FB32B4", "old": "信息显示", "new": "信息显示改"},         # longer, fits in slot
        ]
    elif args.patch:
        entries = json.load(io.open(args.patch[0], encoding="utf-8"))
    else:
        ap.error("need --list / --demo / --patch")

    rep = apply_patch(logical, entries, slots)
    for off, msg, used, slot in rep:
        print("  0x%08X %s" % (off, msg))
    if any("ERROR" in r[1] for r in rep):
        print("abort: errors present")
        sys.exit(2)

    out = args.demo or args.patch[1]
    # fix checksum
    ck = main_checksum(logical)
    struct.pack_into("<I", logical, CK_OFF, ck)
    save(logical, out)
    print("written %s  (new main checksum 0x%08X)" % (out, ck))

    # verify: reload the produced file, invert, re-read patched strings + checksum
    chk = open(out, "rb").read()
    log2 = bytearray(chk[:HDR]) + bytearray(b ^ 0xFF for b in chk[HDR:])
    print("verify: stored checksum 0x%08X / recomputed 0x%08X -> %s"
          % (struct.unpack_from("<I", chk, CK_OFF)[0], main_checksum(log2),
             "OK" if struct.unpack_from("<I", chk, CK_OFF)[0] == main_checksum(log2) else "MISMATCH"))
    for e in entries:
        off = int(e["offset"], 16) if isinstance(e["offset"], str) else int(e["offset"])
        p = off
        chars = []
        while True:
            c = log2[p] | (log2[p + 1] << 8)
            if c == 0:
                break
            chars.append(chr(c))
            p += 2
        print("       0x%08X now reads %r" % (off, "".join(chars)))


if __name__ == "__main__":
    main()
