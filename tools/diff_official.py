#!/usr/bin/env python3
"""Diff  FWUP0024.DAT  vs  official Fujifilm X-T4 v2.12 FWUP0024.DAT.

Read-only analysis; produces every number quoted in notes/06-diff-official.md.

Layout facts used here (verified against these two files, see notes/03-prior-art.md):
  * container header is PLAINTEXT for file[0x000:0x378]; file[0x378:] is stored as
    byte-wise bitwise NOT (XOR 0xFF).
  * FujiFirmHeader: u32 os_type @0x00, model-code region (512 B for os=6) @0x04, then
    u32 version1/version2/checksum/end @0x204/0x208/0x20C/0x210.
  * FFLZ section header (20 B LE) at 0x20000*k + 0x274:
        +0 unpacked_size, +4 packed_size, +8 pages, +12 page_size(0x4000), +16 tag(4),
        +20 token stream. The stream is decoded CONTINUOUSLY: tokens never straddle a
        16 KiB packed page, but literals/matches freely cross pages, so do NOT decode
        page by page (that loses ~50 B per page).
  * FFLZ token semantics (matches tiredboffin/fffw ffcompress/fflz, verified):
        b0 <  0x80 : literal, copy the next b0 bytes verbatim
        b0 >= 0x80 : two-byte back-reference, b1 follows
                     length   = b1 & 0x0F                        (>= 1)
                     distance = ((b0 & 0x7F) << 4) | (b1 >> 4)     (1..2047, NO +1)
                     copy length bytes from `distance` bytes back in the output,
                     byte by byte, so overlapping copies act as RLE.
    NOTE: distance is stored as-is. tools/decode_fflz.py adds 1 (`dist += 1`) and is
    therefore wrong; the products in out/sections/ use the correct convention.
"""
import hashlib
import json
import os
import struct
import sys

import numpy as np


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WD = ROOT
OURS = os.path.join(WD, "FWUP0024.DAT")
OFFI = os.path.join(WD, "out", "official", "FWUP0024.DAT")
SECDIR = os.path.join(WD, "out", "sections")
OUTDIR = os.path.join(WD, "out", "official")
HDR_LEN = 0x378
GRID = 0x20000
SEC_BASE = 0x274
PAGE = 0x4000
CLUSTER_GAP = 64
MAX_LIST = 40


def decoded_view(buf):
    """plaintext view: [0:HDR_LEN] verbatim, [HDR_LEN:] ^ 0xFF."""
    d = bytearray(buf)
    d[HDR_LEN:] = bytes(x ^ 0xFF for x in d[HDR_LEN:])
    return bytes(d)


def parse_header(buf):
    osv = struct.unpack_from("<I", buf, 0)[0]
    code = {1: 64, 2: 128}.get(osv, 512)
    mc = "".join(chr(buf[4 + i]) for i in range(1, code, 2)).rstrip("0\x00")
    v1, v2, cks, end = struct.unpack_from("<4I", buf, 4 + code)
    return dict(os=osv, code_size=code, model_code=mc, v1=v1, v2=v2,
                checksum=cks, end=end, payload_off=4 + code + 16)


def find_sections(dec):
    secs, k = [], 0
    while SEC_BASE + GRID * k + 20 <= len(dec):
        off = SEC_BASE + GRID * k
        u, pk, pages, psz, tag = struct.unpack_from("<IIIII", dec, off)
        if (0 < pk < u and psz in (0x1000, 0x2000, 0x4000, 0x8000) and tag in (1, 2, 3, 4, 5)
                and pages == (pk + psz - 1) // psz and off + 20 + pk <= len(dec)):
            secs.append(dict(off=off, packed_start=off + 20, unpacked=u, packed=pk,
                             pages=pages, page_size=psz, tag=tag))
        k += 1
    return secs


def decompress(packed, expect):
    out, i, n = bytearray(), 0, len(packed)
    while i < n:
        tok = packed[i]
        i += 1
        if tok < 0x80:
            out += packed[i:i + tok]
            i += tok
        else:
            b = packed[i]
            i += 1
            ln = b & 0x0F
            dist = ((tok & 0x7F) << 4) | (b >> 4)
            if ln == 0 or dist == 0:
                raise ValueError("invalid ref at %#x" % (i - 2))
            s = len(out) - dist
            for _ in range(ln):
                out.append(out[s])
                s += 1
    if len(out) != expect:
        raise ValueError("size %d != declared %d" % (len(out), expect))
    return bytes(out)


def page_out_map(packed):
    """out offset at each 16 KiB packed-page start."""
    m, i, out, n = {}, 0, 0, len(packed)
    while i < n:
        if i % PAGE == 0:
            m[i] = out
        tok = packed[i]
        if tok < 0x80:
            i += 1 + tok
            out += tok
        else:
            out += packed[i + 1] & 0x0F
            i += 2
    return m


def map_offset(packed, target, m):
    page = (target // PAGE) * PAGE
    if page not in m:
        return None, False
    out, i = m[page], page
    while i < target:
        tok = packed[i]
        if tok < 0x80:
            i += 1 + tok
            out += tok
        else:
            out += packed[i + 1] & 0x0F
            i += 2
        if i > target:
            return out, False
    return out, True


def clusters_of(sorted_idx, gap):
    if len(sorted_idx) == 0:
        return []
    out, st, prev = [], int(sorted_idx[0]), int(sorted_idx[0])
    for v in sorted_idx[1:]:
        v = int(v)
        if v - prev <= gap:
            prev = v
        else:
            out.append((st, prev))
            st = prev = v
    out.append((st, prev))
    return out


def main():
    log = []

    def p(s=""):
        print(s)
        log.append(s)

    a = open(OURS, "rb").read()
    b = open(OFFI, "rb").read()
    adec, bdec = decoded_view(a), decoded_view(b)

    p("=" * 78)
    p("FWUP0024 diff:  earlier build  vs  official X-T4 v2.12")
    p("=" * 78)
    p()
    p("== 1. files ==")
    for nm, buf in (("OURS", a), ("OFFICIAL", b)):
        p("  %-8s %12d B  sha256=%s" % (nm, len(buf), hashlib.sha256(buf).hexdigest()))

    ha, hb = parse_header(a), parse_header(b)
    p()
    p("== 2. container header ==")
    for k in ("os", "code_size", "model_code", "v1", "v2", "checksum", "end"):
        va, vb = ha[k], hb[k]
        if k in ("checksum", "end"):
            va, vb = "0x%08X" % va, "0x%08X" % vb
        p("  %-11s ours=%-30s official=%-30s %s" % (k, va, vb, "SAME" if va == vb else "**DIFF**"))
    hdiff = [int(i) for i in np.nonzero(np.frombuffer(a[:HDR_LEN], np.uint8)
                                        != np.frombuffer(b[:HDR_LEN], np.uint8))[0]]
    p("  header bytes differing in [0x000,0x378): %s  (n=%d)" % ([hex(i) for i in hdiff], len(hdiff)))

    sa, sb = find_sections(adec), find_sections(bdec)
    p()
    p("== 3. FFLZ sections ==")
    for i, (x, y) in enumerate(zip(sa, sb)):
        p("  sec%d hdr=0x%08X stream=0x%08X..0x%08X  unpacked=%-9d pages=%-4d"
          % (i, x["off"], x["packed_start"], x["packed_start"] + x["packed"],
             x["unpacked"], x["pages"]))
        p("        packed ours=%-9d official=%-9d delta=%+d"
          % (x["packed"], y["packed"], x["packed"] - y["packed"]))

    n = len(a)
    cls = np.zeros(n, dtype=np.uint8)                 # 0 = padding / inter-section gap
    cls[:HDR_LEN] = 1                                 # 1 = plaintext container header
    cls[HDR_LEN:sa[0]["off"]] = 2                     # 2 = uncompressed payload
    LABEL = {0: "padding/inter-section gap", 1: "container header",
             2: "uncompressed payload (no FFLZ)"}
    for i, s in enumerate(sa):
        c = 10 + i
        cls[s["off"]:min(n, s["packed_start"] + s["packed"])] = c
        LABEL[c] = "sec%d packed stream" % i

    diff = np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8)
    idx = np.nonzero(diff)[0]

    p()
    p("== 4. byte diff: totals per region ==")
    p("  TOTAL differing = %d / %d = %.4f%%" % (len(idx), n, 100.0 * len(idx) / n))
    p("  %-32s %12s %10s %10s" % ("region", "changed", "%of region", "%of all diff"))
    for c in sorted(LABEL):
        sel = cls == c
        sub = int((diff & sel).sum())
        if sub:
            p("  %-32s %12d %9.2f%% %9.2f%%"
              % (LABEL[c], sub, 100.0 * sub / max(1, int(sel.sum())), 100.0 * sub / len(idx)))

    p()
    p("== 5. diff intervals, per region (clusters with gap<=%d) ==" % CLUSTER_GAP)
    maps = {i: page_out_map(adec[s["packed_start"]:s["packed_start"] + s["packed"]])
            for i, s in enumerate(sa)}
    interval_json = {}
    for c in sorted(LABEL):
        sel = idx[cls[idx] == c] if len(idx) else np.array([], dtype=np.int64)
        ivs = clusters_of(sel, CLUSTER_GAP)
        if not ivs:
            continue
        interval_json[LABEL[c]] = [[int(s), int(e), int(diff[s:e + 1].sum())] for s, e in ivs]
        p()
        p("  --- %s : %d interval(s), %d changed bytes ---"
          % (LABEL[c], len(ivs), int(sum(diff[s:e + 1].sum() for s, e in ivs))))
        for st, en in ivs[:MAX_LIST]:
            ch = int(diff[st:en + 1].sum())
            extra = ""
            if 10 <= c <= 13:
                i = c - 10
                sec = sa[i]
                o, exact = map_offset(adec[sec["packed_start"]:sec["packed_start"] + sec["packed"]],
                                      st - sec["packed_start"], maps[i])
                if o is not None:
                    extra = "  -> dec 0x%08X%s" % (o, "" if exact else " (inside token)")
            p("    file 0x%08X..0x%08X  len=%-8d changed=%-8d (%.1f%%)%s"
              % (st, en, en - st + 1, ch, 100.0 * ch / (en - st + 1), extra))
        if len(ivs) > MAX_LIST:
            p("    ... %d more intervals (full list in diff_stats.json)" % (len(ivs) - MAX_LIST))

    p()
    p("== 6. distribution per 0x20000 (128 KiB) block ==")
    blk = idx // GRID
    vals, counts = np.unique(blk, return_counts=True)
    total_blocks = (n + GRID - 1) // GRID
    p("  blocks touched: %d of %d" % (len(vals), total_blocks))
    order = np.argsort(-counts)
    top20 = 0
    for j in order[:20]:
        v, ct = int(vals[j]), int(counts[j])
        off = v * GRID
        c = int(cls[min(off + 1, n - 1)])
        p("    block %3d (0x%08X) changed=%-8d [%s]" % (v, off, ct, LABEL[c]))
        top20 += ct
    p("  top-20 blocks hold %.1f%% of all differing bytes" % (100.0 * top20 / len(idx)))
    blk_list = [dict(block=int(v), file_offset=int(v) * GRID, changed=int(ct))
                for v, ct in zip(vals, counts)]

    p()
    p("== 7. decompressed FFLZ sections: ours vs official ==")
    import tempfile
    tmp = os.path.join(tempfile.gettempdir(), "xt4wr", "official_sections")
    os.makedirs(tmp, exist_ok=True)
    sec_summary = []
    for i, (x, y) in enumerate(zip(sa, sb)):
        op = os.path.join(SECDIR, "sec%d.bin" % i)
        if os.path.exists(op):
            da = open(op, "rb").read()
            src = "out/sections"
        else:
            da = decompress(adec[x["packed_start"]:x["packed_start"] + x["packed"]], x["unpacked"])
            src = "recomputed"
        db = decompress(bdec[y["packed_start"]:y["packed_start"] + y["packed"]], y["unpacked"])
        open(os.path.join(tmp, "sec%d_official.bin" % i), "wb").write(db)
        same = da == db
        dm = np.frombuffer(da, np.uint8) != np.frombuffer(db, np.uint8)
        cnt = int(dm.sum())
        pack_d = int(diff[sa[i]["packed_start"]:sa[i]["packed_start"] + sa[i]["packed"]].sum())
        p()
        p("  sec%d  (ours from %s, len %d)" % (i, src, len(da)))
        p("    packed       changed=%-9d (%.2f%% of %d)" % (pack_d, 100.0 * pack_d / x["packed"], x["packed"]))
        p("    decompressed changed=%-9d (%.3f%% of %d)   identical=%s"
          % (cnt, 100.0 * cnt / len(da), len(da), same))
        p("    sha256 ours     =%s" % hashlib.sha256(da).hexdigest())
        p("    sha256 official =%s" % hashlib.sha256(db).hexdigest())
        ivs = []
        if cnt:
            ivs = clusters_of(np.nonzero(dm)[0], 16)
            p("    decompressed diff intervals (gap<=16): %d, total changed %d" % (len(ivs), cnt))
            for st, en in ivs[:MAX_LIST]:
                p("      dec 0x%08X..0x%08X  len=%-8d changed=%-6d"
                  % (st, en, en - st + 1, int(dm[st:en + 1].sum())))
            if len(ivs) > MAX_LIST:
                p("      ... %d more" % (len(ivs) - MAX_LIST))
        sec_summary.append(dict(idx=i, hdr=x["off"], stream_start=x["packed_start"],
                                unpacked=x["unpacked"], pages=x["pages"],
                                packed_ours=x["packed"], packed_official=y["packed"],
                                packed_changed=pack_d,
                                packed_changed_pct=100.0 * pack_d / x["packed"],
                                dec_changed=cnt, dec_changed_pct=100.0 * cnt / len(da),
                                dec_identical=same,
                                sha_ours=hashlib.sha256(da).hexdigest(),
                                sha_official=hashlib.sha256(db).hexdigest(),
                                dec_intervals=[[int(s), int(e), int(dm[s:e + 1].sum())]
                                               for s, e in ivs]))

    p()
    p("== 8. checksum relation:  checksum ?= sum(raw[0x214:EOF]) + K ==")
    for nm, buf, h in (("OURS", a, ha), ("OFFICIAL", b, hb)):
        s = int(np.frombuffer(buf[0x214:], np.uint8).astype(np.uint64).sum()) & 0xFFFFFFFF
        p("  %-8s checksum=0x%08X  sum(0x214..EOF)=0x%08X  K=(checksum-sum)&0xFFFFFFFF=0x%08X"
          % (nm, h["checksum"], s, (h["checksum"] - s) & 0xFFFFFFFF))

    p()
    p("== 9. model literal in the decoded view ==")
    for nm, d in (("OURS", adec), ("OFFICIAL", bdec)):
        q = d.find(b"FUJIDSCFBLOG_DSF.R98.")
        if q >= 0:
            s = d[q:q + 48].split(b"\x00")[0]
            p("  %-8s @file 0x%06X  %r   (block %d, region: %s)"
              % (nm, q, s.decode("latin-1"), q // GRID, LABEL[int(cls[q])]))
        else:
            p("  %-8s not found" % nm)
    m5 = adec.find(b"X-M5")
    t4 = bdec.find(b"X-T4")
    p("  first b'X-M5' in OURS decoded: %s ; first b'X-T4' in OFFICIAL decoded: %s"
      % (hex(m5) if m5 >= 0 else "none", hex(t4) if t4 >= 0 else "none"))

    res = dict(ours=dict(path=OURS, size=len(a), sha256=hashlib.sha256(a).hexdigest()),
               official=dict(path=OFFI, size=len(b), sha256=hashlib.sha256(b).hexdigest()),
               header=dict(ours=ha, official=hb, differing_bytes=hdiff),
               differing_total=int(len(idx)), differing_pct=100.0 * len(idx) / n,
               per_region={LABEL[c]: dict(changed=int((diff & (cls == c)).sum()),
                                          size=int((cls == c).sum()))
                           for c in sorted(LABEL)},
               intervals=interval_json,
               blocks_touched=int(len(vals)), blocks_total=int(total_blocks),
               blocks=blk_list,
               sections=sec_summary)
    json.dump(res, open(os.path.join(OUTDIR, "diff_stats.json"), "w"), indent=1)
    txt = "\n".join(log) + "\n"
    open(os.path.join(OUTDIR, "diff_report.txt"), "w", encoding="utf-8").write(txt)
    p()
    p("wrote %s" % os.path.join(OUTDIR, "diff_stats.json"))
    p("wrote %s" % os.path.join(OUTDIR, "diff_report.txt"))
    p("official decoded sections -> %s" % tmp)


if __name__ == "__main__":
    main()
