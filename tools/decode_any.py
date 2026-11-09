#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Decode any FWUP0024* type-6 firmware into a logical image + FFLZ sections.

Usage:
    python decode_any.py <DAT> <outdir>

Produces:
    <outdir>/decoded.bin              logical image (file[0:0x274] + ~file[0x274:])
    <outdir>/sections/sec0.bin ...    FFLZ sections
    <outdir>/sections/sections.json   parameters + sha256
"""
import io, json, os, struct, sys, hashlib

HDR = 0x274
CODE_SIZES = {1: 64, 2: 128, 3: 512, 4: 512, 5: 512, 6: 512, 7: 512, 8: 512}


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
                tok = p[i]; i += 1
                if tok < 0x80:
                    data += p[i:i + tok]; i += tok
                else:
                    b = p[i]; i += 1
                    dist = ((tok & 0x7F) << 4) | (b >> 4)
                    if dist == 0 or dist > len(data):
                        raise ValueError("bad backref at section 0x%X" % off)
                    for _ in range(b & 0x0F):
                        data.append(data[-dist])
            out.append(dict(payload_offset=off, unpacked=u, packed=pk, pages=pages,
                            page_size=psz, tag=tag, data=bytes(data)))
            off += 20 + pk
            if off & 1:
                off += 1
        else:
            off += 2
            if off & 1:
                off += 1
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    dat, outdir = sys.argv[1], sys.argv[2]
    raw = open(dat, "rb").read()
    os_ = struct.unpack_from("<I", raw, 0)[0]
    code_size = CODE_SIZES.get(os_)
    if not code_size:
        raise SystemExit("unsupported os_type %d" % os_)
    v1, v2, ck = struct.unpack_from("<III", raw, 4 + code_size)
    print("file: %s" % dat)
    print("  size=%d os=%d codeSize=%d version=%d.%02X checksum=0x%08X" %
          (len(raw), os_, code_size, v1, v2, ck))
    logical = raw[:HDR] + bytes(b ^ 0xFF for b in raw[HDR:])
    os.makedirs(os.path.join(outdir, "sections"), exist_ok=True)
    open(os.path.join(outdir, "decoded.bin"), "wb").write(logical)
    pay = logical[HDR:]
    secs = decode_sections(pay)
    meta = []
    for idx, s in enumerate(secs):
        fn = os.path.join(outdir, "sections", "sec%d.bin" % idx)
        open(fn, "wb").write(s["data"])
        meta.append(dict(idx=idx, file_offset=hex(HDR + s["payload_offset"]),
                         payload_offset=hex(s["payload_offset"]),
                         unpacked=s["unpacked"], packed=s["packed"], pages=s["pages"],
                         page_size=s["page_size"], tag=s["tag"],
                         sha256=hashlib.sha256(s["data"]).hexdigest()))
        print("  sec%d file=0x%08X unpacked=%-9d packed=%-8d pages=%-4d sha=%s" %
              (idx, HDR + s["payload_offset"], s["unpacked"], s["packed"], s["pages"],
               meta[-1]["sha256"][:16]))
    json.dump(meta, open(os.path.join(outdir, "sections", "sections.json"), "w"), indent=1)
    print("written ->", outdir)


if __name__ == "__main__":
    main()
