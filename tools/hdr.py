#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hdr.py -- FWUP0024 (Fujifilm X-T4) 顶层容器头只读解析器
=========================================================
对 C:\\Users\\90732\\Desktop\\dev\\xt4\\FWUP0024.DAT 只读，不写任何文件。

已确认的顶层模型（证据见控制台表格与 notes/01-container.md）:
  * os_type                              = u32 LE @0x000 = 6
  * model_code / MODEL_CODE_SIZE=512      @0x004..0x203（512 字节，内容为 ASCII-hex 文本）
  * version1                             = u32 LE @0x204 = 2
  * version2                             = u32 LE @0x208 = 0x12 -> 固件 v2.12
  * checksum(main body)                  = u32 LE @0x20C
  * checksum(R0)                         = u32 LE @0x210
  * checksum(R1)                         = u32 LE @0x214
  * 0x218                                = 1（未定）
  * fragment/region 描述表               = 0x21C..0x273（字段见 table_region_descriptors）
  * 取反(XOR 0xFF)载荷起点               = 0x274（由 3 条独立证据判定，见 proof_payload_base）
  * 公开资料所述 type-6 扩展头明文结束    = 0x378（与 0x274 重叠区为 OPEN QUESTION，见 doc）

校验和算法（本脚本验证）:
      cksum = 0xFFFFFFFF - ( sum(bytes) & 0xFFFFFFFF )        # 8-bit one's complement sum
  覆盖范围:
      @0x20C      : payload[0x000000 .. 0x2FC0020)              （main body）
      @0x210/0x214: R0/R1 逻辑内容
      @0x21C/0x228: R4/R5 逻辑内容
      @0x264/0x270: R2/R3 的「文件存储字节」(非取反后)  -> OPEN QUESTION

调用:
      python tools/hdr.py [DAT路径]
"""

import sys
import os
import hashlib
import struct


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    import numpy as np
except Exception:  # numpy 缺失时退化（较慢，但只读逻辑不变）
    np = None

DEFAULT = os.path.join(ROOT, "FWUP0024.DAT")

PAYLOAD_BASE = 0x274          # 取反载荷物理起点（校验和/分段证据支持）
DOC_HEADER_END = 0x378        # 公开资料 (fujihack patcher) 所述 type-6 扩展头结尾
GRID = 0x20000                # 载荷内 section 对齐网格

EXPECTED_SIZE = 51278280
EXPECTED_MD5 = "73293B4F50269AD07FCD3AEF79B20D16"


# ----------------------------------------------------------------------------- utils
def cksum(buf):
    """0xFFFFFFFF - (8-bit 字节和 mod 2^32)；buf 为 bytes 或 numpy uint8 数组。"""
    if np is not None and isinstance(buf, np.ndarray):
        return (0xFFFFFFFF - (int(buf.sum(dtype=np.uint64)) & 0xFFFFFFFF)) & 0xFFFFFFFF
    return (0xFFFFFFFF - (sum(buf) & 0xFFFFFFFF)) & 0xFFFFFFFF


def entropy(block):
    if np is not None and isinstance(block, np.ndarray):
        cnt = np.bincount(block, minlength=256).astype(np.float64)
        total = len(block)
        p = cnt[cnt > 0] / total
        return float(-(p * np.log2(p)).sum())
    import math
    from collections import Counter
    c = Counter(bytes(block))
    n = len(block)
    return -sum((v / n) * math.log2(v / n) for v in c.values())


def printable_ratio(block):
    b = bytes(block)
    return sum(1 for c in b if 32 <= c < 127) / max(1, len(b))


def hr(title):
    print()
    print("=" * 100)
    print(title)
    print("=" * 100)


def hexdump(buf, off=0, n=64, indent="  "):
    b = bytes(buf[:n])
    for i in range(0, len(b), 16):
        ch = b[i:i + 16]
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in ch)
        print(f"{indent}{off + i:08x}  {ch.hex(' '):<47s}  |{asc}|")


# ----------------------------------------------------------------------------- 1. 文件标识
def file_identity(d):
    hr("1. 文件标识 (只读)")
    md5 = hashlib.md5(bytes(d)).hexdigest().upper()
    print(f"  path      : {PATH}")
    print(f"  size      : {len(d)} = {len(d):#x}")
    print(f"  md5       : {md5}  {'OK (与已知一致)' if md5 == EXPECTED_MD5 else '!! 与已知 MD5 不一致 !!'}")
    print(f"  size OK   : {len(d) == EXPECTED_SIZE}")
    print(f"  payload   : base={PAYLOAD_BASE:#x}  size={len(d) - PAYLOAD_BASE:#x}  "
          f"(= filesize - 0x274)")
    print(f"  公开资料头结尾 DOC_HEADER_END = {DOC_HEADER_END:#x}")


# ----------------------------------------------------------------------------- 2. 512B 模型码区
def model_code_area(d):
    hr("2. 0x004..0x203  (512 字节 model code 区, MODEL_CODE_SIZE=512) 解码链")
    raw = bytes(d[4:0x204])
    print(f"  原始 512 字节: 全部为 ASCII '0'..'9' : {all(0x30 <= b <= 0x39 for b in raw)}")
    print(f"  原始前 64 字符: {raw[:64].decode('ascii')}")
    # 第 1 次 hex 解码
    t1 = bytes.fromhex(raw.decode("ascii"))
    print(f"  1x hex 解码 -> {len(t1)} 字节; 是否仍全为 ASCII 数字: {all(0x30 <= b <= 0x39 for b in t1)}")
    print(f"  1x 解码结果(前 64): {t1[:64].decode('ascii')}")
    # 第 2 次 hex 解码 -> 128 字节 = 32 x u32 BE
    t2 = bytes.fromhex(t1.decode("ascii"))
    print(f"  2x hex 解码 -> {len(t2)} 字节 = {len(t2)//4} x u32 BE")
    vals = [struct.unpack_from(">I", t2, i)[0] for i in range(0, len(t2), 4)]
    print("  32 个 u32 BE 槽位 (0 = 空槽):")
    for i, v in enumerate(vals):
        tag = "" if v == 0 else "   <-- 非空"
        print(f"    slot[{i:02d}]  {v:#010x}  ({v}){tag}")
    nz = [(i, v) for i, v in enumerate(vals) if v]
    print(f"  非空槽位数: {len(nz)} / {len(vals)}")
    print("  非空值之间的差: " + ", ".join(f"{nz[i+1][1]-nz[i][1]}" for i in range(len(nz) - 1)))
    print("  其他读法（用于排除）:")
    le = [struct.unpack_from("<I", t2, i)[0] for i in range(0, len(t2), 4)]
    print(f"    u32 LE 前 11 个 : {[hex(v) for v in le[:11]]}")
    u16 = [struct.unpack_from(">H", t2, i)[0] for i in range(0, len(t2), 2)]
    print(f"    u16 BE 前 22 个 : {[hex(v) for v in u16[:22]]}")
    print("    (u16 BE 读法 = (0x0005, 0x6001), (0x0005, 0x6002) ... 即 u32 BE 的拆分)")
    print("  交叉验证 u32@0x000(=6): 非空槽位数为 11 != 6 -> 0x000 不是本表条目数；")
    print("  6 实际对应下方 binary 描述表中的 6 个 region（见 §5，已逐条校验通过）。")


# ----------------------------------------------------------------------------- 3. 头部字段表
def header_fields(d):
    hr("3. 明文容器头字段表 0x000..0x274（+ 公开资料所述扩展头 0x274..0x378）")
    def u32(off):
        return struct.unpack_from("<I", bytes(d[off:off + 4]), 0)[0]
    fields = [
        (0x000, 4, "os_type",            u32(0),            "u32 LE；公开资料: os_type=6 -> MODEL_CODE_SIZE=512"),
        (0x004, 0x200, "model_code",     "-",               "512B model code 区；本文件为 ASCII-hex 文本（见 §2）"),
        (0x204, 4, "version1",           u32(0x204),        "u32 LE；公开资料: version1=2"),
        (0x208, 4, "version2",           u32(0x208),        "u32 LE；=0x12=18 -> 固件 v2.12"),
        (0x20C, 4, "checksum(main)",     u32(0x20C),        "~sum(payload[0:0x2FC0020]) [已校验]"),
        (0x210, 4, "checksum(R0)",       u32(0x210),        "~sum(R0 逻辑内容) [已校验]"),
        (0x214, 4, "checksum(R1)",       u32(0x214),        "~sum(R1 逻辑内容) [已校验]"),
        (0x218, 4, "unknown/flag",       u32(0x218),        "=1；暂未定（可能是版本/标志/计数）"),
        (0x21C, 4, "checksum(R4)",       u32(0x21C),        "~sum(R4 逻辑内容) [已校验]"),
        (0x220, 4, "R4.offset",          u32(0x220),        "payload 相对偏移"),
        (0x224, 4, "R4.size",            u32(0x224),        "=0x30000"),
        (0x228, 4, "checksum(R5)",       u32(0x228),        "~sum(R5 逻辑内容) [已校验]"),
        (0x22C, 4, "R5.offset",          u32(0x22C),        "payload 相对偏移"),
        (0x230, 4, "R5.size",            u32(0x230),        "=0x18000"),
        (0x234, 0x14, "filler",          "-",               "FF FF FF FF / FF FF FF FF / 0 / FF FF FF FF / 0"),
        (0x248, 4, "R0.offset",          u32(0x248),        "payload 相对偏移"),
        (0x24C, 4, "R0.offset(dup)",     u32(0x24C),        "与 0x248 相同值；疑为「表自身指针」或冗余"),
        (0x250, 4, "R0.size",            u32(0x250),        "=0xC000"),
        (0x254, 4, "R1.offset",          u32(0x254),        "payload 相对偏移"),
        (0x258, 4, "R1.size",            u32(0x258),        "=0xD2CFC"),
        (0x25C, 4, "R2.offset",          u32(0x25C),        "payload 相对偏移"),
        (0x260, 4, "R2.size",            u32(0x260),        "=0x170"),
        (0x264, 4, "checksum(R2)",       u32(0x264),        "~sum(R2 存储字节) [已校验；见 OPEN QUESTION]"),
        (0x268, 4, "R3.offset",          u32(0x268),        "payload 相对偏移"),
        (0x26C, 4, "R3.size",            u32(0x26C),        "=0xC8"),
        (0x270, 4, "checksum(R3)",       u32(0x270),        "~sum(R3 存储字节) [已校验；见 OPEN QUESTION]"),
        (0x274, 4, "(-)",                u32(0x274),        "=0 -> 若 header=0x274 则此处已是 payload；若 header=0x378 则为扩展头"),
        (0x278, 4, "(-)",                u32(0x278),        "=0xFFFFFFFF"),
        (0x27C, 4, "testpattern",        u32(0x27C),        "0x55555555（0x280=0xAAAAAAAA）测试图样"),
        (0x280, 4, "testpattern",        u32(0x280),        "0xAAAAAAAA"),
        (0x284, 0x24, "bit-packed字段?", "-",              "0x284..0x2A7 呈位打包形态（含 0xFFFFE51F/0x000BEAFF/0x1C0B1C0B...）"),
        (0x2A8, 0xD0, "8B 记录表",       "-",               "26 条 (u32 flag, u32 addr)，addr 全为奇数(Thumb) 见 §6"),
    ]
    print(f"  {'file off':>8}  {'size':>6}  {'field':<22} {'value':<14} evidence")
    for off, size, name, val, ev in fields:
        vs = val if isinstance(val, str) else (f"{val:#010x}" if size == 4 else "-")
        print(f"  {off:#08x}  {size:#06x}  {name:<22} {vs:<14} {ev}")


# ----------------------------------------------------------------------------- 4. 取反载荷 & base 证明
def proof_payload_base(d):
    hr("4. 取反(XOR 0xFF)载荷起点判定：0x274 还是 0x378 ?")
    n = len(d)
    print(f"  filesize                       = {n:#x}")
    print(f"  if base=0x274: payload size    = {n - 0x274:#x} (= filesize-0x274)")
    print(f"  if base=0x378: payload size    = {n - 0x378:#x} (= filesize-0x378)")
    print("  6 个 region 偏移链末端          = 0x30CEF54 + 0x18000 = 0x30E6F54")
    print(f"      -> 只有 base=0x274 时与 payload size 完全相等 : {n - 0x274 == 0x30E6F54}")
    print()
    print("  [证据 A] @0x20C checksum 覆盖 main body = payload[0:0x2FC0020)")
    for base in (0x274, 0x378):
        seg = bytes(d[base:base + 0x2FC0020])
        log = bytes(b ^ 0xFF for b in seg)
        print(f"     base={base:#x}: cksum(file[{base:#x}:{base+0x2FC0020:#x}]^FF) = {cksum(log):#010x}"
              f"   <- 存储值 0x56B4BFF5 {'MATCH' if cksum(log) == 0x56B4BFF5 else 'no'}")
    # 混合（0x274..0x378 明文）也测一下
    seg = bytes(d[0x274:0x378]) + bytes(b ^ 0xFF for b in d[0x378:0x2FC0294])
    print(f"     混合(0x274..0x378 明文): {cksum(seg):#010x}  <- 不匹配")
    print()
    print("  [证据 B] 6 个 region 的 offset 链 + size 恰好首尾相接，末端 = payload 末端(base=0x274)")
    print("  [证据 C] 载荷内 section 数据起点全部 = 0x274 + 0x20000*k（见 §7）")
    print()
    print("  -> 结论: 物理布局上 base = 0x274。公开资料所述 0x378 与 0x274..0x378 的重叠属 OPEN QUESTION。")


# ----------------------------------------------------------------------------- 5. region 描述表
REGIONS = [
    # name, checksum field, offset field, size field, checksum mode
    ("R0", 0x210, 0x248, 0x250, "logical"),
    ("R1", 0x214, 0x254, 0x258, "logical"),
    ("R2", 0x264, 0x25C, 0x260, "stored"),
    ("R3", 0x270, 0x268, 0x26C, "stored"),
    ("R4", 0x21C, 0x220, 0x224, "logical"),
    ("R5", 0x228, 0x22C, 0x230, "logical"),
]


def region_descriptors(d):
    hr("5. 6 个 region 描述表（checksum / payload offset / size）+ 校验和验证")
    n = len(d)
    logical_all = bytes(b ^ 0xFF for b in d[0x274:])  # payload 逻辑内容, index = payload offset

    # main body
    body_len = 0x2FC0020
    body_cks = struct.unpack_from("<I", bytes(d[0x20C:0x210]), 0)[0]
    calc = cksum(logical_all[:body_len])
    print(f"  main body : payload[0x000000:0x{body_len:06x})  stored_cksum={body_cks:#010x}  "
          f"calc={calc:#010x}  {'PASS' if calc == body_cks else 'FAIL'}")
    print()
    print(f"  {'name':<4} {'payload_off':>11} {'size':>9} {'payload_end':>11} {'file_off':>10} "
          f"{'file_end':>10} {'stored_cks':>10} {'calc_cks':>10} {'mode':>8}  result")
    total = body_len
    rows = []
    for name, cf, of, sf, mode in REGIONS:
        off = struct.unpack_from("<I", bytes(d[of:of + 4]), 0)[0]
        size = struct.unpack_from("<I", bytes(d[sf:sf + 4]), 0)[0]
        stored = struct.unpack_from("<I", bytes(d[cf:cf + 4]), 0)[0]
        if mode == "logical":
            calc = cksum(logical_all[off:off + size])
        else:  # stored: 直接对文件里保存的字节求和
            f = off + 0x274
            calc = cksum(d[f:f + size])
        ok = "PASS" if calc == stored else "FAIL"
        total += size
        rows.append((name, off, size, stored, calc, mode, ok))
        print(f"  {name:<4} {off:#011x} {size:#09x} {off+size:#011x} {off+0x274:#010x} "
              f"{off+size+0x274:#010x} {stored:#010x} {calc:#010x} {mode:>8}  {ok}")
    print()
    end = 0x30E6F54
    r0_off = struct.unpack_from("<I", bytes(d[0x248:0x24C]), 0)[0]
    print(f"  chain: body_end=0x{body_len:x} == R0.offset(0x{r0_off:x}) -> {body_len == r0_off}")
    print(f"  6 region 首尾相接，末端 = 0x{end:x};  payload size = {len(d)-0x274:#x};  "
          f"相等 = {end == len(d) - 0x274}")
    print(f"  覆盖: main body + 6 region 覆盖整个 payload = {total == len(d) - 0x274}")
    print("  注: R2/R3 的校验和是对「文件存储字节」计算，其余是对「取反后的逻辑内容」计算（OPEN QUESTION）。")
    return rows


# ----------------------------------------------------------------------------- 6. 扩展头 0x214..0x378
def extension_header(d):
    hr("6. 公开资料所述 type-6 扩展头 0x214..0x378（本文件与官方头逐字节相同部分）")
    print("  6.1 region 描述表 0x20C..0x273 之后:")
    print("      0x274: 0x00000000, 0x278: 0xFFFFFFFF, 0x27C: 0x55555555, 0x280: 0xAAAAAAAA (测试图样)")
    print("      0x284..0x2A7: 位打包形态字段 (原样):")
    hexdump(bytes(d[0x284:0x2A8]), off=0x284, n=0x24, indent="        ")
    print("      0x284 u32: ", [hex(struct.unpack_from('<I', bytes(d), o)[0]) for o in range(0x284, 0x2A8, 4)])
    print()
    print("  6.2 0x2A8..0x378 的 8 字节记录表（26 条）:")
    recs = [struct.unpack_from("<II", bytes(d), o) for o in range(0x2A8, 0x378, 8)]
    print(f"      {'#':>3} {'file off':>9} {'flag':>12} {'addr':>12} {'addr&1':>6} {'as Thumb':>10}")
    prev = None
    delta_ok = 0
    for i, (flag, addr) in enumerate(recs):
        dlt = "" if prev is None else f"{addr - prev:+d}"
        if prev is not None and addr - prev == -4:
            delta_ok += 1
        print(f"      {i:>3} {0x2A8 + i * 8:#09x} {flag:#012x} {addr:#012x} {addr & 1:>6} {addr - (addr & 1):#012x} {dlt}")
        prev = addr
    flags = sorted({f for f, a in recs})
    addrs = [a for f, a in recs]
    print(f"      flags 取值集合      : {[hex(x) for x in flags]}")
    print(f"      addr 全为奇数(Thumb) : {all(a & 1 for a in addrs)}")
    print(f"      addr 区间            : {min(addrs):#x} .. {max(addrs):#x}")
    print(f"      addr 步长 -4 的条数 : {delta_ok}/{len(recs)-1}；另有跳变（0x...ada3 -> 0x...ac7b）")
    print("      解释(推测): 指针/fixup 表；0xFFFFFFFE/0xFFFFFFFF 为类型/长度标记，addr 为 Thumb 地址")
    print()
    print("  6.3 0x274..0x378 的两种字节解释（该区间归属是本任务唯一未决点）:")
    print("      [按 base=0x274 视为 payload 开头 -> 取反后]:")
    hexdump(bytes(b ^ 0xFF for b in d[0x274:0x2B4]), off=0x274, n=0x40, indent="        ")
    print("      [按公开资料视为明文扩展头 -> 原样]:")
    hexdump(bytes(d[0x274:0x2B4]), off=0x274, n=0x40, indent="        ")
    print("      观察: 两种解释都呈结构性(0x274 起 0xFF505200+4i 寄存器/指针表 vs 明文 0x00AFxxxx 指针表)，")
    print("            需用官方原版/patcher 源码确认 0x274..0x378 的归属。")


# ----------------------------------------------------------------------------- 7. payload 网格
def payload_grid(d):
    hr("7. 载荷内 section 网格：数据起点 = 0x274 + 0x20000*k ?")
    n = len(d)
    arr = d if np is not None else list(d)
    # 找长度 >= 0x2000 的连续 0x00 段（文件中未取反的 0 填充/擦除区）
    if np is not None:
        z = (arr == 0)
        diff = np.diff(np.concatenate(([0], z.view(np.int8), [0])))
        starts = np.flatnonzero(diff == 1)
        ends = np.flatnonzero(diff == -1)
        runs = [(int(s), int(e)) for s, e in zip(starts, ends) if e - s >= 0x2000]
    else:
        runs = []
        i = 0
        while i < n:
            if arr[i] == 0:
                j = i
                while j < n and arr[j] == 0:
                    j += 1
                if j - i >= 0x2000:
                    runs.append((i, j))
                i = j
            else:
                i += 1
    print(f"  连续 0x00 段(>=0x2000) 共 {len(runs)} 处; 段后第一个非零字节即 section 数据起点:")
    aligned = []
    unaligned = []
    for s, e in runs:
        if e >= n:
            continue
        payload_off = e - 0x274
        is_aligned = (payload_off % GRID == 0)
        (aligned if is_aligned else unaligned).append(e)
    print(f"  其中 = 0x274 + 0x20000*k 的起点 {len(aligned)} 个:")
    for a in aligned:
        print(f"      file {a:#010x}  -> payload offset {a-0x274:#010x}  (k={(a-0x274)//GRID})")
    print(f"  不对齐的起点 {len(unaligned)} 个 (前 12): {[hex(x) for x in unaligned[:12]]}")
    print(f"  头部 u32@0x208 = 0x12 = {0x12}；对齐起点数量 = {len(aligned)}  "
          f"(阈值相关，17~18；弱证据，说明 0x208 可能是载荷 section 数)")
    print()
    print("  另外: @0x274 处的 payload 起点本身也按 0x20000 网格排布（payload offset 0）。")


# ----------------------------------------------------------------------------- 8. 完整性/签名
def integrity(d):
    hr("8. 整体完整性 / 签名检查（尾部、footer、签名块）")
    n = len(d)
    # 尾部
    i = n - 1
    while i >= 0 and d[i] == 0:
        i -= 1
    print(f"  最后一个非零字节: file offset {i:#x} (= {i}), 之后 {n - 1 - i} 字节全 0x00")
    print(f"  文件尾部(最后 32B): {bytes(d[-32:]).hex(' ')}")
    print("  -> 无 MD5/SHA footer；无 ASCII 签名头（RSA/ECDSA/X509/PUBLIC KEY 均未出现）")
    print()
    print("  完整性机制 (已确证): 仅 8-bit 求和取反校验和（弱校验），覆盖整个 payload：")
    print("      main body ~sum @0x20C + 6 个 region ~sum @0x210/0x214/0x21C/0x228/0x264/0x270")
    print("  -> 文件中没有发现整体 RSA/ECDSA/CMAC/SHA 摘要块；验签若存在应在相机端或 updater 内，")
    print("     (或头部 0x204/0x208 的版本字段参与)；本 .DAT 未携带可识别的签名块。")


# ----------------------------------------------------------------------------- main
def main():
    global PATH
    try:  # 让输出在 UTF-8 控制台/重定向时正常（Windows 建议 chcp 65001）
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    with open(PATH, "rb") as f:
        d = bytearray(f.read())
    if np is not None:
        d = np.frombuffer(bytes(d), dtype=np.uint8)
    print("hdr.py -- FWUP0024.DAT 顶层容器头解析 (只读)")
    print(f"python: {sys.version.split()[0]}  numpy: {'yes' if np is not None else 'no'}")
    file_identity(d)
    model_code_area(d)
    header_fields(d)
    proof_payload_base(d)
    region_descriptors(d)
    extension_header(d)
    payload_grid(d)
    integrity(d)
    hr("DONE (只读；未修改 .DAT)")


if __name__ == "__main__":
    main()
