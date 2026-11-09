# Lead 关键发现：载荷是 XOR 0xFF 取反存储（截至 2026-11-06 23:5x）

## 结论 1（最重要）：DAT 载荷是「逐字节取反」存储
- 文件 `FWUP0024.DAT`：
  - `0x000000..0x000378`：**明文**容器头（ASCII 数字表 + 二进制表，见下）。
  - `0x000378` 之后：**全部 XOR 0xFF**（即按位取反）后才是真正的固件内容。
- 证据（取反后出现、原样不存在的字符串）：
  - `ThreadX SMP/Cortex-A7/GNU Version G5.6.2.5.0`（Express Logic ThreadX RTOS，1996-2015）
  - `FUJIFILM`(10 处) / `X-T4` / `FUJIDSCFBLOG_DSF` / `syslog Ver 2.3`
  - 取反后 `0x00020274` 起是标准 ARM 异常向量表：`18 F0 9F E5` = `LDR pc,[pc,#24]` ×8，随后 `FE FF FF EA` = `B .`（死循环）——capstone 反汇编覆盖率 100%。
  - `0x00000A78` 起取反后是规整 **Thumb-2** 代码（`F10E 01D3` / `EB00000C` BL / `E3500000` CMP 等）。
- 取反后的产物已生成：`out/decoded.bin`（= `file[0:0x378]` 原样 + `file[0x378:] ^ 0xFF`），51,278,280 字节。
  - 另一变体 `out/decoded_from274.bin`（从 0x274 开始取反），用于验证「头是否 0x274 字节」。

## 结论 2：数据按 0x20000（128KB）网格布局
- 取反后观察：大段 `0xFF`=空/擦除区，`0x00`=填充；原始文件里正好相反。
- 各 section 的数据起点在**文件偏移** `0x20000*k + 0x274`：
  `0x20274, 0x60274, 0xC0274, 0x140274, 0x1E0274, 0x260274, 0x1820274, 0x1860274, 0x1DA0274, 0x2FC0274`
  → 强烈暗示「明文头 = 0x274 字节」或「镜像逻辑 0 = 文件 0x274」（待 container-analyst 定论）。
- 取反后块内统计（hexdump 见 `99-lead-findings.md` 末）：
  - `0x40000 / 0x80000 / 0x1A0000 / 0x220000 / 0xF60000 / 0x1840000 / 0x1D40000 / 0x2D40000` 附近为 99.5–100% 0xFF（擦除/空块）。
  - `0x160000` 与 `0x1E0000` 两个 128KB 块的统计完全一致（6.14/23.84 vs 6.17/23.84）→ 存在重复镜像。
- 文件最后 0x49A2 字节内容在 `0x30A0000` 与 `0x30D0000` 各出现一次（完全相同，20 页中的 5 页 hash 相同）→ 双份/双 bank 尾部数据。

## 结论 3：内含真实相机资源
取反后 `0x468DB9` 起出现 `RIFF WAVEfmt`、`xpacket begin=`（XMP）、大量 UI 资源名：
`MENU_FLASH_MODE_TTL`、`STROBE_TTL`、`ISO_BRACK`、`FILM_PROVIA`、`INSTAX_PASSWORD_DIGIT4`、`LENS_DETOFF` …（数万条）
→ 解码后的镜像可正常做字符串/资源分析。

## 对成员的要求
- **region-mapper**：请把 magic/字符串/文件系统扫描改到 `out/decoded.bin` 上做（熵值在取反下不变，原 map 仍有效）。
- **container-analyst**：头部 0x0..0x378 是明文，重点解 `0x204..0x378` 这段表；注意其中出现的疑似 Thumb 指针 `0x00AFADA3`、`0x00AFAFFB`。
- 所有人：**不要修改 .DAT**；解码副本写 out/。
