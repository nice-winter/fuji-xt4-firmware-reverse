# 09 · SETP / UI 资源区解析：胶片模拟（Film Simulation）选项与顺序

> 对象：`FWUP0024_affix_1108.DAT`（用户当前目标），并用 `aefix_1106` 交叉验证。
> 原则：**只读**，未修改任何 `.DAT`。派生数据用 `out/f1108/**`（Lead 生成）。
> 工具：`tools/setp_decode.py`（本次新增，可复现下文全部结论）。
> 证据等级沿用 `FIRMWARE-STRUCTURE.md`：**【确证】/【强】/【推测】/【未定位】**。

---

## 0. 结论摘要

| # | 结论 | 强度 |
|---|---|---|
| 1 | **前提修正**：`decoded.bin` 的 `0x460000-0x4A0000`、`0x4C0000-0x580000` **不是**「tokenized SETP 资源」，而是 **FFLZ sec0 的压缩流本体**（`0x260288..0x5AA926`）。里面看到的 `FILM_PROVIA`/`FS_PROVIA` 是被 LZ 字面量截断的片段。 | 【确证】 |
| 2 | 真正的 SETP/UI 资源在**解压后的段**里：`sec0.bin` 与 `sec1.bin` 各有一大块 4 字节对齐、NUL 结尾的 ASCII 标识符池。sec1 池 = `0x6D8AB0..0x70AA2C`（204,668 B，12,623 个名字）。 | 【确证】 |
| 3 | **关键突破**：20 字节「解压段头」给出段的**加载基址**（第 2 个 u32；第 3 个 u32 恰好 = 段长度）。sec0 `base=0x01021000 size=0x714000`；sec1 `base=0x01E0F000 size=0x900000`。凭它把名字池里的裸 ASCII 解析成了**绝对地址引用**。 | 【确证】 |
| 4 | sec1 里有一张 **`(name_ptr, index)` 8 字节注册表**（`0x6C8150..0x6D8AA0`），按「小表」串联；每张小表内 `index` 从 0 连续递增 ⇒ **index = 枚举值**，小表 = 某枚举的「枚举名表」。共 702 张。 | 【确证】 |
| 5 | 由此解出**胶片模拟两张枚举名表**：拍摄用 `UI_FILM_SIM_*`（23 项，enum 0..22）@sec1 `0x6D35F8..0x6D36A8`；RAW 开发用 `UI_RAW_DEV_FILM_SIM_*`（18 项，enum 0..17）@sec1 `0x6D6430..0x6D64B8`。**完整顺序见 §4**。 | 【确证】 |
| 6 | `UI_SETP_*` 是另一套全局 ID 注册表（id 1..2122）@sec1 `0x6C9BD8..0x6CDE20`：`UI_SETP_FILM_SIM=1070`、`_SELECT=1076`、`_SELECT_1=1078`、`_2_SELECT_1=1081`、`UI_SETP_RAW_DEV_FSIM=1655`。 | 【确证】 |
| 7 | 显示名来自 **`FDL Font` 文本资源的 UTF-16LE 文本池**（decoded `0x1DA0274` 起第 1 个包）：标签是「图标 PUA + 文本」的**复合记录**，例如 `\uf06a\uf06f/STANDARD`(=PROVIA/STANDARD)、`\uf370\uf369/CINEMA`(=ETERNA/CINEMA)、`\uf06c\uf071/SOFT`(=ASTIA/SOFT)。 | 【确证】 |
| 8 | **枚举顺序 ≠ 菜单顺序**：枚举把 `MONOCHROME/SEPIA` 放在中间、且**完全没有** `CLASSIC Neg. / NOSTALGIC Neg. / REALA ACE` 的枚举名；而相机菜单把 `CLASSIC CHROME` 排第 4、黑白/棕褐排后面。 | 【确证】 |
| 9 | **「菜单/选项显示顺序」的显式结构：未定位。** 名字池、注册表、FDL 文本池、sec3、4 个解压段的全部候选数组都已排查（§6 列清单），**没有**找到 12–16 项的「选项 ID / 枚举值 顺序数组」。 ⇒ 顺序最可能定义在**尚未定位的 UI 菜单资源或代码**中，而不是任何已知数据表。 | 【未定位】 |
| 10 | 菜单**实际显示**的 12 个基础顺序可由官方手册核对（§7）；`NOSTALGIC Neg. / REALA ACE` 在固件里是**后来追加**的（文本在每语言块之后的小独立池里）。其在菜单中的插入位置**固件侧未证**，标【推测】。 | 【强】/【推测】 |

---

## 1. 前提修正：「tokenized 0x80/0x81 资源」其实是 FFLZ 压缩流

Lead 最初观察到 `decoded.bin` 的 `0x460000-0x4A0000` 有「ASCII 混 0x80/0x81 控制字节、串被截断」的形态，怀疑是某种「长度前缀+类型字节」的 tokenized 资源。**结论：不是。**

### 1.1 范围证据

FFLZ sec0 段头位于 decoded **`0x260274`**（`<5I`）：

```
unpacked   = 7,421,952 (0x714000)     ← 恰好等于 out/f1108/sections/sec0.bin 长度
packed     = 3,450,526 (0x34A69E)
pages      = 211
page_size  = 0x4000 (16 KiB)
tag        = 4
token 流   = decoded 0x260288 .. 0x5AA926
```

`0x460000-0x4A0000` 与 `0x4C0000-0x580000` **都完整落在** `0x260288..0x5AA926` 内 ⇒ 那两片「资源」就是压缩流的中段。

### 1.2 语法证据（逐字节走 token）

以 Lead 给的 `0x486093` 上下文为例，取 `decoded 0x486343` 起：

```
decoded 0x486343:  0A 49 4C 4D 5F 50 52 4F 56 49 41 8B 4A 81 44 03 56 45 4C ...
                   ^^ = 0x0A < 0x80  ⇒ FFLZ 字面量 run，长度 10
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ = "ILM_PROVIA"  （正好 10 字节！）
                                         ^^^^^ = 0x8B 0x4A → 2 字节回溯 token
```

即 `0x80/0x81` 是 **LZ77 回溯 token**（`token>=0x80` 时 `length=B&0x0F, distance=((token&0x7F)<<4)|(B>>4)`，见 `FIRMWARE-STRUCTURE.md §7`），`<0x80` 是字面量 run 长度。所谓「被控制字节隔开的截断串」(`SAV`/`ERR`/`ILM_PROVIA`/`VEL`/`C_ST...`) 全是相邻**字面量 run 的拼接边界**，`F`、`IL` 等被回溯复制，所以看起来缺字。

复现：`python tools/setp_decode.py verify`（会打印上面的段头与字节走查）。

⇒ **真正的 UI/SETP 资源必须到 `out/f1108/sections/sec{0,1,2,3}.bin` 里找。**

---

## 2. 真正的资源在哪：两个 ASCII 标识符池 + 段头里的加载基址

### 2.1 标识符池（NUL 结尾，4 字节对齐）

| 段 | 池范围（段内偏移） | 大小 | 名字数 |
|---|---|---|---|
| `sec0.bin` | `0x3EE0C8..0x48A73C` | 640,628 B | 24,620 |
| `sec1.bin` | `0x6D8AB0..0x70AA2C` | 204,668 B | 12,623 |

两段都含同一族标识符：`UI_FILM_SIM_*`、`UI_RAW_DEV_FILM_SIM_*`、`UI_SETP_*`、`UI_MENUCOM_ITEM_*`、`UI_MENU_KIND_*`…（`sec0` 另有大量图标/消息名）。

### 2.2 解压段头 = 加载基址（本次新发现，其它笔记尚未记录）

`secN.bin` 前 20 字节：

```
sec0: 00 00 00 00 | 00 10 02 01 | 00 40 71 00 | C4 10 29 01
      word0=0     base=0x01021000  size=0x714000  word3=0x012910C4
sec1: 00 00 00 00 | 00 F0 E0 01 | 00 00 90 00 | 60 DE E1 01
      word0=0     base=0x01E0F000  size=0x900000  word3=0x01E1DE60
```

`word2` 与真实文件长度**逐字节相等**，故 `word1` 解释为**加载虚拟基址**可信。§3 的注册表只有在用这个基址时才能全部解析成功（反过来也验证了基址正确）。

### 2.3 为什么之前找不到「指针引用」

- 直接搜 `u32 == 池内偏移`：`sec0`/`sec1` 都 **0 命中**（因为代码里存的是**绝对地址**）。
- 用 §2.2 的基址换算成 VA 后再搜：`sec1` 每个名字**恰好 1 处命中**，且全部落在一张 8 字节记录表里 ⇒ 破案。
- `sec0` 的名字池只有 1,254/24,620 个被引用（是另一套较小的注册表），**`UI_FILM_SIM_*`/`MODE_FSIM_*` 在 sec0 里 0 引用** ⇒ sec0 的池主要是调试名，实际 UI 枚举注册表在 sec1。

---

## 3. sec1 的 `(name_ptr, index)` 注册表（本次核心结构）

### 3.1 记录格式

```
struct Entry { u32 name_ptr_VA; u32 index; };   // 8 字节，表内连续
name_ptr_VA = sec1_base(0x01E0F000) + 名字在 sec1 内的偏移
```

- 表范围：`0x6C8150..0x6D8AA0`（紧邻名字池之前），共 **7,774** 条有效记录。
- 记录被切成 **27 个连续 run**；run 内再按 `index` 是否 +1 切分成 **702 张枚举名表**。
- 每张表内 `index = 0,1,2,…` ⇒ **index 就是该枚举的数值**。

例（拍摄胶片模拟那张表）：

```
sec1 0x6D35F8: 24 9C 4F 02 | 00 00 00 00   → name VA 0x024F9C24 → sec1 0x6EAC24 "UI_FILM_SIM_STD", index 0
sec1 0x6D3600: 34 9C 4F 02 | 01 00 00 00   → "UI_FILM_SIM_F1B", index 1
...
```

两张主表（另有 700 张小表）：

| 表 | 段内偏移 | 条数 | index 范围 | 首个名字 |
|---|---|---|---|---|
| `UI_SETP_*` 全局 ID 表 | `0x6C9BD8..0x6CDE20` | 2,122 | 1..2122 | `UI_SETP_BKUP_VER` |
| 枚举名表串 | `0x6CDE30..0x6D8AA0` | 5,519 | 每表 0..N | `UI_MENUCOM_ITEM_ISO` |

> 注意：第 2 个 run 内 index 会反复从 0 开始，所以它**不是一张全局 ID 表**，而是几百张并列的枚举名表。

复现：`python tools/setp_decode.py registry`。

---

## 4. 胶片模拟相关的有序结构（本次可交付的硬结论）

### 4.1 拍摄用枚举：`UI_FILM_SIM_*`（23 项）

位置：sec1 `0x6D35F8..0x6D36A8`（23×8 B），名字串在 `0x6EAC24..0x6EAE38`。

| enum | 名字 | 实测显示标签（FDL，§5） |
|---:|---|---|
| 0 | `UI_FILM_SIM_STD` | `\uf06a\uf06f/STANDARD` = **PROVIA/STANDARD** |
| 1 | `UI_FILM_SIM_F1B` | `\uf06b\uf070/VIVID` = **Velvia/VIVID** |
| 2 | `UI_FILM_SIM_F1C` | `\uf06c\uf071/SOFT` = **ASTIA/SOFT** |
| 3 | `UI_FILM_SIM_F2` | ?（无对应复合标签，疑为历史别名） |
| 4 | `UI_FILM_SIM_BW` | **MONOCHROME** |
| 5 | `UI_FILM_SIM_SEPIA` | **SEPIA** |
| 6 | `UI_FILM_SIM_CHROME` | ?（与 14 重复嫌疑，见 §7.3） |
| 7 | `UI_FILM_SIM_BW_FILTER` | ?（黑白滤镜基项） |
| 8 | `UI_FILM_SIM_BW_FILTER_NON` | — |
| 9 | `UI_FILM_SIM_BW_FILTER_R` | **MONOCHROME+R FILTER** |
| 10 | `UI_FILM_SIM_BW_FILTER_Y` | **MONOCHROME+Ye FILTER** |
| 11 | `UI_FILM_SIM_BW_FILTER_G` | **MONOCHROME+G FILTER** |
| 12 | `UI_FILM_SIM_PRONEGA_S` | **PRO Neg. Std** |
| 13 | `UI_FILM_SIM_PRONEGA_H` | **PRO Neg. Hi** |
| 14 | `UI_FILM_SIM_CLASSIC_CHROME` | **CLASSIC CHROME** |
| 15 | `UI_FILM_SIM_SUPERIA` | ?（内部名；疑对应 `CLASSIC Neg.`/`NOSTALGIC Neg.` 之一） |
| 16 | `UI_FILM_SIM_ETERNA` | `\uf370\uf369/CINEMA` = **ETERNA/CINEMA** |
| 17 | `UI_FILM_SIM_BLEACH_BYPASS` | **ETERNA BLEACH BYPASS** |
| 18 | `UI_FILM_SIM_ACROS_FILTER` | **ACROS** |
| 19 | `UI_FILM_SIM_ACROS_FILTER_NON` | — |
| 20 | `UI_FILM_SIM_ACROS_FILTER_R` | **ACROS+R FILTER** |
| 21 | `UI_FILM_SIM_ACROS_FILTER_Y` | **ACROS+Ye FILTER** |
| 22 | `UI_FILM_SIM_ACROS_FILTER_G` | **ACROS+G FILTER** |

> 这张表是 **enum 定义序**，不是菜单序：`MONOCHROME/SEPIA` 在中间（4/5），而菜单里它们在倒数第 3/2 位；且**没有** `CLASSIC Neg.`、`NOSTALGIC Neg.`、`REALA ACE` 的枚举名（固件里也搜不到 `REALA`/`NOSTALGIC` 的 ASCII 标识符）。

### 4.2 RAW 开发用枚举：`UI_RAW_DEV_FILM_SIM_*`（18 项）

位置：sec1 `0x6D6430..0x6D64B8`；名字串 `0x6F3570..0x6F3778`。顺序（enum 0→17）：

```
STD, F2, F1B, CLASSIC, F5A, F5, SUPERIA, ETERNA, BLEACH_BYPASS,
ACROSS_FILTER_NON, ACROSS_FILTER_R, ACROSS_FILTER_Y, ACROSS_FILTER_G,
BW_FILTER_NON, BW_FILTER_R, BW_FILTER_Y, BW_FILTER_G, SEPIA
```

与拍摄用枚举**顺序不同**（`F2` 在 `F1B` 前、`SUPERIA/ETERNA` 位置不同、末尾是 `SEPIA`）⇒ 两个 UI（拍摄菜单 / RAW 转换菜单）各有一套顺序，符合 Lead 的分族观察。

### 4.3 相关 SETP 设置项 ID（sec1 全局 ID 表）

| 名字 | id | 名字串偏移 |
|---|---:|---|
| `UI_SETP_FILM_SIM_SET` | 234 | `0x6FD074` |
| `UI_SETP_FUNCLOCK_FILM_SIM` | 745 | `0x700B20` |
| `UI_SETP_FILM_SIM` | **1070** | `0x702C98` |
| `UI_SETP_FILM_SIM_ACROS/_MONO/_MOVIE/_ACROS_MOVIE/_MONO_MOVIE` | 1071–1075 | `0x702CAC..` |
| `UI_SETP_FILM_SIM_SELECT` | 1076 | `0x702D30` |
| `UI_SETP_FILM_SIM_SELECT2` | 1077 | `0x702D48` |
| `UI_SETP_FILM_SIM_SELECT_1/2/3` | 1078–1080 | `0x702D64..` |
| `UI_SETP_FILM_SIM_2_SELECT_1/2/3` | 1081–1083 | `0x702DB8..` |
| `UI_SETP_FILM_SIM_SELECT_FILMSIM` | 1084 | `0x702E0C` |
| `UI_SETP_RAW_DEV_FSIM` | 1655 | `0x706B34` |
| `UI_SETP_DOTLCD_FILM_SIM` | 2047 | `0x709688` |

### 4.4 旧 `MODE_FSIM_*` 名字表（sec0，同样是 enum 定义序）

`sec0` 0x407934 起（1106/1108 同偏移），16 字节步进：`MODE_FSIM_STD, F1b, F1c, F2, B_AND_W,
SEPIA, CHROME, MONO_N/R/Y/G_FILTER, NEGA_COL_1, NEGA_COL_2, CLASSIC_CHROME,
ACROS_N/R/Y/G_FILTER, ETERNA, SUPERIA, BLEACH_BYPASS, MODE_FSIM_NUM`。
⇒ 这是**图像处理层的历史枚举**（含 `F1b/F1c/F2/NEGA_COL` 等别名），同样 **≠ 菜单顺序**，且与 §4.1 不完全一致。【强】

复现：`python tools/setp_decode.py filmsim`。

---

## 5. 显示名（Display Label）从哪来

### 5.1 资源位置

`decoded.bin` 里有 8 个 `FDL Font` 资源包魔数：`0x1DA0274, 0x2720274, 0x2780274, 0x28E0274,
0x29C0274, 0x2AA0274, 0x2B80274, 0x2BC0274`。第 1 个包（`0x1DA0274..0x2720274`，9.96 MB）
承载**全部语言/文本池**（UTF-16LE，NUL 结尾，4 字节对齐；池间用 `0xFF` 填充）。
`+0x40` 处唯一的一条 `"info"` 记录 = 字体元数据（`"ICON_NEW-UCS-CNS"`、`"Standard\Unicode\UCS-CNS"` 等），**不是**菜单目录。

### 5.2 胶片模拟标签是「复合记录」

英文池（`0x1EA0274..0x1ECE8A2`，7,782 条）中专门有一段胶片模拟标签（decoded `0x1EC8630..0x1EC8800`）：

```
0x1EC8630  '\uf3e5'                          ← 图标 PUA
0x1EC8634  'ETERNA BLEACH BYPASS'
0x1EC8660  '\uf3c4'
0x1EC8664  'CLASSIC Neg.'
0x1EC8680  '\uf2b9'
0x1EC8684  'CLASSIC CHROME'
0x1EC86A4  '\uf370'
0x1EC86A8  '\uf369/CINEMA'                   ← ETERNA/CINEMA（名字是 PUA logotype + /类型）
0x1EC86BC  'FILM SIMULATION'
0x1EC86E4  'MONOCHROME+G FILTER'
0x1EC8710  'MONOCHROME+R FILTER'
0x1EC8738  'MONOCHROME'
0x1EC8754  'MONOCHROME+Ye FILTER'
0x1EC8784  'PRO Neg. Hi'
0x1EC87A0  'PRO Neg. Std'
0x1EC87BC  'SEPIA'
0x1EC87CC  '\uf071/SOFT'                     ← ASTIA
0x1EC87E0  '\uf06f/STANDARD'                 ← PROVIA
0x1EC87FC  '\uf070/VIVID'                    ← VELVIA
```

`\uf06a/\uf06b/\uf06c` 是图标，`\uf06f/\uf070/\uf071` 是**名称为 logotype 的 PUA 字形**
（所以全镜像搜索 UTF-16 `"PROVIA"` **0 命中**——它被画成了字形而不是文本）。

### 5.3 文本池顺序 = 按消息 ID（≈按符号名字母序），**不是菜单顺序**

同一个英文池里还有一段**同一批标签的另一种排版**（`0x1EB94AC..0x1EB9664`，图标与文字直接连写成一个记录）。两段顺序一致，均为：`BLEACH → CLASSIC Neg. → CLASSIC CHROME → ETERNA → MONO… → PRO Neg… → SEPIA → ASTIA → PROVIA → VELVIA` —— 这是**消息 ID/符号名排序**，与相机菜单顺序不同。

### 5.4 后加的两种模拟

`NOSTALGIC Neg.`（`0x1E9E3AE` 等，70 处）与 `REALA ACE`（`0x1E9E38A` 等，70 处）
**不在**各语言主池里，而是在每个语言块之后**追加的小独立池**（如 `0x1E9E274`、`0x1EA0174`）。
这是「v2.x 固件追加胶片模拟」的典型痕迹。【强】

复现：`python tools/setp_decode.py labels`。

---

## 6. 「菜单显示顺序」的判定 —— 【未定位】

### 6.1 直接回答 Lead 的问题

- **sec1 里有没有找到「菜单/选项顺序」的显式结构？**
  **没有。** 找到的是：① 名字池；② `(name_ptr, index)` 枚举名表（index=枚举值）；③ `UI_SETP_*` 全局 ID 表。**没有**「选项 ID 数组」「菜单项定义表」这类按显示顺序排列的结构。
- **顺序是否由 ID 数值顺序隐含决定？**
  **否。** 枚举名表顺序（§4.1/4.2）与官方菜单顺序明确冲突（黑白/棕褐位置、缺少 3 个新模拟），所以「按枚举值递增显示」不成立。

### 6.2 已排除的假设（可供后续避免重复劳动）

| # | 假设 | 做法 | 结果 |
|---|---|---|---|
| 1 | decoded `0x460000-0x4A0000` 是 tokenized SETP 资源 | FFLZ 段头 + token 走查（§1） | **否决**（压缩流） |
| 2 | 名字池被 `u32` 指针直接引用 | 搜 `u32 == 名字偏移`；再搜 `base+偏移` | sec0: 0 命中；sec1: 命中注册表（§3） |
| 3 | sec0 名字池也有对应注册表 | 用 sec0 基址扫 `(ptr,id)` | 只有 1,254/24,620 被引用；`UI_FILM_SIM_*`/`MODE_FSIM_*` **0 引用** → 否决 |
| 4 | FDL 文本池顺序 = 菜单顺序 | 解析首个 FDL 包全部 UTF-16 串，逐组核对 | **否决**（按消息 ID/字母序） |
| 5 | 显示名字符串被 `u32/section 内偏移` 引用 | 对 13 个显示名，试 `u32 = off`、`off-包基址`、`off-候选基址` | 全镜像 **0 命中** ⇒ 文本按消息 ID 索引 |
| 6 | 顺序是 12–16 项「小整数枚举数组」 | 扫 sec0/sec1：`u8` 长度 12–24、值 ≤23、互异、首项 0；`u16` 同条件；再扫 `[0,1,2,…]` 前缀（u8/u16） | 只命中间距/插值/范围表（如 sec1 `0x7FDC50`、`0x8321E0`、sec0 `0x5CDA54`），**无菜单数组** |
| 7 | 顺序在「消息 ID 数组」里（假设 ID=池内序号） | 在 `4400..4445`、`6955..7000`、`7660..7700`、`5895..5930` 四个 band 内搜 `u16/u32` 数组，范围覆盖 sec0/sec1/sec2/sec3 + FDL 区 | 只命中升序范围表，**无菜单数组** |
| 8 | 顺序在 sec3（纯数据段） | sec3 里做 `[0,1,2]` 前缀 u8/u16 扫描 | 无 |

### 6.3 结论

- 固件**确实存在**两套「胶片模拟枚举」（§4.1/4.2）和一堆 `UI_SETP_FILM_SIM*` 设置项 ID，
  但**「显示顺序」不在这些结构里**；它最可能定义在 **UI 菜单/布局资源**（尚未定位）或
  **sec0 的 UI 构建代码**中（本任务未做反汇编闭环）。标【未定位】。
- 因此**不建议**用「改枚举名表顺序」来改菜单顺序：枚举名表只是 ID→名字的调试/反射表，
  改它不会改变显示顺序（反而可能破坏日志/调试），且当前也无法定位真正控制顺序的表。

---

## 7. 与官方手册的对照 & 实际显示顺序

### 7.1 官方手册给出的基础顺序（12 项）

官方 X-T4 手册 *IMAGE QUALITY SETTING → FILM SIMULATION* 的表格顺序
（<https://fujifilm-dsc.com/en/manual/x-t4/menu_shooting/image_quality_setting/index.html>）：

1. PROVIA/STANDARD
2. Velvia/VIVID
3. ASTIA/SOFT
4. CLASSIC CHROME
5. PRO Neg. Hi
6. PRO Neg. Std
7. CLASSIC Neg.
8. ETERNA/CINEMA
9. ETERNA BLEACH BYPASS
10. ACROS
11. MONOCHROME
12. SEPIA

【强】—— 与 §4.1 枚举顺序明显不同（枚举是 STD,F1B,F1C,F2,BW,SEPIA,CHROME,…）。

### 7.2 后加的 2 项

`NOSTALGIC Neg.`（v2.0x 追加）、`REALA ACE`（v2.1x 追加，公开资料确认 X-T4 支持
<https://saadnoor.com/photography/how-to-use-reala-ace-on-xt4/>）在固件里只以**追加文本池**
出现（§5.4）。它们在菜单中的插入位置**固件侧未证**，按新机型菜单同构推测：

```
PROVIA, Velvia, ASTIA, CLASSIC CHROME, PRO Neg. Hi, PRO Neg. Std,
CLASSIC Neg., NOSTALGIC Neg., ETERNA, ETERNA BLEACH BYPASS,
ACROS, MONOCHROME, SEPIA, REALA ACE
```

标【推测】：`NOSTALGIC Neg.` 位于 `CLASSIC Neg.` 之后，`REALA ACE` 追加末尾。
**不要**把该 14 项顺序当成固件已证结论。

### 7.3 未解映射（§4.1 里的 `?`）

`UI_FILM_SIM_F2(3)`、`UI_FILM_SIM_CHROME(6)`、`UI_FILM_SIM_SUPERIA(15)` 三个枚举槽没有直接
对应的复合显示标签；而 `CLASSIC Neg.`、`NOSTALGIC Neg.`、`REALA ACE` 有标签却没有同名枚举。
最可能：`SUPERIA`/`CHROME`/`F2` 是**历史枚举槽**，新模拟复用/重映射了其中若干槽，或新模拟
由 UI 层用「文本消息 ID」直接驱动、不走这套枚举。未闭环，标【未定位】。

---

## 8. 「交换两项」的安全性判断（若将来要做顺序实验）

| 目标 | 风险 | 说明 |
|---|---|---|
| 改 §4.1/4.2 枚举名表的字符串（如对调 `STD`↔`F1B` 的 name_ptr） | **高 / 无意义** | 它只是反射/调试名表，不会改菜单；还可能影响 `UI_SETP` 相关日志与查表 |
| 改 FDL 文本池里的标签顺序 | **高 / 无效** | 文本按消息 ID 索引，重排池内顺序会打乱全部语言/屏幕的文本映射 |
| 改 `UI_SETP_*` 全局 ID（1070 等） | **极高** | ID 被代码/资源广泛引用，改号会级联破坏 |
| 直接改「菜单顺序数组」 | **当前不可行** | 数组未定位（§6） |

⇒ 在定位真正的 UI 菜单资源前，**不建议做任何「换序」补丁**。

---

## 9. 未解 / 下一步

| # | 问题 | 建议 |
|---|---|---|
| 1 | 菜单显示顺序的**显式表**在哪 | 反汇编 sec0 中「构建 FILM SIMULATION 选项列表」的函数；锚点：`UI_SETP_FILM_SIM`=1070、`UI_MENUCOM_ITEM_FILM_SIM`=34（`UI_MENUCOM_ITEM_*` 枚举表 @sec1 `0x6CDE30`，478 项） |
| 2 | `F2/CHROME/SUPERIA` ↔ `CLASSIC Neg./NOSTALGIC Neg./REALA ACE` 的映射 | 找「枚举值 → 文本消息 ID」映射表（长度 14/23 的密集小整数数组，尚未命中） |
| 3 | FDL 消息 ID 的精确语义（池内序号？子表序号？） | 解析 FDL 包中语言池的边界与索引结构，做「同一 ID 跨语言一致性」验证 |
| 4 | `UI_MENUCOM_ITEM_*`（478 项）是否就是菜单项顺序 | 若已按菜单顺序，可作为菜单结构证据；需核对 `IMAGE SIZE→QUALITY→RAW→FILM SIM` 等已知顺序 |
| 5 | 1108 vs 1106 vs 官方 v2.12 的差异落点 | Lead 已确认上述枚举/名字表**未变**；差异在 sec0 `0x6ED432`(46,606 B)、sec1 `0x6C6D20`(736 B) 等别处，与本任务结论无关 |

---

## 10. 复现

```powershell
$py = "C:\Users\90732\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"

& $py tools\setp_decode.py verify    # 证明"tokenized 区"= FFLZ 压缩流（§1）
& $py tools\setp_decode.py pools     # 两段的 ASCII 名字池 + 段头基址（§2）
& $py tools\setp_decode.py registry  # 8 字节 (name_ptr,index) 注册表/枚举名表（§3）
& $py tools\setp_decode.py filmsim   # 两张胶片模拟枚举表 + SETP ID（§4）
& $py tools\setp_decode.py labels    # FDL 复合标签（§5）
& $py tools\setp_decode.py all       # 全部
```

产物只读：不写 `.DAT`；输出到 stdout（可重定向到 `out/`）。
`tools/setp_explore*.py` 是本次探索过程中的一次性脚本，保留供追溯（不参与结论复现）。
