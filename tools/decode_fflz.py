#!/usr/bin/env python3
"""FFLZ (Fujifilm LZ77 variant) decompressor + DAT section extractor.

Verified against FWUP0024.DAT: all four sections decode to exactly the
`unpacked_size` declared in their header, and the SHA-256 of the outputs match the
independently implemented reference decoder.

Container
---------
  file[0x000 : 0x274]  plaintext container header (FujiFirmHeader + region table)
  file[0x274 : EOF]    firmware payload, bit-inverted (XOR 0xFF)
  payload offset 0x20000*k  = a section header (file offset 0x274 + 0x20000*k)

FFLZ section header (20 bytes, little endian, in the *decoded* domain)
      +0  u32 unpacked_size
      +4  u32 packed_size
      +8  u32 pages           (= ceil(packed_size / page_size))
      +12 u32 page_size       (0x4000 = 16 KiB)
      +16 u32 tag             (4 for this file)
      +20 token stream

Token stream (LZ77):
      token < 0x80          literal run of N = token bytes follows
      0x80..0xFF  b         back reference:
                              length   = b & 0x0F
                              distance = ((token & 0x7F) << 4) | (b >> 4)   (1..2047)
                            overlapping copies are allowed; NO +1 bias.

IMPORTANT: the 16 KiB "page_size" is the granularity at which the SoC feeds the
hardware decompressor.  A *token* never straddles a page boundary, but the bytes
of a literal run *can*.  Therefore the packed stream must be decoded as ONE
continuous token stream -- splitting it per 16 KiB page silently drops bytes
(the first section then comes out 10,482 bytes short).
"""
import struct, sys, os, json, hashlib
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAT = os.path.join(ROOT, "FWUP0024.DAT")
OUTDIR = os.path.join(ROOT, "out")
HDR = 0x274          # plaintext header length == payload alignment offset


def load_payload():
    """Return the decoded (bit-inverted) payload starting at file offset HDR."""
    raw = open(DAT, "rb").read()
    return bytes(b ^ 0xFF for b in raw[HDR:])


def parse_header(pay, off):
    u, pk, pages, psz, tag = struct.unpack_from("<IIIII", pay, off)
    return dict(payload_offset=off, unpacked=u, packed=pk, pages=pages,
                page_size=psz, tag=tag)


def plausible(h):
    return (h["tag"] in (1, 2, 3, 4, 5)
            and h["page_size"] in (0x1000, 0x2000, 0x4000, 0x8000)
            and h["unpacked"] > 0 and h["packed"] > 0
            and h["pages"] == (h["packed"] + h["page_size"] - 1) // h["page_size"])


def decompress(pay, h):
    packed = pay[h["payload_offset"] + 20: h["payload_offset"] + 20 + h["packed"]]
    out = bytearray()
    i = 0
    n = len(packed)
    while i < n:
        tok = packed[i]
        i += 1
        if tok < 0x80:
            out += packed[i:i + tok]
            i += tok
        else:
            b = packed[i]
            i += 1
            length = b & 0x0F
            dist = ((tok & 0x7F) << 4) | (b >> 4)
            if dist == 0 or dist > len(out):
                raise ValueError("invalid distance %d at output %d" % (dist, len(out)))
            for _ in range(length):
                out.append(out[-dist])
    return bytes(out)


def find_sections(pay, grid=0x20000):
    found = []
    k = 0
    while 20 + grid * k < len(pay):
        h = parse_header(pay, grid * k)
        if plausible(h):
            found.append(h)
        k += 1
    return found


def main():
    pay = load_payload()
    print("payload: %d bytes (file 0x%X .. EOF)" % (len(pay), HDR))
    secs = find_sections(pay)
    print("FFLZ sections found: %d" % len(secs))
    os.makedirs(os.path.join(OUTDIR, "sections"), exist_ok=True)
    meta = []
    total = 0
    for idx, h in enumerate(secs):
        data = decompress(pay, h)
        ok = len(data) == h["unpacked"]
        fn = os.path.join(OUTDIR, "sections", "sec%d.bin" % idx)
        open(fn, "wb").write(data)
        total += len(data)
        meta.append(dict(idx=idx, file_offset=hex(HDR + h["payload_offset"]),
                         payload_offset=hex(h["payload_offset"]),
                         unpacked=h["unpacked"], packed=h["packed"],
                         pages=h["pages"], page_size=h["page_size"], tag=h["tag"],
                         sha256=hashlib.sha256(data).hexdigest()))
        print("  sec%d @file 0x%08X  unpacked=%-9d packed=%-8d pages=%-4d  %s"
              % (idx, HDR + h["payload_offset"], h["unpacked"], h["packed"],
                 h["pages"], "OK" if ok else "MISMATCH!"))
    json.dump(meta, open(os.path.join(OUTDIR, "sections", "sections.json"), "w"), indent=1)
    print("total decompressed: %d" % total)


if __name__ == "__main__":
    main()
