#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fsim_ui_scan.py -- read-only scan: locate the film-simulation selection UI data
in the Fujifilm X-T4 modded firmware FWUP0024.DAT and compute the patch
that removes the B&W-filter ("right column") sub-options for the slot that now
displays REALA ACE.

What it does (all read-only; nothing is modified):
  1. section  : read the 4 FFLZ section headers from the logical image and print the
                load base / size metadata stored at the head of each decompressed
                section (secN.bin) -- this is what makes VA references decodable.
  2. setp     : parse the 32-byte "SETP item definition" records in sec0 that belong
                to the film-simulation setting family (UI_SETP_FILM_SIM = 1070,
                _ACROS = 1071, _MONO = 1072, _MOVIE = 1073, _ACROS_MOVIE = 1074,
                _MONO_MOVIE = 1075), decoding {u16 a; u16 b; u32 id; u32 n; u32 0;
                u32 p1; u32 p_values; u32 p_messages; u32 c}.
  3. options  : decode the option lists (8-byte entries {u32 value; u32 sub_record},
                terminated by 0x7FFFFFFE) that p_values points at, and the value
                lists of the nested sub-records.  This is the "left column = film
                simulation list, right column = B&W filter variants" structure.
  4. patch    : for the entries that carry a sub-record pointer (the two families
                ACROS and MONOCHROME/BW), verify that the 4-byte pointer field is
                stored inside a *literal run* of the FFLZ token stream of sec0
                (=> the patch can be applied without recompressing anything), and
                print the exact logical-image offsets + before/after bytes.
  5. datpatch : (optional, --dat) write out/patch_nofilter_1108.DAT with the two
                pointer fields zeroed and the main container checksum recomputed.

Usage (read-only by default):
    python tools/fsim_ui_scan.py            # everything, no files written
    python tools/fsim_ui_scan.py --dat      # also write out/patch_nofilter_1108.DAT
    python tools/fsim_ui_scan.py --root <workspace>

Evidence levels used in notes/13-fsim-ui-code.md:
    [proven]  byte-verified in this script
    [strong]  strong structural inference
    [guess]   unverified
"""
from __future__ import annotations

import argparse
import io
import os
import struct
import sys


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HDR = 0x274          # plaintext DAT header length == payload (XOR 0xFF) start
MAIN_CK_OFF = 0x20C
MAIN_LEN = 0x2FC0020
DEFAULT_SRC = "FWUP0024.DAT"

# FFLZ section headers in the logical image (file offsets of the 20-byte headers)
SEC_HDRS = (0x260274, 0x5C0274, 0xAE0274, 0x1A00274)

TERM = 0x7FFFFFFE


def load(p):
    with open(p, "rb") as f:
        return f.read()


def section_meta(root):
    """Return [(idx, logical_hdr_off, unpacked, packed, pages, page_size, tag,
    base, size, hdr_word3)] using both the FFLZ header (in the logical image) and
    the metadata block at the head of each decompressed secN.bin."""
    dec = load(os.path.join(root, "out", "fw", "decoded.bin"))
    out = []
    for i, hoff in enumerate(SEC_HDRS):
        u, pk, pages, psz, tag = struct.unpack_from("<5I", dec, hoff)
        sp = os.path.join(root, "out", "fw", "sections", "sec%d.bin" % i)
        data = load(sp)
        w0, base, size, w3 = struct.unpack_from("<4I", data, 0)
        out.append(dict(idx=i, hdr_off=hoff, unpacked=u, packed=pk, pages=pages,
                        page_size=psz, tag=tag, base=base, size=size, w3=w3,
                        path=sp, data=data))
    return out


# ---------------------------------------------------------------- SETP records

def parse_setp_records(s0, base0):
    """Collect the 32-byte records immediately preceding/anchor-adjacent to the
    id fields we care about.  A record is recognized by its shape:
        +0x00 u16 a   (+0x02 u16 b)     small tag
        +0x04 u32 id                    SETP id (1070..1075 family)
        +0x08 u32 n                     small count
        +0x0c u32 0
        +0x10 u32 p1   (VA)             parent / layout record
        +0x14 u32 p2   (VA)             option value list
        +0x18 u32 p3   (VA)             per-option message records
        +0x1c u32 c                     small checksum/len
    Scan the whole section for the (id, plausible pointers) pattern.
    """
    lo, hi = base0, base0 + len(s0)
    recs = []
    for off in range(0, len(s0) - 32, 4):
        a, b, sid, n = struct.unpack_from("<HHII", s0, off)
        z, p1, p2, p3 = struct.unpack_from("<IIII", s0, off + 12)
        if not (1070 <= sid <= 1076):
            continue
        if z != 0 or not (0 < n < 0x40):
            continue
        if not all(lo <= p < hi for p in (p1, p2, p3)):
            continue
        recs.append(dict(off=off, va=base0 + off, tag=(a, b), id=sid, n=n,
                         p1=p1, p2=p2, p3=p3, c=struct.unpack_from("<I", s0, off + 28)[0]))
    return recs


def read_u32_list(s0, base0, va):
    """Read the {u32 value; u32 sub_record} list terminated by 0x7FFFFFFE.
    Returns (entries, terminator_off) or (None, None)."""
    off = va - base0
    if not (0 <= off < len(s0) - 8):
        return None, None
    ents = []
    for k in range(0, 0x1000, 8):
        v, sub = struct.unpack_from("<II", s0, off + k)
        if v == TERM:
            return ents, off + k
        ents.append((off + k, v, sub))
    return None, None


def read_u32_pairs(s0, base0, va):
    """The nested variant lists use the same 8-byte {value; 0} layout."""
    off = va - base0
    out = []
    for k in range(0, 0x400, 8):
        v, x = struct.unpack_from("<II", s0, off + k)
        if v == TERM:
            return out, off + k
        out.append(v)
    return None, None


# ------------------------------------------------------- FFLZ literal map

def fflz_literal_map(dec, sec_hdr_off, target_unpacked):
    """Walk the FFLZ token stream of one section and report, for the unpacked
    offset `target_unpacked`, whether it falls inside a literal run, and where the
    corresponding bytes live in the logical image.
    Returns dict(kind, dec_off, run_len, run_start_unpacked)."""
    unpacked, packed, pages, psz, tag = struct.unpack_from("<5I", dec, sec_hdr_off)
    stream = sec_hdr_off + 20
    i = out = 0
    while i < packed and out <= target_unpacked + 1:
        tok = dec[stream + i]
        i += 1
        if tok < 0x80:
            if out <= target_unpacked < out + tok:
                return dict(kind="literal", dec_off=stream + i + (target_unpacked - out),
                            run_len=tok, run_start_unpacked=out)
            out += tok
            i += tok
        else:
            b = dec[stream + i]
            i += 1
            ln = b & 0x0F
            if out <= target_unpacked < out + ln:
                return dict(kind="backref", dec_off=None, run_len=ln,
                            run_start_unpacked=out)
            out += ln
    return dict(kind="not-found", dec_off=None, run_len=0, run_start_unpacked=None)


# ------------------------------------------------------------------ reporting

def main(argv=None):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="film-sim UI data scan (read-only)")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--dat", action="store_true",
                    help="also write out/patch_nofilter_1108.DAT")
    a = ap.parse_args(argv)

    secs = section_meta(a.root)
    print("=== 1. sections [proven] ===")
    for s in secs:
        print("  sec%d: FFLZ hdr @0x%X unpacked=%#x packed=%#x pages=%d psz=%#x tag=%d"
              % (s["idx"], s["hdr_off"], s["unpacked"], s["packed"], s["pages"],
                 s["page_size"], s["tag"]))
        if s["idx"] < 2:
            print("        metadata@sec%d.bin+0: base=%#010x size=%#x word3=%#010x (len=%#x)"
                  % (s["idx"], s["base"], s["size"], s["w3"], len(s["data"])))
            print("        (size == file length: %s)" % (s["size"] == len(s["data"])))
        else:
            print("        NOTE: sec%d does not use the [0, base, size, w3] metadata layout"
                  " (first 8 B: %s); its load base is NOT derivable from this header [unlocated]"
                  % (s["idx"], s["data"][:8].hex()))
    s0 = secs[0]["data"]
    B0 = secs[0]["base"]

    print("\n=== 2. SETP definition records (sec0) [proven] ===")
    recs = parse_setp_records(s0, B0)
    for r in recs:
        print("  @sec0 0x%06X (VA %#010x)  tag=(%#x,%#x) id=%d n=%d p1=%#x p2=%#x p3=%#x c=%#x"
              % (r["off"], r["va"], r["tag"][0], r["tag"][1], r["id"], r["n"],
                 r["p1"], r["p2"], r["p3"], r["c"]))

    print("\n=== 3. option lists (left column) + nested variant lists (right column) [proven] ===")
    by_va = {r["va"]: r for r in recs}
    seen = set()
    for r in recs:
        key = (r["p2"],)
        if key in seen:
            continue
        seen.add(key)
        ents, term = read_u32_list(s0, B0, r["p2"])
        if ents is None:
            print("  p2 VA %#x: not a value list" % r["p2"])
            continue
        print("  list VA %#x (sec0 0x%06X) linked from SETP %d, %d entries, term@0x%X:"
              % (r["p2"], r["p2"] - B0, r["id"], len(ents), term))
        for off, v, sub in ents:
            extra = ""
            if sub:
                srec = by_va.get(sub)
                if srec:
                    sub_vals, _ = read_u32_pairs(s0, B0, srec["p2"])
                    extra = ("  -> sub-record SETP %d @%#x  variants=%s"
                             % (srec["id"], sub, sub_vals))
                else:
                    extra = "  -> %#x (not a parsed SETP record)" % sub
            print("      +%#06x  value=%-3d sub=%#010x%s" % (off, v, sub, extra))

    print("\n=== 4. patch candidates: zero the sub-record pointer of the B&W/ACROS slots [proven] ===")
    dec = load(os.path.join(a.root, "out", "fw", "decoded.bin"))
    cands = []
    seen_ent = set()
    for r in recs:
        if r["id"] not in (1070, 1073):        # still-mode list and movie-mode list
            continue
        ents, term = read_u32_list(s0, B0, r["p2"])
        if ents is None:
            continue
        for off, v, sub in ents:
            if sub and off not in seen_ent:
                seen_ent.add(off)
                cands.append(dict(list_setp=r["id"], list_va=r["p2"], ent_off=off,
                                  value=v, sub=sub,
                                  sub_id=(by_va.get(sub) or {}).get("id")))
    for c in cands:
        info = fflz_literal_map(dec, SEC_HDRS[0], c["ent_off"] + 4)
        cb = [fflz_literal_map(dec, SEC_HDRS[0], c["ent_off"] + 4 + k)["kind"] for k in range(4)]
        print("  SETP %d list entry @sec0 0x%06X: value=%d sub=%#x (SETP %s)"
              % (c["list_setp"], c["ent_off"], c["value"], c["sub"], c["sub_id"]))
        print("      sub-ptr field @sec0 0x%06X  bytes=%s  per-byte fflz=%s"
              % (c["ent_off"] + 4, s0[c["ent_off"] + 4:c["ent_off"] + 8].hex(), cb))
        if all(k == "literal" for k in cb):
            print("      => ALL 4 bytes are literal -> in-place patch OK; decoded offsets %s"
                  % [hex(fflz_literal_map(dec, SEC_HDRS[0], c["ent_off"] + 4 + k)["dec_off"])
                     for k in range(4)])
        else:
            print("      => NOT all literal (LZ back-references) -> cannot be patched in place")

    if a.dat:
        _write_dat(a, dec, [c for c in cands if c["sub_id"] in (1072, 1075)])

    print("\n=== 5. how to apply the patch ===")
    print("  Zero the 4-byte `sub=` field of the entry whose value is the B&W family")
    print("  (value 7).  In the still-mode list (SETP 1070 -> sec0 0x4F40C0) that")
    print("  entry is the one that now shows 'REALA ACE' (it used to be MONOCHROME),")
    print("  and its pointer field is the ONLY one stored as 4 pure literal bytes ->")
    print("  patch decoded.bin 0x4BB45C..0x4BB45F = 00 00 00 00, no recompression.")
    print("  The movie-mode copies (SETP 1073) store the same field as LZ")
    print("  back-references, so they cannot be patched in place; see")
    print("  notes/13-fsim-ui-code.md section 7.2.")
    return 0


def _write_dat(a, dec, cands):
    src = os.path.join(a.root, a.src)
    dst = os.path.join(a.root, "out", "patch_nofilter_1108.DAT")
    raw = bytearray(load(src))
    logical = bytearray(raw[:HDR]) + bytearray(b ^ 0xFF for b in raw[HDR:])
    n = 0
    for c in cands:
        info = fflz_literal_map(dec, SEC_HDRS[0], c["ent_off"] + 4)
        if info["kind"] != "literal":
            print("  SKIP SETP %d entry: not a literal run" % c["list_setp"])
            continue
        o = info["dec_off"]
        before = logical[o:o + 4].hex()
        if c["sub_id"] == 1072:
            logical[o:o + 4] = b"\x00\x00\x00\x00"
        else:
            logical[o:o + 4] = b"\x00\x00\x00\x00"
        print("  patch @0x%X: %s -> %s (SETP %d / value %d)"
              % (o, before, logical[o:o + 4].hex(), c["list_setp"], c["value"]))
        n += 1
    body = logical[HDR:HDR + MAIN_LEN]
    ck = (0xFFFFFFFF - (sum(body) & 0xFFFFFFFF)) & 0xFFFFFFFF
    struct.pack_into("<I", logical, MAIN_CK_OFF, ck)
    out = bytearray(logical[:HDR]) + bytearray(b ^ 0xFF for b in logical[HDR:])
    open(dst, "wb").write(out)
    print("  wrote %s (%d B), %d patch site(s), main checksum -> 0x%08X" % (dst, len(out), n, ck))


if __name__ == "__main__":
    raise SystemExit(main())
