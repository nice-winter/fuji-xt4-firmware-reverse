#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ui_patch.py -- patch Simplified-Chinese UI strings inside FWUP0024.DAT.

Modes
-----
1) in-place: replacement fits the record slot (distance to next record).
2) long edit (--long): replacement is longer than the slot.  The text pool is
   one contiguous list in the **plaintext** part of the image, so the tail after
   the edited record is simply shifted right by the length delta.  Absolute
   pointers to shifted records are then rewritten as well:
     * pointers in the plaintext image are patched directly;
     * pointers inside the compressed sections are patched through FFLZ
       provenance -- only literal-sourced bytes are touched, the packed stream
       keeps its size, so no re-compression is needed.

Model (see docs/notes/17-long-text-edits.md):
    CN pool = decoded 0x1FB3244 .. first 0xFFFF sentinel, UTF-16LE records,
    NUL-terminated, 2/4-byte aligned.  Free FF padding after the pool up to the
    end of the 0x40000 language block (~118 KB) is the growth budget.

Usage
    python ui_patch.py --list
    python ui_patch.py --demo out/demo.DAT
    python ui_patch.py --patch patches.json out/patched.DAT [--long] [--allow-shift-refs]
        patches.json = [{"offset":"0x1FB3244","old":"自动对焦模式","new":"..."}]
"""
import argparse
import io
import json
import os
import struct
import sys

ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT = os.path.join(ROOT, "FWUP0024.DAT")
TSV = os.path.join(ROOT, "out", "ui_sc_strings.tsv")
HDR = 0x274
MAIN_BODY = 0x2FC0020
CK_OFF = 0x20C

POOL_START = 0x1FB3244
POOL_BLOCK = 0x40000
POOL_GRID_BASE = 0x1E9E000
PLAIN_END = 0x260274          # decoded offset where the first packed section starts

SECTION_PAYLOAD_OFFSETS = {0: 0x260000, 1: 0x5C0000, 2: 0xAE0000, 3: 0x1A00000}

_ALLOWED_RANGES = (
    (0x0020, 0x007E), (0x00A0, 0x00FF), (0x0370, 0x03FF), (0x0400, 0x04FF),
    (0x0590, 0x05FF), (0x0600, 0x06FF), (0x0900, 0x097F), (0x0E00, 0x0E7F),
    (0x2000, 0x206F), (0x2460, 0x24FF), (0x3000, 0x303F), (0x3040, 0x30FF),
    (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF),
    (0xE000, 0xF8FF), (0xFF00, 0xFFEF),
)
_ALLOWED_SINGLE = {0x00B0, 0x00D7, 0x2103}


def allowed_unit(u):
    return u in _ALLOWED_SINGLE or any(a <= u <= b for a, b in _ALLOWED_RANGES)


def load():
    raw = open(DAT, "rb").read()
    logical = bytearray(raw[:HDR]) + bytearray(b ^ 0xFF for b in raw[HDR:])
    return raw, logical


def main_checksum(logical):
    body = logical[HDR:HDR + MAIN_BODY]
    return (0xFFFFFFFF - (sum(body) & 0xFFFFFFFF)) & 0xFFFFFFFF


def save(logical, out_path):
    raw = bytearray(logical[:HDR]) + bytearray(b ^ 0xFF for b in logical[HDR:])
    with open(out_path, "wb") as fh:
        fh.write(raw)
    return raw


def load_slots():
    slots = {}
    if not os.path.exists(TSV):
        return slots
    with io.open(TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 6:
                slots[int(p[0], 16)] = (int(p[2]), p[5])
            elif len(p) >= 5:
                slots[int(p[0], 16)] = (int(p[2]), p[4])
    return slots


def decode_at(logical, off, maxchars=600):
    chars = []
    p = off
    while p + 1 < len(logical):
        u = struct.unpack_from("<H", logical, p)[0]
        if u == 0:
            return "".join(chars), p + 2
        if not allowed_unit(u) or len(chars) > maxchars:
            return None, None
        chars.append(chr(u))
        p += 2
    return None, None


def find_pool_end(logical):
    p = POOL_START + (POOL_START & 1)
    while p + 1 < len(logical):
        if logical[p] == 0xFF and logical[p + 1] == 0xFF:
            return p + 2
        p += 2
    raise SystemExit("error: text-pool sentinel (0xFFFF) not found")


def iter_records(logical):
    end = find_pool_end(logical)
    p = POOL_START
    while p + 1 < end:
        if logical[p] == 0xFF and logical[p + 1] == 0xFF:
            return
        text, nxt = decode_at(logical, p)
        if text is None:
            p += 2
            continue
        yield p, text, nxt
        p = nxt


def block_end_for(off):
    k = (off - POOL_GRID_BASE) // POOL_BLOCK
    return POOL_GRID_BASE + (k + 1) * POOL_BLOCK


# --------------------------------------------------------------- FFLZ decode
def decode_fflz(pay, sec_index):
    """decode one packed section; return (unpacked bytes, provenance list, stream base in 'pay')"""
    sec_off = SECTION_PAYLOAD_OFFSETS[sec_index]
    u, pk, pages, psz, tag = struct.unpack_from("<IIIII", pay, sec_off)
    stream = pay[sec_off + 20: sec_off + 20 + pk]
    out = bytearray()
    src = []
    i = 0
    n = len(stream)
    while i < n:
        tok = stream[i]
        i += 1
        if tok < 0x80:
            for q in range(tok):
                out.append(stream[i + q])
                src.append(("L", i + q))
            i += tok
        else:
            b = stream[i]
            i += 1
            d = ((tok & 0x7F) << 4) | (b >> 4)
            cnt = b & 0x0F
            for _ in range(cnt):
                out.append(out[len(out) - d])
                src.append(("C", len(out) - 1 - d))
    return bytes(out), src, HDR + sec_off + 20


def literal_of(src, pos):
    """follow copy chain to the literal stream offset producing out[pos]"""
    while True:
        kind, ref = src[pos]
        if kind == "L":
            return ref
        pos = ref


# ------------------------------------------------------------------- scanning
def looks_like_ptrs(data, p, pool_end):
    for q in (p - 4, p + 4, p - 8, p + 8):
        if 0 <= q and q + 4 <= len(data):
            nv = struct.unpack_from("<I", data, q)[0]
            if POOL_START <= nv < pool_end:
                return True
    return False


def find_refs(logical, values):
    """absolute u32 pointers to shifted records.

    returns (plaintext_hits[(pos,value)], section_hits[(sec,pos,value)])
    """
    vals = set(values)
    pool_end = find_pool_end(logical)
    plain = []
    for p in range(HDR, PLAIN_END - 4, 4):
        v = struct.unpack_from("<I", logical, p)[0]
        if v in vals and looks_like_ptrs(logical, p, pool_end):
            plain.append((p, v))
    sec_hits = []
    pay = bytes(logical[HDR:])
    for k in sorted(SECTION_PAYLOAD_OFFSETS):
        out, _src, _base = decode_fflz(pay, k)
        for p in range(0, len(out) - 4, 4):
            v = struct.unpack_from("<I", out, p)[0]
            if v in vals and looks_like_ptrs(out, p, pool_end):
                sec_hits.append((k, p, v))
    return plain, sec_hits


def patch_plain_pointers(logical, plain, new_off):
    fixed = 0
    for pos, v in plain:
        nv = new_off(v)
        if nv != v:
            struct.pack_into("<I", logical, pos, nv)
            fixed += 1
    return fixed


def patch_section_pointers(logical, sec_hits, new_off):
    """rewrite section pointers through FFLZ provenance (literals only).

    returns (fixed_count, unresolved_count)
    """
    if not sec_hits:
        return 0, 0
    pay = bytes(logical[HDR:])
    by_sec = {}
    for k, pos, v in sec_hits:
        by_sec.setdefault(k, []).append((pos, v))
    # collect desired byte values per literal; shared literals that would need
    # two different values are left untouched (that pointer stays stale)
    literal_patch = {}
    conflicted = set()
    unresolved_refs = 0
    for k, items in by_sec.items():
        out, src, base = decode_fflz(pay, k)
        for pos, v in items:
            nv = new_off(v)
            desired = {}
            for byte_i in range(4):
                lit = base + literal_of(src, pos + byte_i)
                desired[lit] = (nv >> (8 * byte_i)) & 0xFF
            if any(loc in literal_patch and literal_patch[loc] != val for loc, val in desired.items()):
                conflicted.update(desired)
                unresolved_refs += 1
                continue
            literal_patch.update(desired)
    for loc, val in literal_patch.items():
        if loc in conflicted:
            continue
        logical[loc] = val
    applied = sum(1 for loc in literal_patch if loc not in conflicted)
    return applied, conflicted, unresolved_refs


# --------------------------------------------------------------------- modes
def apply_inplace(logical, edits, slots):
    reports, remaining = [], []
    for off, old, new in edits:
        cur, end = decode_at(logical, off)
        if cur is None:
            reports.append((off, "ERROR: cannot decode record", 0, 0))
            continue
        if old and cur != old:
            reports.append((off, "ERROR: text mismatch: file has %r, patch expects %r" % (cur, old), 0, 0))
            continue
        slot, _orig = slots.get(off, (None, None))
        if slot is None:
            nxt = end
            while nxt % 4:
                nxt += 1
            slot = nxt - off
        enc = new.encode("utf-16le")
        if not enc:
            reports.append((off, "ERROR: empty replacement", 0, 0))
            continue
        if len(enc) + 2 > slot:
            remaining.append((off, old, new))
            continue
        logical[off:off + slot] = enc + b"\x00\x00" + b"\x00" * (slot - len(enc) - 2)
        reports.append((off, "OK in-place: %r -> %r (slot %d B, used %d B)"
                        % (cur, new, slot, len(enc) + 2), len(enc) + 2, slot))
    return reports, remaining


def apply_growth(logical, edits, allow_refs=False):
    reports = []
    if not edits:
        return reports
    blob_end0 = find_pool_end(logical)
    plan = []
    for off, old, new in sorted(edits, key=lambda e: e[0]):
        cur, end = decode_at(logical, off)
        if cur is None:
            return [(off, "ERROR: cannot decode record", 0, 0)]
        if old and cur != old:
            return [(off, "ERROR: text mismatch: file has %r, patch expects %r" % (cur, old), 0, 0)]
        enc = new.encode("utf-16le")
        if not enc:
            return [(off, "ERROR: empty replacement", 0, 0)]
        new_len = len(enc) + 2
        old_len = end - off
        pad = (old_len - new_len) % 4
        new_bytes = enc + b"\x00\x00" + b"\x00" * pad
        plan.append((off, cur, new, new_bytes, end, len(new_bytes) - old_len))
    total = sum(p[5] for p in plan)
    if total <= 0:
        return [(0, "ERROR: growth mode without positive growth", 0, 0)]
    block_end = block_end_for(POOL_START)
    blob_end1 = blob_end0 + total
    if blob_end1 > block_end:
        return [(0, "ERROR: growth exceeds free space: pool 0x%X -> 0x%X > block end 0x%X"
                 % (blob_end0, blob_end1, block_end), 0, 0)]
    for q in range(blob_end0, blob_end1):
        if logical[q] != 0xFF:
            return [(0, "ERROR: growth would overwrite non-FF data at 0x%X" % q, 0, 0)]

    first = plan[0][0]
    edited = {p[0] for p in plan}
    shifted_old = [roff for roff, _t, _e in iter_records(logical)
                   if roff >= first and roff not in edited]

    def new_off(v):
        return v + sum(dl for off, _c, _n, _b, end, dl in plan if end <= v)

    blob_end = blob_end0
    for off, cur, new, new_bytes, end, _delta in reversed(plan):
        # shift the pool tail right *inside* the existing image: the FF padding
        # after the pool absorbs the growth, so the file size stays the same.
        tail = bytes(logical[end:blob_end])
        logical[off:off + len(new_bytes)] = new_bytes
        logical[off + len(new_bytes):off + len(new_bytes) + len(tail)] = tail
        blob_end += len(new_bytes) - (end - off)
        reports.append((off, "OK long: %r -> %r (+%d B, tail shifted)"
                        % (cur, new, len(new_bytes) - (end - off)), 0, 0))

    plain, sec_hits = find_refs(logical, shifted_old)
    if plain:
        n = patch_plain_pointers(logical, plain, new_off)
        reports.append((0, "rewrote %d plaintext pointer(s)" % n, 0, 0))
    if sec_hits:
        applied, conflicts, unresolved = patch_section_pointers(logical, sec_hits, new_off)
        reports.append((0, "rewrote %d section literal byte(s) through FFLZ provenance (%d refs)"
                        % (applied, len(sec_hits)), 0, 0))
        if unresolved:
            msg = ("WARN: %d section pointer(s) share a literal byte with other data and were "
                   "left stale; affected UI items may show old text" % unresolved)
            if not allow_refs:
                return [(0, "ERROR: " + msg + " -- rerun with --allow-shift-refs to force", 0, 0)]
            reports.append((0, msg, 0, 0))
    if not allow_refs:
        # remaining risk: pointers we could not see (computed at run time)
        pass
    reports.append((0, "pool: 0x%X..0x%X (grew by %d B, free %d B left in block)"
                    % (POOL_START, blob_end1, total, block_end - blob_end1), 0, 0))
    return reports


def main():
    ap = argparse.ArgumentParser(description="Patch Simplified-Chinese UI text (in-place or long shift).")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--demo", metavar="OUT")
    ap.add_argument("--patch", nargs=2, metavar=("JSON", "OUT"))
    ap.add_argument("--long", action="store_true", help="allow edits longer than the slot (pool shift)")
    ap.add_argument("--allow-shift-refs", action="store_true",
                    help="kept for compatibility; pointers are rewritten automatically")
    args = ap.parse_args()

    raw, logical = load()
    slots = load_slots()
    print("file          : %s" % DAT)
    print("size          : %d" % len(raw))
    print("main checksum : @0x%X = 0x%08X (recomputed 0x%08X)"
          % (CK_OFF, struct.unpack_from("<I", raw, CK_OFF)[0], main_checksum(logical)))
    print("SC strings    : %d" % len(slots))
    blob_end = find_pool_end(logical)
    print("CN pool       : 0x%X..0x%X (%d B); free FF padding to block end 0x%X: %d B"
          % (POOL_START, blob_end, blob_end - POOL_START,
             block_end_for(POOL_START), block_end_for(POOL_START) - blob_end))

    if args.list:
        for off, (slot, text) in sorted(slots.items())[:20]:
            print("  0x%08X slot=%-4d %s" % (off, slot, text))
        return

    if args.demo:
        entries = [
            {"offset": "0x1FB3244", "old": "自动对焦模式", "new": "自动对焦模式"},
            {"offset": "0x1FB3254", "old": "传感器清洁", "new": "传感器清洁（超长示例：加长的说明文字）"},
            {"offset": "0x1FB32B4", "old": "信息显示", "new": "信息显示改"},
        ]
    elif args.patch:
        entries = json.load(io.open(args.patch[0], encoding="utf-8"))
    else:
        ap.error("need --list / --demo / --patch")

    edits = []
    for e in entries:
        off = int(e["offset"], 16) if isinstance(e["offset"], str) else int(e["offset"])
        edits.append((off, e.get("old", ""), e["new"]))

    before = bytes(logical)
    rep, remaining = apply_inplace(logical, edits, slots)
    for off, msg, used, slot in rep:
        print("  0x%08X %s" % (off, msg))
    if any("ERROR" in r[1] for r in rep):
        print("abort: errors present")
        sys.exit(2)

    if remaining:
        if not args.long:
            print("\n%d edit(s) do not fit their slot; rerun with --long to shift the pool tail." % len(remaining))
            sys.exit(3)
        rep2 = apply_growth(logical, remaining, allow_refs=args.allow_shift_refs)
        for off, msg, used, slot in rep2:
            print("  %s %s" % ("0x%08X" % off if off else "       ", msg))
        if any("ERROR" in r[1] for r in rep2):
            print("abort: errors present")
            sys.exit(2)

    out = args.demo or args.patch[1]
    ck = main_checksum(logical)
    struct.pack_into("<I", logical, CK_OFF, ck)
    save(logical, out)
    print("\nwritten %s  (new main checksum 0x%08X)" % (out, ck))

    chk = open(out, "rb").read()
    log2 = bytearray(chk[:HDR]) + bytearray(b ^ 0xFF for b in chk[HDR:])
    stored = struct.unpack_from("<I", chk, CK_OFF)[0]
    print("verify: stored checksum 0x%08X / recomputed 0x%08X -> %s"
          % (stored, main_checksum(log2), "OK" if stored == main_checksum(log2) else "MISMATCH"))
    print("        file size unchanged: %s" % (len(chk) == len(raw)))
    b_recs = [(o, t) for o, t, _e in iter_records(bytearray(before)) if t]
    a_recs = [(o, t) for o, t, _e in iter_records(log2) if t]
    print("        pool records before/after: %d / %d" % (len(b_recs), len(a_recs)))
    a_text = {t for _o, t in a_recs}
    edited_old = {old for _off, old, _new in edits if old}
    missing = [t for _o, t in b_recs if t not in a_text and t not in edited_old]
    for off, old, new in edits:
        got, _e = decode_at(log2, off)
        where = "at original offset"
        if got != new:
            hit = [o for o, t in a_recs if t == new]
            if hit:
                got = new
                where = "shifted to 0x%X" % hit[0]
        print("       0x%08X %r (%s)" % (off, got, where))
    if missing:
        print("       WARN: %d original strings no longer readable: %r" % (len(missing), missing[:5]))
    # sections must still decode to the same size; only pointer bytes may differ
    pay2 = bytes(log2[HDR:])
    total_sec_diff = 0
    for k in sorted(SECTION_PAYLOAD_OFFSETS):
        o1, _s1, _b1 = decode_fflz(bytes(before[HDR:]), k)
        o2, _s2, _b2 = decode_fflz(pay2, k)
        d = sum(1 for a, b in zip(o1, o2) if a != b)
        total_sec_diff += d
        print("       sec%d decoded %d B, bytes changed: %d" % (k, len(o2), d))
    print("        total section bytes changed: %d" % total_sec_diff)


if __name__ == "__main__":
    main()
