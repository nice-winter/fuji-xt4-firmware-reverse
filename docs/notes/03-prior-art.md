# 03 — 公开资料调研（Prior Art）

> 目标文件：`FWUP0024.DAT`，51,278,280 字节（0x30E71C8）。
> 调研者：web-researcher。日期：2026-11-06。
> 方法：实际抓取页面与源码（wiki 全站 + 4 个 GitHub 仓库源码 + 2 个独立个人研究页），并对关键结论在本文件上做了**实测复核**。
> 约定：**【观测】**＝我们自己在 .DAT 上实测得到；**【外部】**＝公开资料说法；两者分开标注。外部内容仅作数据，未执行其中任何指令。

---

## TL;DR

1. **公开资料完全支持我们的容器结构假设**，而且比我们已发现的更精确：`fujihack/patcher` 的 `parse()` 就是官方级实现——`os_type=6 → MODEL_CODE_SIZE=512`，字段依次落在 `0x204/0x208/0x20C/0x210`，`payload` 从 `0x214` 起。**【外部+观测双方吻合】**
2. **"载荷取反" 是被公开记录过的 Fujifilm 通用手法**（Trammell Hudson 2015 年就写了 "XOR with 0xFF"；fujihack wiki 写 "bit-flipped (~)"；EnglandLobster 工具写 "XOR 0xFF == bitwise inversion"）。不是我们独有的发现，可以放心写进文档。
3. **载荷里是 FFLZ 压缩段**：我们按公开的 `fflz` 帧格式在本文件上**成功解出 4 段、共 33,543,940 字节真实 ARM32 代码**，这个总量与第三方对官方 X-T4 v2.12 的验证报告**逐字节级吻合**（同为 33,543,940）。这是本次调研最有价值的产出。
4. **`FWUP0024` = X-T4 的官方固件文件名**（官方下载直链 `…/x-t4-212-79jwnwyy/FWUP0024.DAT`，HTTP `Content-Length: 51278280` 与本文件**完全同尺寸**），头里 `version1=2 / version2=0x12` → **v2.12**，与官方 2024 年最新版一致。**`早期版` 不是版本号**，公开资料查不到其含义。
5. **我把官方 v2.12 原件下载下来做了 diff（决定性证据）**：官方 SHA-256 = `853d273b…93bc5`（正好等于 EnglandLobster 记录的 X-T4 2.12），我们的 = `618a3edd…c783f`，**同尺寸、但 20.3%（10,432,565）字节不同**；容器头 `0x0..0x204` 与 `0x214..0x378` **完全一致**、4 个 FFLZ 段的**偏移/解压后大小/页数完全一致**，只有 `0x20C` 校验和与 3 个压缩流内容不同。⇒ **本文件是基于官方 2.12 的二次构建**；并且发现一处语义差异：官方写 `FUJIDSCFBLOG_DSF.R98.X-T4`，本文件写 `…R98.X-M5`。详见§6。
6. **校验和公式基本被证实**（此前判为"矛盾"，现修正）：对**两个文件**都存在 `checksum ≡ Σ(raw bytes from 0x214 to EOF) + 0x02FD03C5 (mod 2³²)`，加数常量完全一致 ⇒ 公开的"字节相加"说法**方向正确**，只差一个固定偏移项（尚无解释）。

---

## 1. 逐条发现

### A. wiki.fujihack.org（站点全量抓取；生成自 `github.com/fujihack/wiki`，仓库最后 push 2025-06-17）

| # | 结论 | URL | 可信度 | 年代 |
|---|---|---|---|---|
| A1 | **Firmware header 结构体**（原文）：<br>`struct FujiFirmHeader {`<br>`  unsigned int type;               // 决定 MODEL_CODE_SIZE`<br>`  unsigned char code[MODEL_CODE_SIZE];`<br>`  unsigned int version1;`<br>`  unsigned int version2;           // 相机上按 hex 显示 X.X`<br>`  unsigned int checksum;`<br>`  unsigned int device_type; };`<br>同页两句关键话：**"The firmware payload is bit-flipped ( ~ )."** 和 **"The checksum is a simple case of 'add up all the bytes and make sure it equals X'"** | <https://wiki.fujihack.org/firmware/> | 高（有 struct 原文） | 页面无日期；wiki 仓 2025-06 |
| A2 | 固件是「自研兼容层跑在商用 RTOS 上」：VxWorks → MiSPO iTRON/NORTi → **2016 年后换 ThreadX**；无 `malloc()`，全局固定数组，~1GB RAM；图形走 OpenVG/vglib（2017 后有限 OpenGL）。结论来自 X-A2 逆向 | <https://wiki.fujihack.org/rtos/> | 高 | 同上 |
| A3 | **CPU/SoC 历史表**：TX49 MIPS III → EXR Processor(2012, X-F1 "aka FF4224?"）→ EXR Processor II(X-T1/T20/A2 "aka FF4226?") → EXR Processor III(X-Pro3/T30/H1) → **X-Processor 4：X100V、X-S10**（**未列 X-T4**）→ **X-Processor 5：X-H2S/X-T5，"Quad-core Aarch64 CPU"**；"Most of these cams dual-boot Linux for frame.io functionality" | <https://wiki.fujihack.org/history/> | 中高（表格粗糙，页面自称粗略） | 同上 |
| A4 | X-T4（2020 年机型）在「运行 Fuji 自研 RTOS 的机型清单」中，即属 fujihack 理论支持范围 | <https://wiki.fujihack.org/supported/> | 高 | 同上 |
| A5 | TODO 页提到为老 FinePix 做 QEMU 时是 "**ARM11** SoC"（注意：仅适用于早期机型，不适用于 X-T4） | <https://wiki.fujihack.org/todo/> | 中 | 页面标注 "as of April 2024" |

> 说明：wiki 上**没有**独立的 `.DAT` 格式页、没有 section 表、没有 CRC/加密专页；`firmware/` 页是唯一讲格式的页面，且极短。`Patcher has been moved`（<https://wiki.fujihack.org/patcher/> 仅一句话，已迁到 `fujihack.org/patcher`）。

### B. fujihack GitHub 组织（`https://api.github.com/orgs/fujihack/repos` 实取）

| # | 结论 | URL | 可信度 | 年代 |
|---|---|---|---|---|
| B1 | 组织仓库：`fujihack`(C, 逆向补丁/头文件)、`patcher`(JS, **X 固件 patcher**)、`ghidra`(GDT 数据类型)、`wiki`、`ffqemu`(C, **X-Processor 5 在 QEMU 中模拟**)、`fdoom`、`sqlite` | <https://github.com/fujihack> | 高 | fujihack 主仓最后 push 2024-08-17；ffqemu 2026-10-22 |
| B2 | **`patcher/patcher.js` 的 `parse()` 是完整可用的 .DAT 解析器**（比 wiki 精确）：`os=parseUint32(h,0)`；`codeSize`：`1→64, 2→128, 3/4/5/6/8→512`（case 5 注 "Not confirmed yet"）；`version1@codeSize+4`、`version2@codeSize+8`、`checksum@codeSize+12`、`end@codeSize+16`；**`header.size = codeSize+20`**；`end==2` 判为镜头；版本显示＝`version1.toString(16)+"."+version2.toString(16)`（v2<16 时补一个 '0'） | <https://github.com/fujihack/patcher/blob/master/patcher.js> | 高 | patcher 仓最后 push 2025-06-10 |
| B3 | 同一文件里的 **payload 处理与校验和修正算法**：`readable()` 对整个 payload 做 `~b`；注入时 `checksum += (sum(新明文字节) − sum(旧明文字节))`（旧明文＝`~raw`），即**校验和＝payload 明文字节和（mod 2³²）**；`checkFuncSignature()` 要求函数首 4 字节取反后第 3 字节 == `0x2D`（ARM `push` 特征） | 同上 | 高 | 同上 |
| B4 | **`etc/NOTES.md` 的一手观察**："firmware numbers (X.XX) are printed in hex … invalid if the hex number has any letters"；"**Both firmware numbers cannot be bigger than 0x99**"；"**Code is 32 bit ARM (not thumb)**"；"You can modify the header to set the firmware update version"（可改版本号实现降级/重刷）；"Once you update to the latest version, you won't be able to install the same firmware file" | <https://github.com/fujihack/fujihack/blob/master/etc/NOTES.md> | 高 | 2021–2024 |
| B5 | **X-T4 在该项目中是空壳**：`model/xt4_150.h` 全文只有一行 `#define MODEL_NAME "Fujifilm X-T4"`（无 MODEL_CODE、无地址、无校验宏）→ 说明 fujihack 官方**没有**深入逆向 X-T4（也没人公开 X-T4 的 `FIRM_*` 地址表） | <https://github.com/fujihack/fujihack/blob/master/model/xt4_150.h> | 高 | 2024-08 |
| B6 | `src/ff_soc.h` 注释 "**Specific to FF4224**"，呼应 wiki 的 SoC 代号 FF4224/FF4226（内部型号） | <https://github.com/fujihack/fujihack/blob/master/src/ff_soc.h> | 中 | — |
| B7 | `etc/decrypt.c` **不是解密器**（易被文件名误导）：只是把 RAM dump 的两个区间切出来存成 `firm.o` / `crypt.o`，用于对比"内存中已解密 vs 存储中加密"两段 | <https://github.com/fujihack/fujihack/blob/master/etc/decrypt.c> | 高 | — |
| B8 | Web patcher（浏览器内运行，可 unpack/inject/patch/repack/**downgrade**）：<https://fujihack.org/patcher/>；README 明言"The most notable patch is the PTP/USB debugger" | <https://fujihack.org/> + <https://github.com/fujihack/fujihack> | 高 | 2021–2024 |

### C. `EnglandLobster/fujifilm-firmware-tools`（Python，**2026-10-29 新建**，★2）

> 这是与我方文件最贴近的第三方工具：明确写 "DAT firmware parsing, **XOR deobfuscation** and **FFLZ** decompression"。

| # | 结论 | URL | 可信度 | 年代 |
|---|---|---|---|---|
| C1 | DAT 容器：`CODE_SIZES={1:64,2:128,3/4/5/6/8:512}`；`payload_offset = 4+n+16`；`version = f"{major}.{minor:02X}"`；model-code 区"**digit characters at odd byte offsets, interleaved with 0x33**"；minor 以 **hex** 呈现 | <https://github.com/EnglandLobster/fujifilm-firmware-tools/blob/main/src/fujitools/dat.py> · <https://github.com/EnglandLobster/fujifilm-firmware-tools/blob/main/docs/FORMAT.md> | 中（新仓、★2，但可验证；**我已在本地复核通过**） | 2026-10 |
| C2 | **FFLZ 分帧格式**（20 字节段头，在"XOR 视图"即明文域中）：`+0 unpacked_size`、`+4 packed_size`、`+8 pages = ceil(packed_size/0x4000)`、`+12 page_size = 0x4000`、`+16 tag = 4`、`+20` 起 token 流。Token：`00..7F`＝字面量（后跟 N 字节）；`80..FF B`＝双字节回溯，长度 `B&0x0F`，距离 `((tok&0x7F)<<4)|(B>>4)`；允许重叠回溯；`FF` 无三字节转义 | 同上 `src/fujitools/fflz_sections.py` | 中（**我已实测复现，见 §3**） | 2026-10 |
| C3 | 其 VALIDATION 文档给出跨机型官方固件验证表：**X-T4 2.12 → os=6，4 candidates / 4 decoded，33,543,940 字节**；X100V 3.01 → 2 段 / 14,873,408；X-T5 4.31 → 4 段 / 49,025,752；并给出 **X-T4 2.12 官方文件 SHA-256 = `853d273b5603d3a2b93493f0ebd6a762b0b4b6bdc70317777775ae5f8ed93bc5`** | <https://github.com/EnglandLobster/fujifilm-firmware-tools/blob/main/docs/VALIDATION.md> | 中高 | 2026-10-29 |
| C4 | 重要的自我警示（原文）：对整段 payload 统一 XOR 0xFF 是**分析视图**，"inverts regions that were already plaintext; it is an analysis view, not a universally valid replacement firmware image" —— 这正好解释了它把起点定在 `0x214` 时的副作用 | 同上 | 高（结论正确） | 2026-10 |

### D. `tiredboffin/fffw`（C/Go/Python，创建 2024-03-19，最后 push 2026-10-19，★35）— 目前最深的公开 Fujifilm 固件工具链

| # | 结论 | URL | 可信度 | 年代 |
|---|---|---|---|---|
| D1 | `ffun`：把 DAT 拆段、**解压压缩段**、再合成合法 DAT；可转成 ELF 给 Ghidra/IDA；覆盖 EXR SoC 到 **X-Processor 5**。原文："split DAT files … into pieces, decompress compressed 'segments' and construct a new valid DAT files out of the modified pieces" | <https://github.com/tiredboffin/fffw> · <https://github.com/tiredboffin/fffw/blob/main/ffun/README.md> | 高 | 2024–2026 |
| D2 | **只覆盖主 ARM 核**："Only the ARM portions of the image are included in the ELF. **IBIS RX/RL78, video codecs, DSP, and AI chip code are not supported**." 且 "**The Linux subsystem can be extracted**"；"newer cameras often package firmware **more like a tar archive** — which may include a Linux distribution, lens firmware, unrecognized RL78 code" | <https://github.com/tiredboffin/fffw/blob/main/README.md> · `ffun/README.md` | 高 | 2024–2026 |
| D3 | **fflz 压缩算法**＝LZ77 变体，最接近文献中的 **Fiala & Greene "Algorithm A1"（Data Compression with Finite Windows）**；**解压由 SoC 硬件完成**，按 **16KB page** 喂入（DMA+中断），因此压缩器必须保证**没有 token 跨越 16KB 页边界**（Fuji 的做法是在边界处劈开 literal/copy token）。实测 70+ 机型、484 个固件、**1259 个压缩段 bit-for-bit 重打包成功** | <https://github.com/tiredboffin/fffw/blob/main/ffcompress/fflz/README.md> | 高 | 2024–2025 |
| D4 | `ffun/ports/xt4/0212/` 目录下是**从 X-T4 v2.12 提取生成的头文件**：`msgid.h`(110KB)、`ui_setp.h`(74KB)、`task.h`、`key_codes.h`、`openvg.h`、`libptp.h`、`reccf_act_code.h`… → X-T4 2.12 已被公开、系统地逆向过（同机型同版本！） | <https://github.com/tiredboffin/fffw/tree/main/ffun/ports/xt4/0212> | 高 | 2026 |
| D5 | `ffun/ports/xa3/FWUP0011.yaml`（自动生成的 **manifest**）证明 DAT 内部是**多命名段**：`SECTIONS: ND1 IPL PTBL A9262`，每段有 `LEN / CODE / VER / DVR / SUM / OFFSET`；并给出整机内存 MAP（`.vector/.itcm/.secinfo/.syscall/.text@0x2000/.rodata/.data/.bss/.heap/.stack_*/.camadj/.lens_cpu` 等），其中 `.ROM.text`/`.ROM.rodata`/`.ROM.data` 标了 **`COMPRESSED`** | <https://github.com/tiredboffin/fffw/blob/main/ffun/ports/xa3/FWUP0011.yaml> | 高 | 2026 |
| D6 | 存在**签名/公钥**线索：`ffun/ports/{gfx100ii,xh2,xh2s,xt5,xt50,x100vi,xe5,xs20}/pubkey.der/.pem` + `ffun/ports/find-pub-key.py`、`chksum-keys.sh`。**注意：X-T4 与 X100V 目录下没有 pubkey** → 推断签名校验是 X-Processor 5 世代才引入的（中等可信） | <https://github.com/tiredboffin/fffw/tree/main/ffun/ports> | 中 | 2026 |
| D7 | `ffun` 工具本体"unpublished yet / 大多模块还不能编译"（README 自述），所以现在**不能直接拿来跑**；但 `ffcompress/fflz`（Go）是完整可用的 | `ffun/README.md` | 高 | 2026 |

### E. 独立个人研究（早期的、一手资料）

| # | 结论 | URL | 可信度 | 年代 |
|---|---|---|---|---|
| E1 | **Trammell Hudson《Fuji X100》**：<br>· "**XOR with 0xFF** — strings appear, but with gaps."<br>· "Fuji's EXR CPU is clearly **ARM** based" + 贴出 `push {r4,r5,r6,r7,r8,r11,lr}` 等有效 ARM 序列<br>· 头部："Starts with **04 00 00 00**, followed by **512 bytes of ASCII text containing values in the range 30 to 39**. If that ASCII text is re-interpreted as a hex dump again, it becomes the string `00026381 00026382 00026384 00026389 00000000…`"<br>· 他的猜测："Perhaps there are **multiple updates included in the file** and this is denoting which ones are present?"<br>· 段标记：`aa 55 00 ff`（原样）/ `55 aa ff 00`（取反后）每 0x200 字节重复；之后 `13 00 00 eb` 标记 + **64KB 一段的 ARM 代码** | <https://trmm.net/Fuji_X100/> | 高（一手、独立于我方的第三方） | 2015（页面 2020-11-08 修订） |
| E2 | **Igor Skochinsky `dump_hdr.py`**（回答 RE.SE 提问）：**另一种** Fujifilm 容器——老 FinePix `FPUPDATE.DAT` 用 magic `"RIHR"`(0x52494852)，结构 `(sig, unk4, nb, plfm, unkC)` + `nb` 个 `(typ, blkoff, blksize, unk8, cksum)`，**偏移/长度以 512 字节为单位**（`blkoff<<9`） | <https://gist.github.com/skochinsky/3b9f16ecf33f9906fdaebe8a356a09da> | 高 | 2019-11-16 |
| E3 | 结论：Fujifilm 至少有**两族** .DAT：老 FinePix 的 `RIHR` 块表族，和 X 系列/GFX 的 `os_type + FujiFirmHeader` 族。**我们的文件属后者**（0x00 = 6，无 RIHR） | 综合 E2 + B2 | 高 | — |

### F. 官方 Fujifilm 资料（机型/版本/更新流程）

| # | 结论 | URL | 可信度 | 年代 |
|---|---|---|---|---|
| F1 | **X-T4 最新固件 = Ver.2.12**（页面 "Last Updated: 07.09.2024"），下载文件名 **`FWUP0024.DAT`**，直链 `https://dl.fujifilm-x.com/support/firmware/x-t4-212-79jwnwyy/FWUP0024.DAT`；HTTP 头 **`Content-Length: 51278280`**、`Last-Modified: 2024-07-04`——**与本文件字节数完全相同** | <https://fujifilm-x.com/en-us/support/download/firmware/cameras/x-t4/> | 高（官方） | 2024-09 |
| F2 | X-T4 固件版本历史（页面枚举）：1.00, 1.01, 1.02, 1.03, 1.10, 1.11, 1.20, 1.21, 1.22, 1.23, 1.25, 1.30, 1.40, 1.50, 1.60, 1.70, 1.71, 1.72, 2.00, 2.01, 2.10, 2.11, **2.12** | 同上 | 高 | 2024-09 |
| F3 | **文件命名规则（官方原话）**："Download the firmware **`FWUP00##.DAT`** for the camera. **'##(figures)' varies depending on models.** The file name is **`FPUPDATE.DAT`** in case of X-Pro1." → `FWUP0024` 是**机型专属编号**，与版本号无关 | <https://fujifilm-x.com/en-us/support/download/procedure-x-interchangeable/> | 高（官方） | — |
| F4 | 更新流程：充满电 → 相机内格式化 SD → PC 拷贝 `FWUP00##.DAT` 到卡根目录 → 插卡开机（按住 **DISP/BACK** 可查当前版本）→ 菜单内执行更新；"The firmware upgrade is not required if its version is latest" | 同上 | 高 | — |
| F5 | X-T4 = 2610 万像素 BSI X-Trans CMOS 4 + **X-Processor 4**，2020-02-25 发布 | <https://en.wikipedia.org/wiki/Fujifilm_X-T4> | 高 | 2020 |

### G. X-Processor 4 的架构：公开资料的边界（要诚实）

| # | 结论 | URL | 可信度 | 年代 |
|---|---|---|---|---|
| G1 | **没有找到任何 Fujifilm 官方或权威第三方公开文档**说明 X-Processor 4 的核数、ISA 版本、主频。Fujifilm 只做营销名，不公布 die shot/CPU 细节 | （检索 X-Processor 4 + Cortex-A7 / teardown 均无权威命中） | — | — |
| G2 | 可用的**间接公开证据**：fujihack wiki 把 **X-Processor 5 明确写成 "Quad-core Aarch64 CPU"**，并单独列 **X-Processor 4 = X100V/X-S10** 一行（未标 Aarch64）→ 即 X-Processor 4 是**32 位 ARM** 世代（Aarch64 是 v5 的"新特性"） | <https://wiki.fujihack.org/history/> | 中 | 2025 |
| G3 | fffw 的 ARM 工具链全部按 **ARM32** 处理（`ks.ARCH_ARM`、unicorn "ARM/ARM64"），且 ELF 只覆盖 ARM 主核 | `fujihack/patcher`、`fffw/ffcompress` | 中 | 2024–2026 |
| G4 | **我们自己的证据最硬**：解码后 `0x20274` 是 ARM 异常向量表、section0 起点是 ARM32 函数序言、并直接读到 **`ThreadX SMP/Cortex-A7/GNU Version G5.6.2.5.0`** 字符串（【观测】，Lead 发现）。即 **X-T4 主固件 = 32 位 ARM (Cortex-A7) + ThreadX SMP**，这与 G2/G3 一致，但"**公开资料从未直接写出 X-T4 = Cortex-A7 + ThreadX**"——只能算"由公开资料间接支持 + 我方直接观测证实" | — | 【观测】高 | 2026-11 |

---

## 2. 对本次分析可用之处（能解释我们观测的公开结论）

| 我们的观测 | 公开资料的解释 | 来源 |
|---|---|---|
| `0x00` u32 = **6**（曾被猜为"表项数/块数"） | **不是块数**，而是 **DAT container `os`/`type` 版本号 = 6**；它决定 `MODEL_CODE_SIZE` | A1, B2, C1 |
| `0x04..0x203` 恰好 **512 字节** ASCII hex 文本 | `os=6 ⇒ MODEL_CODE_SIZE = 512`，所以 `code[]` 正好占 512 字节 → 下个字段落在 `0x204`。**数学上唯一自洽** | B2, C1 |
| `0x04` 起是 `33 30 33 30…`（每隔一字节 0x33） | model-code 区在**奇数下标**存数字字符，偶数下标填 `0x33`('3')，即"ASCII hex 再套一层 ASCII" | C1, E1 |
| `0x204` = 2、`0x208` = 0x12 | `version1=2`、`version2=0x12`，相机按 **hex** 显示 → **v2.12**；与官方 X-T4 最新版 2.12 完全一致 | A1, B2, C1, F1 |
| `0x20C` = `F5 BF B4 56` | `checksum` 字段（u32 LE = 0x56B4BFF5） | A1, B2 |
| `0x210` 起有一段"像表"的二进制 | `device_type`/`end` 字段；**但 type 6 的这段明显更长**（见 §3、§4） | A1, B2 |
| `0x27C` 有 `55 55 55 55 AA AA AA AA` | 与 E1 记录的 `aa 55 00 ff` / `55 aa ff 00` **段边界标记同族**；Trammell 在 X100 上也见到 `aa 55`/`55 aa` 与 `ff ff aa aa` 混排的填充/边界样图 | E1 |
| 取反后出现大量 `FUJIFILM`/`X-T4`/ThreadX/UI 资源串 | 载荷**逐字节取反**是 Fujifilm 一贯手法（"XOR with 0xFF"） | A1, C1, E1 |
| 取反后 `0x20274` 是 ARM 向量表、有 Thumb-2 代码 | 主固件为 32 位 ARM；fujihack 的 ARM32 工具链、Trammell 的 ARM 代码序列都印证 | B4, E1, G4 |
| 数据按 **0x20000（128KB）网格**、段数据起点 `0x20000*k + 0x274` | **无公开文档**直接写这个网格/0x274。但公开资料给出的相邻事实是：段是**页对齐容器**（fflz 用 **16KB page** 喂硬件解压、fujihack 用 `codeSize+20` 算头长、老 FinePix 用 **512 字节为单位**的块表）。0x20000 网格 + 0x274 前缀应视为**我们的一手结论**，公开资料只能算"不矛盾" | D3, B2, E2 |
| 载荷中段"没有 ARM 代码" | **因为它是压缩的**：FFLZ/LZ77 压缩段占大块，只有解压后才是代码 | C2, D3 |
| 尾部全 0 / 尾部双份数据 | 无公开佐证（Lead 观测）。最接近的是 E1 记录的 "all 0xff until 0x48250" 之类块式空洞 | E1 |

### 我们实测复核过的公开结论（可信度已升级为"我们确认"）

1. **头结构 100% 命中**：按 B2/C1 的算法解析本文件 → `os=6, codeSize=512, payload_offset=0x214, version=2.12, checksum=0x56B4BFF5`。
2. **取反判定**：`FUJIFILM` 在**取反域出现 10 次**、原样 **0 次**；文件前 8MB 采样 2,097,152 个 u32 中，ARM `push` 特征（高半字 ∈ {E92D,E92C,E92E}）**取反域 1995 个 vs 原样 18 个**（~110×）。→ 取反确凿。
3. **FFLZ 压缩段：用公开格式在本文件上解出 4 段，全部通过"输出长度必须精确等于声明长度"的强校验，合计 33,543,940 字节**——与 C3 对**官方 X-T4 2.12** 报告的 `33,543,940` **完全相同**（四段之和亦逐一对应）。段位置（文件偏移，均在 `0x20000*k+0x274`）：

   | # | 文件偏移 | 解压后 | 压缩后 | pages | 解压/压缩 |
   |---|---|---|---|---|---|
   | 0 | `0x0260274` | 7,420,408 | 3,449,482 | 211 | 2.15 |
   | 1 | `0x05C0274` | 9,437,184 | 5,256,655 | 321 | 1.80 |
   | 2 | `0x0AE0274` | 10,240,000 | 4,632,713 | 283 | 2.21 |
   | 3 | `0x1A00274` | 6,446,348 | 3,310,991 | 203 | 1.95 |
   | | | **33,543,940** | 16,649,841 | 1018 | |

   段 0 解压后开头即合法 ARM32：`00 50 2d e9`(push) `0f 50 2d e9` `0d 00 a0 e1`(mov r0,sp) `b1 bd 09 eb`(bl) `0f 50 bd e8`(pop) `1e ff 2f e1`(bx lr)；段内含 `FUJIFILM`×5、`MOVIE`×1024、`MODE_PIXEL`×30、`4K`×434。
   > 脚本与产物在临时目录（`%TEMP%\xt4wr\`，已写出 `xorview.bin` 与 4 个 `sec*.bin`），未写入共享工作区，**未修改 .DAT**。

---

## 3. 与我们观测**矛盾**之处（必须写进文档的"未决点"）

1. **校验和算法：修正后的结论（此前误判为"矛盾"）**
   - 公开说法：A1 "add up all the bytes"；B3 的实现是 `checksum += Σ(明文字节)`。
   - 我实测 `0x20C = 0x56B4BFF5`，**直接简单求和确实不匹配**：`Σ(raw payload 0x214..EOF)` = `0x53B7BC30`；`Σ(~payload)` = `0xB7A9881C`；u16/u32 字和、`crc32`、`adler32`、大小端互换——全不匹配。
   - **但拿到官方原件后规律浮现**：<br>
     `OURS`  : `0x56B4BFF5 − 0x53B7BC30 = 0x02FD03C5`<br>
     `OFFICIAL`: `0x56831A6C − 0x538616A7 = 0x02FD03C5`<br>
     ⇒ 两个**内容完全不同**的文件，`checksum − Σ(raw bytes 0x214..EOF)` 是**同一个常量** `0x02FD03C5`。
   - ⇒ 校验和确实是"从 `0x214` 到 EOF 的字节累加"，再加一个**固定偏移/种子项 `0x02FD03C5`**（等价说法：对取反域求和再加另一常量，因为两者只差 `255×L mod 2³²`）。该常量的来历**仍未知**（候选：算法里的固定 seed、覆盖区间比 EOF 多/少一段固定长度、或包含某个固定项）。
   - **重要副结论**：本文件虽然被改动过，但**校验和是按同一算法正确重算过的**（不是"改了内容忘了改校验"）⇒ 造这个 `早期二改` 包的人/工具**完整实现了 Fujifilm 的校验和算法**。
   - 建议：用第三个样本（如 X100V 3.01 或 X-T4 2.11）验证 `0x02FD03C5` 是否**跨机型/跨版本恒定**；若恒定 → 直接写进结构文档作为"校验和常量"。
2. **取反起点：`0x214/0x204` vs `0x378`**
   - 公开实现（B2、C1）都把 payload 起点（`codeSize+20 = 0x214`）当作取反起点。
   - Lead 实测：明文容器头一直到 **`0x378`**，之后才取反。
   - 两者**不冲突但公开资料不足**：`0x214` 只是 `FujiFirmHeader` 结构体长度，type 6 在其后还有 `0x214..0x377`（0x164 = 356 字节）的明文表。C4 也自己承认"统一 XOR 会破坏本来就是明文的区域"。
   - ⇒ 文档里应写：`FujiFirmHeader` 到 `0x214` 结束；**type 6 的容器头实际到 `0x378`**（我们的一手结论，公开资料未记录）。
3. **`0x210` 的 `device_type`/`end` 语义失效**
   - A1 说"是否镜头/机身"，B2 说 `end==2` 判为镜头。
   - 我们读到 `0x210 = 0xFF6DB51F`，既不是 1 也不是 2。⇒ type 6 的该字段**不是**简单枚举，或 `0x210` 已属于扩展头（呼应上一条）。
4. **"Code is 32 bit ARM (not thumb)"**（B4）与我们观察到的 **Thumb-2** 代码（Lead 在取反后 `0x0A78` 处见 `F10E 01D3`/`EB00000C` 等）冲突。⇒ B4 是早期机型的结论，**X-T4 是 ARM + Thumb-2 混合**（ARM 向量表/部分函数用 ARM，主体多为 Thumb-2）。
5. **model-code 的语义三种说法不一致**
   - B2：把整个字符串当一个 `MODEL_CODE` 去和 `model/*.h` 里的宏比较；
   - C1：按 8 个 hex 字符分组 → `前6位=base, 后2位=区域变体`；
   - E1（Trammell）：猜测是"本文件里包含哪些更新"的清单。
   - 本文件解出 11 组：`00056001/00056002/00056004/00056009` 与 `00057001/00057002/00057004/00057005/00057006/00057007/00057008`（两个 base：`000560`、`000570`）。**哪种解释正确仍未知**；C1 的"区域变体"读法能自洽，但没有旁证。
6. **官方 wiki 的 CPU 表漏了 X-T4**：`X-Processor 4` 一行只写 X100V/X-S10，不含 X-T4（X-T4 确实是 X-Processor 4）。⇒ 该表不可作为权威依据。
7. **`FWUP0024` / `早期版` 的含义**：`FWUP0024` = X-T4 已由官方直链证实（F1/F3）；**`早期版` 与 `早期二改` 在公开资料中零命中**。已知它不是版本（版本字段是 2.12），也不是机型号。**候选解释（均未证实）**：构建/日期编号、服务（service）固件批次号、"AE fix" 专项修正包编号。**建议**：拿到官方原件比对后再判断（若两者仅少量字节不同，则 `早期二改` 极可能是"在官方 2.12 上只改了 AE 相关代码/参数"的定制构建）。

---

## 4. 建议下一步（按性价比排序）

1. ~~下载官方 `FWUP0024.DAT`（v2.12）并做二进制 diff~~ → **已完成，见 §6**。结论：同尺寸、头结构全同、4 段位置与解压后大小全同、20.3% 字节不同、含 `…R98.X-M5` 字面量、校验和按同一算法正确重算。
   - 若还要再进一步：下载 **X-T4 v2.11 / v2.10**（或 X100V 3.01）做第三个样本，用来确认 §3-1 的常量 `0x02FD03C5` 是否跨版本/跨机型恒定。
   - 直接可用的直链规律：`https://dl.fujifilm-x.com/support/firmware/<model>-<ver>-<hash>/FWUP<xxxx>.DAT`（`<hash>` 每版不同，需从对应机型 firmware 页抓 `href`）。
   - 注意：**不要**把 51MB 固件提交进共享工作区；放 `out/` 或临时目录。
2. **用已验证的 FFLZ 解码器产出真正的"可分析镜像"**（成本极低，收益巨大）
   - 我这里已跑通（4 段 / 33,543,940 字节，段 0 开头即合法 ARM32）。建议把这段逻辑固化成 `tools/*.py`：`decode_fflz.py` → 输出 4 个 `out/sec{0..3}.bin` + 一份 `out/sections.json`（offset/unpacked/packed/pages）。
   - **region-mapper 的字符串/资源扫描应改到"解压后的段"上做**，而不是在 `xor_view` 上做——`xor_view` 只有 16.6MB 压缩流 + 未解压区，会漏掉 33.5MB 里的绝大部分字符串/表（例如 `MODE_PIXEL_4K`、`MOVIE_REC_START` 这类符号）。
3. **用 fffw 的产物作为"对照答案"**
   - `ffun/ports/xt4/0212/` 里已有 `msgid.h`(110KB)、`ui_setp.h`(74KB)、`task.h`、`key_codes.h`、`openvg.h`、`libptp.h` 等——都是**同机型同版本**的公开逆向成果。可直接用来给解出的符号"命名"，并反过来校验我们的分段是否正确。
   - 但 `ffun` 本体未发布（README 自述不能编译），**不要指望直接跑 `dat2elf`**；`ffcompress/fflz`（Go）是可用的、bit-exact 的压缩/解压参考实现。
4. **校验和专项**：在官方原件上先跑 §3-1 的穷举；若仍失败，试 (i) 跳过 `0x0..0x378` 头、(ii) 只算"压缩段"区间、(iii) 16-bit 折叠和、(iv) 把 `0x20C` 当 `(sum ^ 0xFFFFFFFF)`/补码。也建议**在 fujihack patcher 里对官方文件做一次"版本号 +1"再导回**，看它算出的新 `0x20C` 与官方原值差是否等于注入差值——这是对 B3 公式最直接的检验（不刷机，仅离线算）。
5. **签名/加密判断（结论：本项目大概率不需要密钥）**
   - 公开资料里**没有任何**"Fujifilm .DAT 主体被加密"的记录；唯一被反复确认的"加密"就是 **XOR 0xFF** 取反。
   - 公钥材料只出现在 X-Processor 5 世代端口（`ffun/ports/{xh2,xh2s,xt5,xt50,x100vi,gfx100ii,xe5,xs20}/pubkey.*`），**X-T4 目录没有**。⇒ **X-T4 的 .DAT 很可能只做校验和校验，没有 RSA/ECDSA 签名**（中等可信，值得在文档里标为"推测"）。
   - 若后续发现确实有签名，`ffun/ports/find-pub-key.py` 与 `chksum-keys.sh` 是现成的入手点。
6. **想抄现成工具**（如果只想"看到内容"）：<https://fujihack.org/patcher/> 的 web patcher 可以直接拖入 .DAT 做 unpack/inject/repack/downgrade；`EnglandLobster/fujifilm-firmware-tools` 的 `dat.py` + `fflz_sections.py` 只有 ~200 行，最容易被我们复制进 `tools/`。

---

## 5. 关键结论对照：公开资料 vs 我们的硬结论

| 命题 | 公开资料 | 我方观测 | 结论状态 |
|---|---|---|---|
| 容器头 = `os_type + 512B model-code + version1/2 + checksum + device_type`（到 `0x214`） | ✅ 有 struct 原文 + 两套独立实现 | ✅ 逐字段命中 | **已证实（双方）** |
| 载荷逐字节取反（XOR 0xFF） | ✅ 2015 起多次记录 | ✅ 取反域 ARM 密度 ~110×、`FUJIFILM` 只在取反域 | **已证实（双方）** |
| 取反起点 = `0x214` | ⚠️ 公开实现如此假设 | ❌ 实测明文到 `0x378` | **公开资料不精确，以我方为准** |
| 载荷含 LZ77/FFLZ 压缩段，16KB 页 | ✅ 完整格式 + 1259 段 bit-exact 验证 | ✅ 4 段全解，合计 33,543,940 B，与官方 X-T4 2.12 报告一致 | **已证实（双方）** |
| 机器码为 32 位 ARM | ✅ 多来源 | ✅ 解出 ARM32 序言/向量表；且含 Thumb-2 | **已证实**；但"纯 ARM 无 Thumb"是错的 |
| X-T4 = Cortex-A7 + ThreadX SMP | ⚠️ 仅间接（v5=Aarch64、ThreadX 年表） | ✅ 固件内直接读到 banner | **我方直接证实；公开资料仅旁证** |
| 校验和 = 字节和 | ⚠️ wiki/patcher 这么说 | ✅ 两文件均为 `Σ(raw 0x214..EOF) + 0x02FD03C5` | **基本证实**（只差一个固定常量，见 §3-1） |
| 版本 = 2.12 | ✅ 官方最新 2.12 | ✅ `version1=2, version2=0x12` | **已证实** |
| `FWUP0024` = X-T4 机型文件名 | ✅ 官方直链 | ✅ 同尺寸 | **已证实** |
| `早期版` / `早期二改` 含义 | ❌ 无任何公开记录 | ➕ 与官方 2.12 同尺寸、头结构全同、20.3% 字节不同、含 `…R98.X-M5` 字面量 | **仍未决**；但已可确定"**基于官方 2.12 的二次构建**"，见 §6 |
| 是否含全部模块 / 每次更新是否全量 | ✅ fffw："newer cameras often package firmware **more like a tar archive**"，可含 Linux、镜头固件、RL78(IBIS)、DSP、AI chip 代码 | ➕ 我们解出 4 个压缩段，另有大量未压缩/未识别区 | **更新包=全量镜像**（含非主 CPU 部分） |

---

## 6. 附：与官方 X-T4 v2.12 原件的逐字节比对（本次一手实证，2026-11-06）

> **权威完整版见 [`06-diff-official.md`](06-diff-official.md)**（含完整区间坐标、分区统计、解压后逐段对比、证据强度分级）；本节为先行简版。

### 6.1 取样

| | 本文件 | 官方原件 |
|---|---|---|
| 来源 | 用户提供 `FWUP0024.DAT` | <https://dl.fujifilm-x.com/support/firmware/x-t4-212-79jwnwyy/FWUP0024.DAT> |
| 大小 | 51,278,280 | 51,278,280（**完全相同**） |
| SHA-256 | `618a3edd…62c783f` | `853d273b5603d3a2b93493f0ebd6a762b0b4b6bdc70317777775ae5f8ed93bc5` |
| | | （此哈希**正好等于** C3 对 X-T4 2.12 的记录 → 确认取到的确是官方 2.12） |

> 官方文件仅用于**只读比对**，存放在临时目录，未放入共享工作区；本文件未被修改。

### 6.2 头部：完全一致（结构是"构建不变量"）

| 字段 | 本文件 | 官方 | 一致? |
|---|---|---|---|
| `0x00` os_type | 6 | 6 | ✅ |
| `0x04..0x204` model_code | `00056001 00056002 00056004 00056009 00057001 00057002 00057004 00057005 00057006 00057007 00057008` | 完全相同 | ✅ |
| `0x204` version1 | 2 | 2 | ✅ |
| `0x208` version2 | 0x12 | 0x12 | ✅ |
| `0x20C` checksum | `0x56B4BFF5` | `0x56831A6C` | ❌ 差 `0x31A589` |
| `0x210` end/device_type | `0xFF6DB51F` | `0xFF6DB51F` | ✅（**证明它不是"镜头/机身"枚举，而是构建不变量**） |
| `0x214..0x378` 扩展明文头 | — | — | ✅ **逐字节相同** |

⇒ 结论：`0x0..0x378` 的容器头是**版本级固定结构**，不随内容变化；只有 `0x20C` 校验和随内容变。**这一点对写结构文档非常有利**。

### 6.3 压缩段：位置/大小/页数完全一致，只有压缩流内容不同

| # | 文件偏移 | 解压后 | pages | packed（本文件） | packed（官方） | 差 |
|---|---|---|---|---|---|---|
| 0 | `0x0260274` | 7,420,408 | 211 | 3,449,482 | 3,449,330 | +152 |
| 1 | `0x05C0274` | 9,437,184 | 321 | 5,256,655 | 5,254,523 | +2,132 |
| 2 | `0x0AE0274` | 10,240,000 | 283 | 4,632,713 | 4,632,713 | **0** |
| 3 | `0x1A00274` | 6,446,348 | 203 | 3,310,991 | 3,309,617 | +1,374 |
| | | **33,543,940** | 1018 | 16,649,841 | 16,646,183 | +3,658 |

- 段的**起点、解压后大小、页数在两份文件里逐个相同**（`pages = ceil(packed/0x4000)` 均成立）。
- 这说明：**0x20000 网格 + `+0x274` 段头**是容器规范，不是本文件的特例。⚠️ 注意：公开资料（C2/D3）**没有**写过 `0x20000`/`0x274`，所以这条仍应标注为"我方一手结论，公开资料不矛盾但未记载"。
- 两份文件的**最后一个非零字节都是 `0x30D49A1`**，尾部 **75,814** 字节全 0（与 Lead 的"尾部双份/全零"观察一致）。

### 6.4 内容差异

- 不同字节：**10,432,565 / 51,278,280 = 20.345%**，聚成 **540 个簇**（gap≤64）。
- 第一个差异就是 `0x20C..0x20E`（校验和本身，预期内）；第二个在 `0x0C03D2`。
- 可读字符串总体**几乎完全相同**：取反域去重后 本文件 17,727 条 / 官方 17,713 条，只有 26 / 12 条各自独有，且绝大多数是压缩流里偶然出现的可打印字节（噪声）。
- **两处有语义的差异**（后续 `06-diff-official.md` 的完整版为准）：

  **(a) 机型字面量**（文件偏移 `0x0C03D0`，未压缩区、NUL 分隔字符串表；仅 2 字节不同）：

  ```
  OURS     : _FUJIDSCFBLOG_DSF.R98.X-M5
  OFFICIAL : _FUJIDSCFBLOG_DSF.R98.X-T4
  ```

  ⇒ 这个构建在编译期用的是 **`X-M5`** 这个机型标识，而官方 2.12 用的是 `X-T4`。

  **(b) 尾部（第 4 段之后 `0x1D28817..EOF`）多出的未压缩多语言界面文本**：本文件在该区多写约 **17.7 KB**（官方为 `0xFF` 擦除态），以 `0x40000` 为周期、约 70 个约 500 B 的块，内容是 UTF-16LE 的 UI 文本（抽查到德语 `Kräftige S…`、意大利语 `TINTE AMBR…`、印尼语 `Warna ambe…`、英语 `NOSTALGIC Neg.`）。`"NOSTALGIC Neg."`/`"REALA"` 在本文件各出现 70 次、在官方 2.12 中 **0 次**。

  > 补充：`20.3%` 的字节差异**不是** `20.3%` 的功能改动 —— 压缩流的 LZ 级联会放大差异。解压后真实改动只有 **sec0 44,151 B + sec1 3,517 B + sec3 7,967 B ≈ 55.6 KB**，**sec2 完全未动**。详见 `06-diff-official.md`。

### 6.5 由 6.2–6.4 能确定 / 不能确定的事

**能确定（高可信）**
1. 本文件**不是**官方 2.12 原件，而是**在官方 2.12 基础上重新构建/改造**的包：容器头 100% 相同、4 个段的位置与解压后大小 100% 相同，但校验和与 3 个压缩流不同。
2. 造它的人**完整实现了 Fujifilm 的容器格式 + FFLZ 压缩 + 校验和算法**（否则不可能保持头/段布局完全一致且校验和符合 §3-1 的规律）。
3. `0x210` 不是"镜头/机身"枚举（两份文件都等于 `0xFF6DB51F`）。
4. 官方 2.12 与我们的文件都满足 `checksum = Σ(raw 0x214..EOF) + 0x02FD03C5`。

**不能确定（需谨慎表述）**
- `早期二改` / `早期版` 的确切含义；`X-M5` 字面量的出现意味着什么（见下）。
- 20.3% 字节差异中，哪些是"真实功能改动"，哪些只是 LZ77 压缩的级联效应 → **已在 `06-diff-official.md` §7 定论**：解压后真实改动仅 sec0 44,151 + sec1 3,517 + sec3 7,967 ≈ 55.6 KB，sec2 完全未动。

**关于 `X-M5` 的三种可能解释（均未证实，按可能性排序）**
1. **内部工程构建**：`早期二改` = "AE fix" 的专项验证固件，从与 X-M5 共享的代码基线编译，机型字面量未改回 → 这能同时解释"内容大改 + 头结构/版本号保持 2.12 + 文件名带 `_早期二改`"。
2. **跨机型移植/改标**：有人把机型标识改成 `X-M5`（4 字符），但保留了 X-T4 的 model_code 与版本号。
3. **区域/SKU 变体**：`X-M5` 是构建系统里的内部代号（可能性较低，X-M5 是 2024 年真实机型名）。

> 建议把这条**作为"待验证的事实"写进最终文档**：`0x0C03D2` 处的机型字面量 = `X-M5`（本文件）vs `X-T4`（官方 2.12），并注明"含义未定论"。这是一个**用户会很在意**的发现（说明该文件来路并非普通官方下载）。

### 6.6 顺带确认的三条"公开资料未记录"的事实
1. 明文容器头到 `0x378`（公开实现只算到 `0x214`）。
2. 段数据落在 `0x20000*k + 0x274`，段头 = 20 字节 FFLZ 帧（`unpacked/packed/pages=ceil(packed/0x4000)/0x4000/tag=4`）。
3. 校验和 = `Σ(raw 0x214..EOF) + 0x02FD03C5`（待第三个样本确认常量是否普适）。
