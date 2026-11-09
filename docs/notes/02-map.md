# 02 全文件区域测绘 (Region Map) — FWUP0024_aefix_1106.DAT

> 任务：region-mapper / task-2。只做逆向分析与结构文档，.DAT 全程只读。
> 状态：**已完成**（基于原始 .DAT + Lead 确认的解码镜像 `out/decoded.bin` + Lead 解出的 4 个 FFLZ 段 `out/sections/sec*.bin`）。
> 说明：本文件所有 offset 均指**文件偏移**（原始 .DAT 与 decoded.bin 同尺寸 51,278,280 B = `0x30E71C8`，偏移一致）。

---

## 0. TL;DR（结论摘要）

1. **容器 = 明文头 + XOR 0xFF 载荷 + 128KB 分块网格**：
   - `0x000000..0x000274`：明文容器头（`u32@0 = 6`，`0x04..0x203` 为 512 字节 ASCII-hex，两层 hex 解码后是 128 字节表；`0x204` 起为二进制字段/指针；`0x27C` 有 `55 55 55 55 / AA AA AA AA` 测试图样）。
   - `0x000274..EOF`：**逐字节 XOR 0xFF** 存储；解码镜像 = `out/decoded.bin`（**Lead 最终版，base=0x274**；早期 base=0x378 版本仅差 `0x274..0x378` 这一小段）。解码后出现 `ThreadX SMP/Cortex-A7/GNU Version G5.6.2.5.0`、`FUJIFILM`、`X-T4`、ARM 异常向量表。**解码镜像上一切 magic/字符串/文件系统扫描才有效；在原始 .DAT 上的扫描结果是取反域噪声，已作废。**
   > 注：`out/map.csv` 等窗口统计是基于旧版 decoded.bin(0x378) 计算的；新版仅差 `0x274..0x378` 的 0x104 字节，且熵对取反不变，对窗口级结论可忽略。
2. **载荷按 128KB (0x20000) 分块，块起点 = 文件偏移 `0x20000*k + 0x274`**。用 4 个 FFLZ 压缩段头、14 个区段起点、28 个填充段端点独立验证（详见 §4）。每块内数据之后用 `0x00` 填充或整块 `0xFF` 表示擦除/空块。全文件 `0xFF` 17.85 MB + `0x00` 2.03 MB = **19.88 MB（38.8%）填充/擦除**。
3. **真正的固件主体 = 4 个 FFLZ 压缩段（私有 LZ77，已由 Lead 解出）+ 明文代码/配置/资源区**：
   | FFLZ 段 | 文件偏移 | 打包 B | 解压 B | 页数 | 解压产物 | 内容（本报告 §5 分类） |
   |---|---|---|---|---|---|---|
   | sec0 | `0x00260274` | 3,449,482 | 7,420,408 | 211 | `out/sections/sec0.bin` | ARM32 主程序 + Exif/XMP/RIFF 模板 + UI 服务/错误串 |
   | sec1 | `0x005C0274` | 5,256,655 | 9,437,184 | 321 | `out/sections/sec1.bin` | 系统/程序代码（libc/POSIX/getopt/errno 串），ARM 代码密度最高 |
   | sec2 | `0x00AE0274` | 4,632,713 | 10,240,000 | 283 | `out/sections/sec2.bin` | 网络/Wi-Fi 协议栈 + 设置逻辑（MAC/IP ADDRESS、STA TIME…） |
   | sec3 | `0x01A00274` | 3,310,991 | 6,446,348 | 203 | `out/sections/sec3.bin` | **非代码**：u16 表开头，疑似字体/度量/资源表 |
   合计解压 **33,543,940 B**（约 32 MB），打包合计 16,649,841 B（压缩率 ~49.6%）。
4. 编码镜像中**没有**标准压缩容器或文件系统：gzip/xz/lzma/zlib/bzip2/zstd/squashfs/cramfs/jffs2/ubifs/ext/FAT/ELF/uImage/FDT/zip/tar/PNG/JPEG(font) 全部未通过结构校验（§7）。私有 FFLZ 是唯一压缩格式。
5. 剩余大面积内容：11.37 MB 多语言 UI 字符串（UTF-16LE）、2.32 MB 16-bit 表、1.53 MB 高熵未识别块、1.0 MB HEVC/H.265 资源、1.21 MB 尾部 Thumb-2 程序区（含双份 0x49A2 B 重复数据）。

---

## 1. 本任务产物（out/ 与 tools/）

| 产物 | 说明 |
|---|---|
| `out/map.csv` | **主表**：12520 个 4KB 窗口 × `window_offset,window_size,entropy,printable_ratio,hints`（hints 分号分隔：`ent:`/`fill:`/`txt:`/`magic:`/`arm32:`/`thumb:`/`zeros:`）。**在 decoded.bin 上计算** |
| `out/entropy.csv` | 同上，仅熵/可打印比两列（供其他成员快速读） |
| `out/entropy_classes.csv` | 低/中/高熵连续区段（阈值：低 <3.5，中 3.5–7.0，高 ≥7.0 bits/byte） |
| `out/regions.csv` | 4KB 窗口级粗分类合并区段（fill/text/code-arm/code-thumb/high-ent/mid-high/mid/low + 证据串） |
| `out/magics.csv`, `out/containers.csv` | magic 命中（含结构校验/受限解压验证结果）与 high/med 置信容器候选 |
| `out/fills.csv` | 全部 `0x00/0xFF/0x55/0xAA` 长填充段（≥256B；decoded 镜像） |
| `out/repeats.csv` | 高频重复 3/4 字节模式（全文件统计） |
| `out/summary.json` | 全局汇总（尺寸、熵、magic 计数、填充、top n-gram、分类计数） |
| `out/blocks128.csv` | **128KB 块级分类**（熵、FF/00%、可打印、UTF-16、指针表比、ARM/Thumb capstone 采样、字符串数、标签） |
| `out/sections.csv` | 由 blocks128 合并出的「解码镜像区块表」（§3 表的机器可读版） |
| `out/sections_report.json` | 4 个 FFLZ 解压段的定量分析（熵/覆盖率/magic/字符串） |
| `out/sections_strings.txt` | 4 段各 20 条可打印字符串样本（§5 引用） |
| `out/extract_attempts.csv` | 所有容器/解压/文件系统**尝试记录**（成功/失败原因） |
| `out/extracted/` | 实际解出的资源：`xmp_sec0_A.xmp`(12,236 B)、`xmp_sec0_B.xmp`(12,269 B)、`sec0_exif_riff_template_3B7100.bin`(0x700 B) |
| `out/regions/` | 区域样本：`decoded_region_samples.txt`（14 个关键区域 hexdump）、`sec0_arm_code_sample.txt`、`sec0_exif_riff_template_3B7100.txt` |
| `tools/scan.py` | 主扫描器；`--input out/decoded.bin`（默认）或原始 DAT；`--prefix` 前缀输出 |
| `tools/scan_blocks.py`, `scan_sections.py` | 128KB 块分类 / 区块表构建 |
| `tools/scan_extract.py` | 只读提取尝试（解压/文件系统/资源） |
| `tools/scan_sec.py` | 4 个 FFLZ 解压段分析 |
| `tools/scan_stat.py`, `scan_deep.py`, `scan_hex.py`, `scan_probe.py` | 辅助探查脚本（统计/hexdump/深度 dump） |

> 重跑方式：`& <python> tools\scan.py --input out\decoded.bin` → 覆盖 `out/map.csv` 等主产物；`tools\scan_blocks.py` → `out/blocks128.csv`；`tools\scan_sec.py` → `out/sections_report.json`。

---

## 2. 原始 .DAT 顶层结构

```
0x000000  u32 = 6                       (表项数/版本字段)
0x000004  512 字节 ASCII-hex 字符串      两层 hex 解码 -> 128 B 表
0x000204  二进制字段区                   02 00 00 00 / 12 00 00 00 / CRC? /
                                        u32 指针 0x02FC0020、0x02FCC020、0x0309ED1C ...(指向尾部区)
0x00027C  55 55 55 55 AA AA AA AA       测试图样
0x0002A4  记录表                        (0xFFFFFFFE/-2, 0x00AFADFF) 等 8B 记录
0x000274  ------------- 载荷起点（XOR 0xFF；Lead 最终版 decoded.bin 的 base）-------------
0x000274..EOF  解码镜像 = raw[0:0x274] + (raw[0x274:] ^ 0xFF)
```
- 尾部（最后 ≥0x1000 B）在原始文件里全 0，解码后全 0xFF（擦除），无 MD5 footer。
- 明文头长度最终由 Lead 定为 `0x274`，与容器 128KB 网格偏移一致（见 §4）；早期 `0x378` 版本差 `0x104` 字节，不影响本报告 offset。

---

## 3. 解码镜像主区域表（decoded.bin，按 offset 排序）

> 列含义：`start..end`（end 不含）、size、4KB 熵概览、类型猜测、证据。区块逐块明细见 `out/blocks128.csv`。
> `0xFF`=解码后擦除/空块（原文件 0x00 区），`0x00`=解码后填充（原文件 0xFF 区）。

| start | end | size (hex / B) | 熵 | 类型猜测 | 证据 |
|---|---|---|---|---|---|
| `0x00000000` | `0x00000378` | `0x378` (888) | 2.6 | **明文容器头** | `u32@0=6`；0x04–0x203 双层 ASCII-hex 表；0x204 起二进制字段；0x27C `55555555/AAAAAAAA` |
| `0x00000378` | `0x00000A78` | `0x700` (1,792) | 0 | 0x00 填充 | 解码后全 0x00 |
| `0x00000A78` | `0x00007E94` | `0x741C` (29,724) | 2–4 | 低熵代码/数据混合 | 0xA78 起 **Thumb-2 代码**（Lead 确认）；0x1000–0x2000 有 ARM condE 特征 |
| `0x00007E94` | `0x00020274` | `0x183E0` (99,296) | 0 | 0xFF 擦除块 | 99.2 KB 全 0xFF（原文件 0x00） |
| `0x00020274` | `0x0002CAC5` | `0xC851` (51,281) | 5.4–5.9 | **ARM32 启动/异常处理代码** | `18 F0 9F E5` = `LDR pc,[pc,#24]` ×8 → `FE FF FF EA` = `B .`，随后异常 handler；capstone ARM 覆盖率 100%（Lead 验证） |
| `0x0002CAC5` | `0x00040274` | `0x137AF` (79,791) | 0 | 0x00 填充 | 解码后全 0x00 |
| `0x00040274` | `0x00060274` | `0x20000` (131,072) | 0.04 | 0xFF 擦除块 | 1 个空块 |
| `0x00060274` | `0x0007B316` | `0x1B0A2` (110,754) | 5.4–6.0 | **ARM32 代码 + RTOS/字符串** | 0x60294 起 ARM 代码（LDR/BIC 序列）；0x7B190 `ThreadX SMP/Cortex-A7/GNU Version G5.6.2.5.0`、`syslog Ver 2.3`、`Copyright (c) 1996-2015 Express Logic`、地区/语言代码表 |
| `0x0007B316` | `0x00080274` | `0x4F5E` (20,318) | 0 | 0x00 填充 | — |
| `0x00080274` | `0x000C0274` | `0x40000` (262,144) | 0.04 | 0xFF 擦除块 | 2 个空块 |
| `0x000C0274` | `0x00132274` | `0x72000` (466,944) | 3.3–4.3 | **明文配置/描述/字符串区** | `FUJIFILM`、`X-T4`、`FUJIDSCFBLOG_DSF`、`lenscom`/`biscom` 任务名、`ERR_SYSTEM_HALT`、UI 错误串；含递增/递减 LUT 表（ASCII 序列） |
| `0x00132274` | `0x00140274` | `0xE000` (57,344) | 0 | 0xFF 擦除块 | — |
| `0x00140274` | `0x001404B5` | `0x241` (577) | 2.5 | 指针表（u32） | 表项 → `0x00E2xxxx`（运行时地址，对应 sec0 域） |
| `0x001404B5` | `0x00160274` | `0x1FDBF` (130,495) | 0 | 0x00 填充 | — |
| `0x00160274` | `0x001842C1` | `0x2404D` (147,533) | 3.5–6.1 | **ARM 模块 A（入口指针表 + 代码 + 字符串）** | 起始 u32 指针表（`0x00E32704`,`0x00E42398`…）；condE 0.83–0.89，分支密度高（bl 41–78/窗口）；`%s,0x%x,%d`、`A:\DCIM\100_FUJI\`、`FinePix`；0x183xxx 递增/递减 u16 表 |
| `0x001842C1` | `0x001A0274` | `0x1BFB3` (114,611) | 0 | 0x00 填充 | — |
| `0x001A0274` | `0x001E0274` | `0x40000` (262,144) | 0.04 | 0xFF 擦除块 | — |
| `0x001E0274` | `0x002042C1` | `0x2404D` (147,533) | 3.5–6.1 | **ARM 模块 B = 模块 A 的副本（另一加载地址）** | 与 A 仅 **1863/262,144 B 不同（0.71%）**；差异为 u32 入口指针整体 **+0x100000**（`0x00E32704 → 0x00F32704`），其余为少量代码常量；推测同一模块的两份（A/B bank 或两个链接基址） |
| `0x002042C1` | `0x00220274` | `0x1BFB3` (114,611) | 0 | 0x00 填充 | — |
| `0x00220274` | `0x00260274` | `0x40000` (262,144) | 0.04 | 0xFF 擦除块 | — |
| `0x00260274` | `0x005AA4FD` | `0x34A289` (3,449,481) | 6.4–6.8 | **FFLZ 压缩段 sec0（打包）** | 20B 头：unpacked 7,420,408 / packed 3,449,482 / pages 211 / page 0x4000 / tag 4；解压后 = ARM32 主程序 + Exif/XMP 资源（§5） |
| `0x005AA4FD` | `0x005C0274` | `0x15D77` (89,463) | 0 | 0x00 填充 | — |
| `0x005C0274` | `0x00AC3843` | `0x5035CF` (5,256,655) | 6.4–7.0 | **FFLZ 压缩段 sec1（打包）** | unpacked 9,437,184 / pages 321；解压后 = 系统/程序库（libc/POSIX/getopt/errno） |
| `0x00AC3843` | `0x00AE0274` | `0x1CA31` (117,297) | 0 | 0x00 填充 | — |
| `0x00AE0274` | `0x00F4B2FD` | `0x46B089` (4,632,713) | 6.4–6.7 | **FFLZ 压缩段 sec2（打包）** | unpacked 10,240,000 / pages 283；解压后 = 网络栈 + 设置逻辑 |
| `0x00F4B2FD` | `0x00F60274` | `0x14F77` (85,879) | 0 | 0x00 填充 | — |
| `0x00F60274` | `0x01820274` | `0x8C0000` (9,175,040) | 0 | **0xFF 擦除区（大）** | 70 个 128KB 空块；原文件对应 8.75 MB 全 0（推测：flash 预留/未使用区块） |
| `0x01820274` | `0x01840274` | `0x20000` (131,072) | 2.0 | 明文资源（TEXT/RES） | 110 条 ≥12 可打印串；含 `0xFFFFFFFE`(-2) + `0x00ADxxxx` 指针的 8B 记录（疑似补丁/重定位表） |
| `0x01840274` | `0x01860274` | `0x20000` (131,072) | 0 | 0xFF 擦除块 | — |
| `0x01860274` | `0x019D6954` | `0x1766E0` (1,533,664) | **7.3–7.8** | **高熵未识别区** | 无 FFLZ 头；gzip/xz/lzma/zlib/bzip2/zstd 全部解压失败；无文件系统 magic；字节位平面近随机 → 疑似加密或私有压缩资源 |
| `0x019D6954` | `0x01A00274` | `0x29920` (170,272) | 0 | 0xFF 擦除块 | — |
| `0x01A00274` | `0x01D28803` | `0x32858F` (3,310,991) | 6.4–6.8 | **FFLZ 压缩段 sec3（打包）** | unpacked 6,446,348 / pages 203；解压后 = u16 表 / 字体或度量资源（**非代码**，condE=0.003） |
| `0x01D28803` | `0x01D40274` | `0x17A71` (96,881) | 0 | 0x00 填充 | — |
| `0x01D40274` | `0x01DA0274` | `0x60000` (393,216) | 0 | 0xFF 擦除块 | — |
| `0x01DA0274` | `0x01DE0274` | `0x40000` (262,144) | 0–2.5 | 小块头 + 0x00 填充 | 0x1DA0274 起 0x49B 字节数据（内容近似空/小表），随后 0x00 填充 |
| `0x01DE0274` | `0x028B77D3` | `0xAD755F` (11,367,775) | 3.4–6.9 | **多语言 UI 字符串资源（UTF-16LE）** | UTF-16 比 ~0.49；日文假名 0x30xx / 西里尔 0x04xx / ASCII；每 0x40000 有 0xFF 擦除间隔；块内 150–200 条字符串/128KB；含 UTF-16 "FUJIFILM" 与多语言菜单文本 |
| `0x028B77D3` | `0x028E0274` | `0x28AA1` (166,561) | 0 | 0xFF 擦除块 | — |
| `0x028E0274` | `0x02BD3486` | `0x2F3212` (3,093,010) | ~5.8 | **16-bit 数据表 / 资源（非代码）** | condE≈0.003（无 ARM 代码特征）；u16 值规律、0x00 大量；字符串密度高但为 16-bit 结构（`GVFF` 等）→ 疑似字体/度量/查找表 |
| `0x02BD3486` | `0x02C40274` | `0x6CDEE` (445,934) | 0 | 0xFF 擦除块 | — |
| `0x02C40274` | `0x02D40274` | `0x100000` (1,048,576) | 4.4–6.8 | **HEVC/H.265 编码器资源/字符串** | `H.265 MP Encoder`、`HEVCENC`、`Long GOP`；内部多段 0x00 填充 |
| `0x02D40274` | `0x02FC0274` | `0x280000` (2,621,440) | 0 | **0xFF 擦除区（大）** | 20 个空块 |
| `0x02FC0274` | `0x030E71C8` | `0x126F54` (1,208,148) | 0–6.7 | **尾部程序/数据区** | 头 u32 = `0x02FC0000`（自指文件偏移）/`0x20`；u16 偏移表；**Thumb-2 代码**（0x2FE3000 起 `b0 bd 4f f0 07 00` = `pop {r4,r5,r7,pc}; mov.w r0,#7`）；`BISLX45`、`lenscom fail` 串；**0x30A0000 与 0x30D0000 各有完全相同的 0x49A2 B 重复数据**（分别位于尾部 region R4/R5 的 +0xE38 处，Lead 区号）；其余 0x00/0xFF 填充 |

合计行宽检验：表中 size 求和 = 51,278,280 B（=文件大小，已核对）。

---

## 4. 0x20000 网格统计证据（为什么块起点 = 0x20000k + 0x274）

| 证据 | 数据 |
|---|---|
| 4 个 FFLZ 段头偏移 | `0x260274`(k=19)、`0x5C0274`(k=46)、`0xAE0274`(k=87)、`0x1A00274`(k=208) —— **4/4 均 ≡ 0x274 (mod 0x20000)** |
| 由 `blocks128.csv` 合并出的 14 个区段起点 | **14/14 均 ≡ 0x274 (mod 0x20000)** |
| 填充段端点（`out/fills.csv`，decoded） | 236 段中 **28 段 end ≡ 0x274 (mod 0x20000)**；≥32KB 的 73 段中 **24 段 end 对齐**；8 段 start 对齐（正是「擦除块结束→数据块开始」处） |
| Lead 列出的明文区起点 | `0x20274/0x60274/0xC0274/0x140274/0x1E0274/0x1820274/0x1860274/0x1DA0274/0x2FC0274` 全部 ≡ 0x274 |
| 文件尺寸分解 | `0x30E71C8 = 0x274 + 391 × 0x20000 + 0x6F54` → 392 个 128KB 块（最后一块 0x6F54 B 不满） |
| 填充语义 | 原始文件 0x00 区 → 解码 0xFF（**擦除**）；原始 0xFF 区 → 解码 0x00（**填充**）。与 128KB 块尾部对齐（FFLZ 以 16KB 页喂给硬件解压器，也不跨块） |

**结论（已由 Lead 定论：base=0x274）**：载荷 = `0x274` 字节头 + 按 128KB 块组织的镜像；块内数据之后用 0x00 补满，未用块整块 0xFF 擦除。

---

## 5. 4 个 FFLZ 解压段的内容分类（Lead 已解出，本报告定量分析）

> 解压器：`tools/decode_fflz.py`；产物 `out/sections/sec0..3.bin`；头结构 20B：
> `+0 unpacked u32 / +4 packed u32 / +8 pages u32 / +12 page_size(=0x4000) / +16 tag(=4)`。
> 解压后 magic 计数为**整段字节匹配**，仅 RIFF/Exif/xpacket/FUJIFILM 等有意义的命中单列；普通 zlib/sfnt 短 pattern 计数多为代码/数据噪声。

| 段 | 解压 B | 熵 | 0xFF% | 0x00% | 可打印比 | UTF16比 | **ARM condE** | capstone ARM/Thumb (中位) | ≥8B 可打印串 | 资源 magic（有意义的） |
|---|---|---|---|---|---|---|---|---|---|---|
| sec0 | 7,420,408 | 6.03 | 4.6 | 24.8 | 0.26 | 0.03 | **0.463** | 1.00 / 0.14 | 4000+ | RIFF×2, WAVE×2, fmt×2, Exif×2, xpacket×3, FUJIFILM×5, LX45×77 |
| sec1 | 9,437,184 | 6.30 | 2.6 | 18.3 | 0.23 | 0.03 | **0.656** | 1.00 / 0.06 | 4000+ | POSIXLY_CORRECT×1, xml×2, FUJIFILM×5 |
| sec2 | 10,240,000 | 5.55 | 1.8 | 32.7 | 0.20 | 0.04 | **0.476** | 1.00 / 0.10 | 4000+ | MAC ADDRESS×2, IP ADDRESS×2, STA TIME×1, Exif×1, FUJIFILM×6 |
| sec3 | 6,446,348 | 5.62 | 3.2 | 32.5 | 0.25 | 0.01 | **0.003** | 0.14 / 0.22 | ~100 | 无（仅 sfnt1/zlib 短 pattern 噪声） |

> capstone「覆盖率」对 ARM 会因数据/零填充被高估（几乎全部 32-bit 模式在 ARM 下都是合法指令），因此**判断代码主用 condE（4 字节对齐字高半字节==0xE 的比例）与分支密度**：真实 ARM 代码 condE≈0.7–0.95；纯数据/UTF-16 <0.1。sec0/1/2 有明显 ARM 代码，sec3 不是代码。
> Lead 复核的 arm 中位覆盖率：**sec0=0.997 / sec1=1.0 / sec2=1.0 / sec3=0.145（thumb 0.216）**，与本报告采样结果（1.00/1.00/1.00/0.14，thumb 0.22）一致。

### 5.1 sec0（0x260274，解压 7,420,408 B）— ARM32 主程序 + 元数据模板 + UI 字符串
- 开头 0x20 字节小头，0x20 起即 ARM 代码：`00 50 2d e9`(`push {r12,lr}`)、`0f 50 2d e9`、`0d 00 a0 e1`、`b1 bd 09 eb`(BL)、`1e ff 2f e1`(`bx lr`)（样本见 `out/regions/sec0_arm_code_sample.txt`）。
- **真实可提取资源**（已落盘）：
  - XMP 包 A：`0x552B23`，12,236 B，可打印比 1.00，以 `xpacket begin='\xef\xbb\xbf' id='W5M0MpCehiHzreSzNTczkc9d'?> <x:xmpmeta ...>` 开头 → `out/extracted/xmp_sec0_A.xmp`；
  - XMP 包 B：`0x555B02`，12,269 B → `out/extracted/xmp_sec0_B.xmp`；
  - EXIF/RIFF 元数据模板：`0x3B7100`（`RIFF WAVE fmt fact LIST INFO ICRD ICMT ICOP Exif everetime core ... FUJIFILM <?xpacket begin=`）→ `out/extracted/sec0_exif_riff_template_3B7100.bin`（注意：这是**元数据模板**，不是音频/图片）。
- 20 条字符串样本（`out/sections_strings.txt`）：
  ```
  0x3B7128 RIFFWAVEfmt factLISTINFOICRDICMTICOPexifeveretimecoremdlemntdatafree0100
  0x3B719E xpacket begin=            0x3B71AE xpacket end=
  0x3B71F4 lenscomtsk fail           0x3B7244 biscomtsk fail
  0x3B8410 uicom_svc_composite_recinput_focusmode(1)
  0x3B8494 uicom_svc_composite_setp_through_prev(1)
  0x3B8518 uicom_svc_get_DispSetp(1)
  0x3B8534 uicom_svc_setp2dsckeyword_continue_setp()
  0x3B8560 uicom_svc_setp2setpsize_pixel()
  0x3B8580 uicom_svc_setp_backup2recinput_through_exp_prev(1)
  0x3B85E8 uicom_svc_setp_iso2setpsetmax()
  0x3B8608 uicom_svc_setpsetmax2setp_iso()
  0x3B8708 uicom_svc_get_recinput_recpreferopt()
  0x3E7238 UI:AUTOSET:ui_setp_rec_mode_func_option_val Error
  0x3E726C UI:AUTOSET:ui_shutter_type_val Error
  0x3E7294 UI:AUTOSET:ui_floghlg_val Error
  0x3E72B4 UI:AUTOSET:ui_hs_movie_mode_val Error
  0x3E72DC UI:AUTOSET:ui_hs_movie_fps_rec_val Error
  ```
- 判断：**主程序/应用代码段**。含设置项（AE/ISO/快门/F-Log/HS 录像）UI 服务函数名，与「aefix（AE 修复）」主题相关，是后续逆向的第一优先级。

### 5.2 sec1（0x5C0274，解压 9,437,184 B）— 系统/程序库（ARM 代码密度最高）
- condE 0.656（四段最高），字符串集中在 `0x6C7xxx`：C 库/POSIX 特征：
  ```
  0x6C7104 Infinity               0x6C7114 POSIXLY_CORRECT
  0x6C7132 is ambiguous (could be  0x6C7162 invalid option --
  0x6C717E argument required for option
  0x6C72D8 Not owner               0x6C72E4 No such file or directory
  0x6C7300 No such process         0x6C7310 Interrupted system call
  0x6C7328 I/O error               0x6C7334 No such device or address
  0x6C7350 Arg list too long       0x6C7364 Exec format error
  0x6C7378 Socket already connected 0x6C7394 Bad file number
  0x6C73A4 No children             0x6C73B0 Destination address required
  0x6C73D0 No more processes       0x6C73E4 Not enough space
  0x6C73F8 Permission denied       0x6C740C Bad address
  0x6C7418 Device or resource busy 0x6C7430 File exists
  ```
- 判断：**C 运行时库 + 系统/应用代码**（getopt/errno/POSIX 语义），是定位主程序入口与 RTOS 服务的高价值段。

### 5.3 sec2（0xAE0274，解压 10,240,000 B）— 网络/Wi-Fi 协议栈 + 设置逻辑
- 字符串（`0x3Exxxx` 区）：
  ```
  0x3E417C MAC ADDRESS:            0x3E419E AA:AA:AA:AA:AA:AA
  0x3E41C0 IP ADDRESS:             0x3EDD54 API_INFO:
  0x3EDD78 FncAdr:0x              0x3EDD84 KEY_LOG:(
  0x3EDD90 )      STA TIME         0x3EDDB0 GET_KEY_FAILED
  0x3EDDC0 STM Transition Log:(    0x3EDDD8 Software Version:
  0x3EDDEC EEP Adjust Date(MM/dd): 0x3EDE04 Script Version:
  0x3EDE41 F%s (%d)(MAX=%d)        0x3EDF1C SCR_ID too long..
  0x3EDF30 MENU_KIND too long..    0x3EDF48 SETP too long..
  0x3EDF64 COM_GETVAL(%s)=         0x3EDF8C ltUiLib.dispId=
  0x3EDFC4 uwTargetPos =           0x3EE060 Hello world
  0x3EFF70 shiro1,30,24            0x3F00F4 Long GOP
  0x3F015C GHz (W52. W53) : Indoor Use Only
  0x3F0188 IS 13252(Part 1)/
  ```
- 判断：**网络/Wi-Fi 协议栈 + 相机设置/状态机逻辑**（MAC/IP、STA 关联、密钥日志、STM 状态机、EEP 调整日期、法规字符串）。

### 5.4 sec3（0x1A00274，解压 6,446,348 B）— 非代码数据表（疑似字体/度量/资源表）
- 开头即 u16 表：`0x0014,0x0018,0x001E,0x0024,0x0030,0x0000,0x0198,0x001E,...`（重复结构，像 (x,y,size,flag) 度量表）。
- condE = 0.003 → **不是 ARM 代码**；u16 零占比 20.8%，最大值 0xFFFF，均值 ~20,499。
- 可打印串极少（仅约 100 条 ≥8 B，且多为 `GVFF`/`G V F F` 类 16-bit 数据伪串）：
  ```
  0x000D0F1A yCGVFF I     0x000EE37B DGVFFi6b    0x000FDC97 AGVFFIKb
  0x001320AF C gRC i0C gRC 0x0013C743 BGVFFi6b   0x00143BD7 BGVFFIKb
  0x001AB3F3 CGVFFIKb    0x0020033D a(CGVFF6Nd 0x002618C0 GVFFPr64
  0x00269242 pAGVFF G    0x002CCDFF AGVFF6Nd   0x002FF841 pZAGVFFF
  0x00332A67 AGVFFi6b    0x003332E6 RBGVFF6f   0x003D4B29 OKBGVFF6Nd
  0x003D62AA IBGVFF6Nd   0x004D98CF DGVFF f8
  ```
- 判断：**16-bit 表/字体度量/资源表**（非代码，无标准字体头）。是「sec3 到底装什么」的待办（字体位图？菜单布局？校准表？）。

> **关于 sec0/1/2 中「JPEG 105 / OTTO 79 / zlib 数百」等 magic 计数**：全部为**伪命中**。
> - JPEG（`FF D8 FF`）在 sec0/1/2 共 124 处候选，PIL 全部无法解码 → 不是真 JPEG；
> - OTTO 79 处均为 UI 名称的子串（如 `BOTTOMMOST`、`OTTOM_...` 等 "BOTTOM..." 词），不是字体；
> - `0x00 0x01 0x00 0x00`(sfnt) / `0x78 0x01`(zlib) 等短 pattern 命中数量巨大（数千），属代码/数据噪声。

---

## 6. ARM32 / Thumb 代码区域清单（解码镜像 + 解压段）

| 区域 | 模式 | 证据 |
|---|---|---|
| `0x00020274..0x0002CAC5` | **ARM32** | 8× `LDR pc,[pc,#24]`（`18 F0 9F E5`）+ `FE FF FF EA`(B .) + 异常 handler；capstone ARM 覆盖 100% |
| `0x00060274..0x0007B316` | **ARM32** | 0x60294 起 `LDR/BIC/…`；condE 0.85+；0x7B190 ThreadX 字符串 |
| `0x0000A78..`（小段） | **Thumb-2** | Lead 确认 0xA78 起规整 Thumb-2（`F10E 01D3`/`EB00000C` 等）；0x1000–0x2000 窗口另有 ARM condE 特征 |
| `0x00160274..0x001842C1`（模块 A） | **ARM32** | condE 0.70–0.89/窗口；`bl` 41–78/窗口；入口 u32 指针表 |
| `0x001E0274..0x002042C1`（模块 B） | **ARM32** | 与 A 同构，0.71% 差异，指针 +0x100000（A/B 两份，另一加载地址） |
| `0x00260274` 起（FFLZ sec0 packed 内） | 压缩流 | 头后 0x260288 起是 token 流（字面量复制使局部出现 ARM 字节，不能直接反汇编；**应分析解压后的 sec0.bin**） |
| `0x02FE3000..0x03083000`（尾部多段） | **Thumb-2** | `b0 bd 4f f0 07 00` = `pop {r4,r5,r7,pc}; mov.w r0,#7`；窗口 0x2FE3000/0x2FE5000/0x2FEA000/0x2FF1000/0x3062000/0x306E000/0x307A000/0x3082000… |
| sec0/sec1/sec2（解压后） | **ARM32** | condE 0.463 / 0.656 / 0.476；ARM 指令流（push/lsl/bl/bx）与函数序言可见 |

> 说明：扫描器对 `0xE9xxxxxx` 分支/`0xEA` 字面量池的自动检测（`arm32:condE=…,b=…,bl=…,ldm=…`）已写入 `out/map.csv` 的 hints 列；真实 ARM 代码窗口集中在上述区域。

---

## 7. magic / 压缩 / 文件系统 / 资源提取尝试结果汇总

> 全部尝试记录在 `out/extract_attempts.csv`（204 条）。在 **decoded.bin** 与 **4 个解压段**上：
> - **标准压缩/归档**：gzip / xz / lzma-alone / zlib / bzip2 / zstd / zip / tar / cpio —— **0 命中**（私有 FFLZ 是唯一压缩格式，已由 Lead 解出）。
> - **文件系统**：squashfs / cramfs / jffs2 / ubifs / ext2-4 / FAT —— **0 命中**（FAT 的 `FAT12/16/32` 文本与 `MSDOS` 串只在明文配置区作字符串出现，不是引导扇区）。
> - **可执行/固件容器**：ELF / PE / uImage / FDT / Android boot —— **0 命中**（主程序是裸 ARM32 镜像，无 ELF 头）。
> - **图像/音频/字体/数据库/XML**：PNG / BMP / TIFF / SQLite / TTF/OTF/TTC —— **0 命中**；JPEG 候选 124 处 **PIL 全部解码失败**（伪命中）；RIFF 仅 sec0 的 Exif 元数据模板（非音频）；XMP 为真实资源（已提取 2 个 12KB 包）。
> - **高熵块（0x1860274，1.53 MB）**：5 个偏移 × 6 种 codec 全部失败 → 非标准压缩，疑似加密/私有格式。
> - **成功解出的东西**：`out/extracted/xmp_sec0_A.xmp`、`xmp_sec0_B.xmp`、`sec0_exif_riff_template_3B7100.bin`（见 §5.1）。

### 7.1 对早期「取反域噪声」命中的重新解释（Lead 要求）
1. **`xmp` 命中 @ `0x468E1B/0x468E1D/0x4D59AD/0x4D59AF/0x4D60BE/0x4D67F2`**：这些偏移落在 **FFLZ sec0 的打包流内部**（`0x260274..0x5AA4FD`）。FFLZ 的 token 流含「字面量 run」，会把原始字节原样搬入压缩流，因此出现 `RIFF WAVEfmt`、`FUJIFILM`、`xpacket begin=` 等字符串片段。**它们不是独立的 RIFF/XMP 文件**；解压后 sec0 中才有真正的 XMP 包（0x552B23 / 0x555B02）与 Exif 模板（0x3B7100）。
2. **`cortexm_vectortable` 命中（0xD2C18 / 0x2C78198 / 0x300B198 等）**：解码镜像是 **Cortex-A7**（ThreadX SMP/Cortex-A7），不存在 Cortex-M 向量表；该检测器只看「前 4B 像 SRAM 栈指针 + 后 16 字多为奇数 handler」，在 ARM 代码/16-bit 数据中极易误报 → **判为噪声/伪命中**（原始 .DAT 上的同类命中更是取反域噪声）。真正有意义的向量表只有 `0x20274` 的 **ARM32 异常向量表**。
3. **`lzma_alone`/`font_ttf`/`fat` 等 46/37/6 条命中（原始文件扫描）**：均来自取反域/短 pattern，结构校验不过；decoded 镜像上结构性命中仅剩 `xml`(7，其中 6 条在 FFLZ 打包流内) + `arm_vectortable`(1) + `cortexm` 伪命中。

---

## 8. 熵区段汇总（decoded.bin，4KB 窗口）

- 全文件：mean **3.49** / min 0.00 / max **7.94** bits/byte；12520 个 4KB 窗口。
- 粗分类（按 4KB 窗口）：**低熵 (<3.5)** ≈ **23.46 MB**；**中熵 (3.5–7.0)** ≈ **20.58 MB**；**高熵 (≥7.0)** ≈ **3.85 MB**。
- 4KB 窗口标签计数（`out/regions.csv`）：fill 4700、high-ent 1058、mid-high 3759、mid 2066、low 801、code-arm 106、code-thumb 25、text 5。
- 主要低熵带：`0x000000-0x00260274`（头/代码/填充/小表混合）、`0x00F60274-0x01820274`（8.75 MB 擦除）、`0x02D40274-0x02FC0274`（2.5 MB 擦除）、`0x01D29000-0x01DDC000` 等。
- 主要中熵带：`0x00260000-0x0046B000`（sec0 打包）、`0x005C0000-0x009BD000`（sec1 打包）、`0x00AE0000-0x00CDE000`（sec2 打包）、`0x01A00000-0x01D29000`（sec3 打包）、`0x01DE0274-0x028B77D3`（UTF-16 UI 文本，熵 ~4）。
- 主要高熵带：**`0x01860274-0x019D6954`（1.53 MB，7.3–7.8）**；其余高熵 4KB 窗口散布在 FFLZ 打包流内（压缩流局部 >7.0）。
- 填充：`0xFF` 17,850,506 B（17.85 MB，擦除）+ `0x00` 2,027,638 B（2.03 MB，填充）= 19.88 MB（38.8%），共 236 段（≥256 B）。
- 高频重复 3/4 字节模式（`out/repeats.csv`，decoded 镜像）：`FF FF FF`×17,871,931 / `00 00 00`×2,728,646（填充主导）；`00 64 00`/`64 00 64`×287,106/139,450（UTF-16 文本域中的 `d`）、`8C 00 64 00`、`8B 00 64 00` 等——均落在 UTF-16 UI 文本/表区，**不是压缩特征**。

---

## 9. 值得深入的前 10 个区域（含理由）

1. **`out/sections/sec0.bin`（源 0x260274；解压 7.42 MB）** — ARM32 主程序 + AE/ISO/快门/F-Log UI 服务函数名 + 真实 XMP/Exif 模板。是「aefix」主题最相关、信息最丰富的段。**理由**：唯一同时包含代码、错误串、元数据资源的段。
2. **`out/sections/sec1.bin`（源 0x5C0274；解压 9.44 MB）** — ARM 代码密度最高（condE 0.656），含 libc/POSIX/getopt/errno。**理由**：可定位主程序入口、RTOS 服务与系统库边界。
3. **`out/sections/sec2.bin`（源 0xAE0274；解压 10.24 MB）** — 网络/Wi-Fi 协议栈 + 相机状态机/设置逻辑（MAC/IP/STA/KEY_LOG/STM 日志）。**理由**：独立子系统，结构清晰，可利用字符串定位协议实现。
4. **`out/sections/sec3.bin`（源 0x1A00274；解压 6.45 MB）** — 非代码，u16 表开头，疑似字体/度量/资源表。**理由**：目前唯一「内容性质未定」的解压段，解析后可能得到字体/glyph 或 UI 布局表。
5. **`0x01860274-0x019D6954`（1.53 MB，熵 7.3–7.8）** — 唯一大面积未识别高熵块；无 FFLZ/标准头。**理由**：若为私有加密/压缩资源，可能是图像/校准数据；值得做 codec 指纹（熵谱、位平面、首部 20B 变体扫描）。
6. **`0x01DE0274-0x028B77D3`（11.37 MB UTF-16LE UI 文本）** — 多语言菜单/消息资源 + 索引表（每 0x40000 一块，日文/西里尔/拉丁）。**理由**：量大、结构周期性强，可提取语言表/消息 ID（与 sec0 的 `MSG_*`/`uicom_*` 交叉引用）。
7. **`0x028E0274-0x02BD3486`（2.32 MB 16-bit 表）** — 非代码，u16 规律数据。**理由**：疑似字体度量/查找表/校准表；若确认是字体，可还原字形/字号体系。
8. **`0x02C40274-0x02D40274`（1.0 MB）** — HEVC/H.265 编码器资源/字符串（`H.265 MP Encoder`、`Long GOP`）。**理由**：视频编码库边界，便于识别第三方 codec 与授权字符串。
9. **`0x02FC0274-0x030E71C8`（1.21 MB 尾部）** — 自指头 `0x02FC0000` + u16 偏移表 + Thumb-2 代码 + `0x30A0000/0x30D0000` 双份 0x49A2 B 数据。**理由**：疑似「更新器/引导修补程序」，且双份数据暗示 A/B 校验或补丁结构，**可能与 aefix 修改机制直接相关**。
10. **模块 A/B 对（`0x160274` vs `0x1E0274`，各 0x2404D B）** — 同一 ARM 模块两份，仅 0.71% 差异（入口指针 +0x100000）。**理由**：天然的「补丁/版本差异」样本，可用于理解 A/B bank 或链接基址差异；若与 aefix 有关可直接定位改动点。

> 次优先级：`0x00020274` 启动向量表（boot 流入口）；`0x000C0274-0x00132274` 配置/描述区（`X-T4`/`FUJIDSCFBLOG_DSF`/`LX45` 机型标识）；`0x01820274` 疑似补丁/重定位表（-2 + 0x00ADxxxx 记录）。

---

## 10. 存疑 / 待办（明确标注「推测」）

1. **明文头长度**：已由 Lead 定论为 **0x274**（decoded.bin 最终版 base=0x274），与容器 128KB 网格一致；本报告区域表基于该版本，早期 0x378 版本差异仅在 `0x274..0x378`。
2. `0x01860274-0x019D6954` 高熵块的性质：**推测**为加密或私有压缩资源，尚无 codec 指纹。
3. `0x028E0274-0x02BD3486` 的 16-bit 表：**推测**字体/度量/查找表，未证实。
4. `0x160274/0x1E0274` 模块 A/B 与尾部 `0x30A0000/0x30D0000` 双份数据：**推测** A/B bank、回滚副本或补丁副本，语义未定。
5. 8.75 MB + 2.5 MB 两个大 `0xFF` 擦除区：**推测**为 flash 预留/未用块（映射到 128KB 空块）。
6. FFLZ 头 `tag=4` 的语义、页内 token 规则由 Lead 的 `tools/decode_fflz.py` 验证（本报告按已解出结果使用）。
7. `sec0/1/2` 的 capstone ARM 覆盖率会因数据/零填充饱和（见 §5 注释），代码边界应以 condE + 分支密度 + 实际反汇编进一步确认。

---

## 11. 相关文件
- Lead 关键发现：`99-lead-findings.md`；环境约定：`00-ENV.md`；公开资料：`03-prior-art.md`
- 容器/头部解析：`01-container.md`（container-analyst）
- FFLZ 解压器与产物：`tools/decode_fflz.py`、`out/decoded.bin`、`out/sections/sections.json`、`out/sections/sec0..3.bin`
