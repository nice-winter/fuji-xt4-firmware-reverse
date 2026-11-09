# 11 — 胶片模拟「槽位」定位与菜单顺序可调整性分析（1108）

> 目标固件：`FWUP0024_affix_1108.DAT`（X-T4，os=6，v2.12 派生；逻辑镜像 `out/f1108/decoded.bin`，解压段 `out/f1108/sections/sec*.bin`）
> 对比样本：官方 v2.12（`out/fofficial/`）与 1106（`out/f1106` 可自行生成）
> 结论标记：**【确证】/【强】/【推测】/【未定位】**

---

## 0. 结论摘要（先看这里）

| # | 结论 | 强度 |
|---|---|---|
| 1 | 胶片模拟在固件里分**三层**：① 模式枚举名表 `MODE_FSIM_*`（sec0 `0x407934`，**19 个值**，末尾 `MODE_FSIM_NUM`）② UI 名字表 `UI_FILM_SIM_*` / `UI_RAW_DEV_FILM_SIM_*` / `UI_SETP_FILM_SIM*`（sec1 `0x6EAC24` / `0x6F3570` / `0x702CA0`，sec0 `0x44FB24`）③ 显示文本（FDL Font 文本池里的复合标签，带 PUA 前缀的消息 ID） | 确证 |
| 2 | **枚举顺序 ≠ 菜单顺序**。枚举是 `STD, F2, B_AND_W, SEPIA, CHROME, MONO_N/R/Y/G, NEGA_COL_1, NEGA_COL_2, CLASSIC_CHROME, ACROS_N/R/Y/G, ETERNA, SUPERIA, BLEACH_BYPASS`（19 项，含滤镜变体）；而菜单是 `PROVIA→Velvia→ASTIA→CLASSIC CHROME→PRO Neg Hi→PRO Neg Std→CLASSIC Neg→NOSTALGIC Neg→ETERNA→BLEACH→ACROS→MONOCHROME→SEPIA`。两者对不上 ⇒ 菜单顺序**另有来源**。 | 确证 |
| 3 | **没有找到"13/14 项枚举/ID 顺序数组"**。已穷举扫描：sec0/sec1 里 13/14 项 `0..N` 排列表、u16 消息 ID 数组、u32 指针表、文本池索引表 —— 命中的都是别的用途（二维读取/插值图案、字符串索引表等）。⇒ 菜单顺序**不是**靠一个能直接交换的小数组定义的。 | 确证（扫描结果）/ 未定位（来源） |
| 4 | 显示文本层：FDL 文本池里，选项标签是**复合字符串**（示例 `\uf2fa\uf2ef+G FILTER`、`\uf3e5ETERNA BLEACH BYPASS`、`\uf06c\uf071/SOFT`、`\uf3c4CLASSIC Neg.`、`\uf370\uf369/CINEMA`），前缀 PUA 字符即**内嵌图标/子字符串引用**；池内顺序≈按消息 ID 排序，**不是**菜单顺序。 | 强 |
| 5 | 官方 v2.12 与 affix_1108 的**三层名字表偏移与内容完全一致**（未改动）；两构建差异集中在 sec0 `0x6ED432`（46,606 B）与 sec1 `0x6C6D20`（736 B）等别处。→ 想靠"对比官方/二改找出顺序表"这条路走不通。 | 确证 |
| 6 | **可行性判断**：菜单顺序**理论上可改**，但必须先定位「UI 资源里的选项列表（SETP/菜单定义）」；**改枚举值顺序不可取**（会牵连出图参数、EXIF、RAW 处理）。当前状态：**选项列表未定位**，因此"直接交换顺序"尚不可执行。 | — |

---

## 1. 三层结构的具体位置（1108 与官方 v2.12 相同）

### 1.1 模式枚举名表（sec0 `0x407934`）

`MODE_FSIM_*` 共 20 个名字，最后一个 `MODE_FSIM_NUM` 是**计数**：

```
0x00407934 MODE_FSIM_STD              0x00407A58 MODE_FSIM_ACROS_N_FILTER
0x00407964 MODE_FSIM_F2               0x00407A74 MODE_FSIM_ACROS_R_FILTER
0x00407974 MODE_FSIM_B_AND_W          0x00407A90 MODE_FSIM_ACROS_Y_FILTER
0x00407988 MODE_FSIM_SEPIA            0x00407AAC MODE_FSIM_ACROS_G_FILTER
0x00407998 MODE_FSIM_CHROME           0x00407AC8 MODE_FSIM_ETERNA
0x004079AC MODE_FSIM_MONO_N_FILTER    0x00407ADC MODE_FSIM_SUPERIA
0x004079C4 MODE_FSIM_MONO_R_FILTER    0x00407AF0 MODE_FSIM_BLEACH_BYPASS
0x004079DC MODE_FSIM_MONO_Y_FILTER    0x00407B08 MODE_FSIM_NUM
0x004079F4 MODE_FSIM_MONO_G_FILTER
0x00407A0C MODE_FSIM_NEGA_COL_1        ← Classic Neg. 类
0x00407A24 MODE_FSIM_NEGA_COL_2        ← Nostalgic Neg. 类
0x00407A3C MODE_FSIM_CLASSIC_CHROME
```

要点：
* **19 个有效值**（0..18）+ 1 个计数名；
* 滤镜（`.+R/+Y/+G/+Ye`）在枚举里是**独立值**，占多个槽位；
* 该表是**名字表**（调试/日志用），名字没有被 u32 指针引用（全文件搜索其偏移无命中）⇒ 枚举值大概率就是**表内序号**，由代码按下标取名字。

### 1.2 UI 名字表（sec1 / sec0）

| 位置 | 内容 |
|---|---|
| sec1 `0x6EAC24..0x6EAE68` | `UI_FILM_SIM_*`：STD, F1B, F1C, F2, BW, SEPIA, CHROME, BW_FILTER(+NON/R/Y/G), PRONEGA_S, PRONEGA_H, CLASSIC_CHROME, SUPERIA, ETERNA, BLEACH_BYPASS, ACROS_FILTER(+NON/R/Y/G), SELECT_1..3 |
| sec1 `0x6F3570..0x6F3790` | `UI_RAW_DEV_FILM_SIM_*`（RAW 转换菜单用）：STD, F2, F1B, CLASSIC, F5A, F5, SUPERIA, ETERNA, BLEACH_BYPASS, ACROSS_FILTER_NON/R/Y/G, BW_FILTER_NON/R/Y/G, SEPIA |
| sec1 `0x702CA0..0x702D80` | `UI_SETP_FILM_SIM*`：SETP 定义名（`UL_SETP_FILM_SIM`, `..._ACROS/_MONO/_MOVIE/_SELECT...`） |
| sec0 `0x44FA84..0x44FD84` | 同族 + 设置框架哨兵：`..._SET_ON/_SET_OFF/_SET_VAL_MAX/_SET_VAL_IGNORE_SET/_SET_VAL_BACKUP_GET/_SET_VAL_PREV_GET`、`..._VAL_MAX/_VAL_IGNORE_SET/...` |

> `SET_VAL_MAX / VAL_IGNORE_SET / VAL_BACKUP_GET / VAL_PREV_GET` 这类命名说明胶片模拟是一个**标准 SETP 设置项**（有 ON/OFF、max、忽略设置、备份/上次值等），因此它的"可选项集合与顺序"应由 **SETP 资源**定义。

### 1.3 显示文本层（FDL Font 文本池）

* 每个语的文本池在 decoded `0x1E7xxxx..0x270xxxx` 一带；标签是**复合串**：
  ```
  0x01EB9458  '\uf2fa\uf2ef+G FILTER'      ← ACROS + G 滤镜
  0x01EB9470  '\uf2f7\uf2ef'
  0x01EB9478  '\uf2f9\uf2ef+R FILTER'
  0x01EB9490  '\uf2f8\uf2ef+Ye FILTER'
  0x01EB94AC  '\uf3e5ETERNA BLEACH BYPASS'
  0x01EB94D8  '\uf06c\uf071/SOFT'          ← ASTIA/SOFT
  0x01EB94E8  '\uf3c4CLASSIC Neg.'
  0x01EB9504  '\uf370\uf369/CINEMA'        ← ETERNA/CINEMA
  0x01EB9518  'FILM 1' / 'FILM 2' / 'FILM 3'
  0x01EB9548  '\uf1b5MONOCHROME+G FILTER'
  ```
* 行首 `\uf0xx–\uf4xx` 是 PUA 码位，作用是**引用其它字符串/图标字形**（如 `\uf2ef` 在多条标签里重复出现 = 同一子串引用）。
* 该池是**按消息 ID/索引排序**的字符串表（我们已验证：池内相邻条目的索引连续、且有"跳号"= 空槽）。

### 1.4 文本池索引表（重要新发现）

sec1 `0x85F26C..0x85F4AE` 有一段 **连续 u16 索引数组**（4300,4301,…,4312,4314,…），即"逻辑序号 → 池内索引"的映射表，其中**跳号（4313/4328/4344/…）应该就是空槽/未使用条目**。
⇒ 这印证了：**UI 通过"索引"访问字符串**，所以"菜单顺序"必然是**某处的一组索引/ID 序列**（或由 SETP 定义中的选项列表给出）。

---

## 2. 为什么可以直接断定「枚举顺序 ≠ 菜单顺序」

| 枚举顺序（MODE_FSIM，19 项） | 实际菜单顺序（13 项） |
|---|---|
| STD(0), F2(1), B_AND_W(2), SEPIA(3), CHROME(4), MONO_N..G(5..8), NEGA_COL_1(9), NEGA_COL_2(10), CLASSIC_CHROME(11), ACROS_N..G(12..15), ETERNA(16), SUPERIA(17), BLEACH(18) | PROVIA, Velvia, ASTIA, CLASSIC CHROME, PRO Neg Hi, PRO Neg Std, CLASSIC Neg, NOSTALGIC Neg, ETERNA, ETERNA BLEACH BYPASS, ACROS, MONOCHROME, SEPIA |

* 枚举里滤镜单独占槽，菜单里滤镜是"ACROS/MONOCHROME 的子选项" → 菜单是**另一套展示结构**；
* 菜单前 4 项（PROVIA/Velvia/ASTIA/CLASSIC CHROME）在枚举里是散开的；
* 因此菜单顺序**必须**来自 UI 层的选项列表（或代码里的显式列表），而不是枚举。

---

## 3. 已经排除的假设（避免重复劳动）

| 假设 | 做法 | 结果 |
|---|---|---|
| 存在 13/14 项 `0..13` 枚举顺序数组 | 全 sec0/sec1 扫 `set(blk)==set(range(13/14))` | 命中均为其它用途（`[0,1,2,3,8,9,10,11,4,5,6,7,12,13]` 等与相邻 `[0,1,4,5,...]` 成对出现，是二维读取/插值图案） |
| 存在 `u16` 消息 ID 顺序数组 | 用「名字串前 2/4/6 字节」反推 ID，再扫含 ≥8 个 ID 的数组 | sec0/sec1/sec2/sec3 均 0 命中 |
| 存在 `u32` 指针表指向名字串 | 全文件搜 `u32 == 名字偏移` | 0 命中（说明名字表靠下标访问，不靠指针） |
| 顺序表在官方 vs 二改差异里 | 解压官方 v2.12 与 1108 后逐字节 diff | 名字表/枚举表**完全未改**；差异在 sec0 `0x6ED432` 等别处 |
| 顺序 = 文本池顺序 | 解析文本池顺序 | 池按索引升序排列，不是菜单顺序 |

---

## 4. 可调整性判断与风险

### 4.1 三种"改顺序"的方式

| 方式 | 可行性 | 风险 |
|---|---|---|
| **A. 改 UI 资源的选项列表**（把选项 ID 顺序重排） | **首选**，但**必须先定位该列表**（当前未定位） | 低：显示顺序变、参数跟随 ID 走（前提是列表只用于显示/遍历） |
| **B. 交换两个枚举值对应的"功能映射"** | 不可行 | 高：枚举值贯穿出图参数、EXIF FilmMode、RAW 处理、包围曝光（`MODE_CONTINUOUS_FSIM_BRACKET`）等，交换会串档 |
| **C. 交换显示标签（把 A 的标签指向 B 的名字）** | 可行（改文本池） | 高：菜单文字与实际出图**不一致**，属于欺骗性改动，不建议 |

### 4.2 结论

* **不能**靠改几个字节直接换顺序（没有找到这种表）；
* 菜单顺序由 UI 层（SETP/菜单定义资源）决定；**把该资源里的选项序列找到后，交换两个条目是低风险操作**（因为参数/EXIF 跟的是选项 ID，不是顺序位置）；
* 在找到该列表之前，**不建议**动任何东西——现有证据都是否定的。

---

## 5. 下一步（可执行的三个实验）

1. **解析 sec1 的 UI 资源**（0x6C0000–0x710000 一带）：
   * 已确认里面有大量 `UI_*` 名字 + 连续索引表；先按「记录 = {u16 id, u16 count, …}」猜结构，用"索引表 0x85F26C 的跳号"做校验；
   * 目标：找到 `UI_SETP_FILM_SIM` 对应的**选项列表**（期望长度 13，元素是模式枚举值/索引）。
2. **反汇编 sec0 里引用 `MODE_FSIM_NUM` 的函数**：看它是 `for(i=0;i<NUM;i++)` 遍历（⇒ 顺序=枚举，改不了显示顺序），还是从某个列表取值（⇒ 列表可改）。这一步能直接定性。
3. **最小实验验证**（风险可控）：
   * 在文本池里把两个**标签**互换（例如把 `CLASSIC Neg.` 的标签文本换成 `ACROS`），生成固件、上机看菜单文字是否跟着变；
   * 若文字变了而出图不变 ⇒ 证明显示层可独立改（方式 C 的路径），再去找"顺序列表"就能安全重排。

---

## 6. 附：本次新增的分析脚本

| 脚本 | 用途 |
|---|---|
| `tools/decode_any.py` | 任意 FWUP0024 type-6 固件 → 逻辑镜像 + 4 个 FFLZ 段（1108 已生成 `out/f1108/`） |
| `tools/filmsim1108.py` / `filmsim1108_b.py` | 1108 里胶片模拟名字表/文本池定位 |
| `tools/fsim_order_seek.py` | 找"顺序表"的多种假设（含 19 项枚举指纹） |
| `tools/fsim_diff_official.py` | 官方 v2.12 vs 1108 的段内 diff（聚焦胶片模拟结构） |
| `tools/fsim_index_arrays.py` | 文本池索引表/索引数组扫描 |
| `tools/filmsim_perm1108.py` | 13/14 项排列表穷举 |

> 原始 `.DAT` 全程只读；1108 的派生数据在 `out/f1108/`，官方对照在 `out/fofficial/`。

---

## 7. 补充：setp-parser 的独立结果（已并入结论，细节见 `09-setp-resource.md`）

**重大方法突破**：解压段头前 20 字节里有**加载基址**（第 2 个 u32）与段长（第 3 个 u32）：
`sec0 base=0x01021000 size=0x714000`、`sec1 base=0x01E0F000 size=0x900000`。
有了基址才能把「绝对虚拟地址引用」解出来（此前搜裸偏移当然 0 命中）。

由此得到的 **sec1 注册表结构【确证】**：
```
每条 8 字节： {u32 name_ptr_VA ; u32 index}
表范围 sec1 0x6C8150 .. 0x6D8AA0（7,774 条 / 702 张枚举名表）
表内 index 从 0 开始 ⇒ **index 就是枚举值**
```

**两张胶片模拟枚举名表（枚举值 = 表内下标）**：

| 用途 | 表位置(sec1) | 项数 | 顺序（枚举 0..N） |
|---|---|---|---|
| 拍摄 `UI_FILM_SIM_*` | `0x6D35F8..0x6D36A8` | **23** | STD, F1B, F1C, F2, BW, SEPIA, CHROME, BW_FILTER(+NON/R/Y/G), PRONEGA_S, PRONEGA_H, CLASSIC_CHROME, SUPERIA, ETERNA, BLEACH_BYPASS, ACROS_FILTER(+NON/R/Y/G) |
| RAW 开发 `UI_RAW_DEV_FILM_SIM_*` | `0x6D6430..0x6D64B8` | **18** | STD, F2, F1B, CLASSIC, F5A, F5, SUPERIA, ETERNA, BLEACH_BYPASS, ACROSS_FILTER(NON/R/Y/G), BW_FILTER(NON/R/Y/G), SEPIA |

**关键 SETP ID**：`UI_SETP_FILM_SIM = 1070`、`_SELECT = 1076`、`_SELECT_1 = 1078`、`_SELECT_2_SELECT_1 = 1081`、`UI_SETP_RAW_DEV_FSIM = 1655`；
`UI_MENUCOM_ITEM_FILM_SIM = 34`（478 项 `UI_MENUCOM_ITEM_*` 表在 sec1 `0x6CDE30`）——这是下一步最值得反汇编的锚点。

**显示标签的真实构成【确证】**：`PROVIA / Velvia / ASTIA` 的"名字"是 **PUA logotype 字形**（`\uf06a\uf06f/STANDARD`、`\uf06b\uf070/VIVID`、`\uf06c\uf071/SOFT`），所以全镜像直接搜 UTF-16 "PROVIA" 是 0 命中——这也解释了为什么它们看起来"没有字符串"。

**对第 4 节结论的修正**：第 1.1 节列出的 `MODE_FSIM_*` 名字块只是**名字排列**，不是权威枚举值；**权威枚举顺序以上表（注册表 index）为准**（23 项，含滤镜独立槽），它与菜单顺序依然不同 ⇒ 第 2 节结论不变。

### 7.1 sec0 代码侧扫描（`tools/filmsim_scan.py`，可复现）

该脚本对 sec0（1108 与 1106 两个构建）扫描"胶片模拟枚举表形状"的连续小整数，并尝试用 ARM 字面量池指针找引用。当前结果（score≥100 的 30 个候选）：

* 绝大多数是 `0c 0b 0a 09 ... 00`（**倒序初始值数组**）或 `00 01 02 ... 1d`（**升序初始化表**），明显是别的用途（初始化/查表）；
* 唯一"接近 19 项"的候选：`0x65e2d0`(u16,19) / `0x65eca8`(u16,19) / `0x65f0bc`(u8,19)
  `10 11 12 00 08 07 09 06 0a 05 0b 04 0c 03 0d 02 0e 01 0f`
  —— 这正好是 **19 项**（与 MODE_FSIM 值数一致），但顺序是"3 组交错/锯齿"，更像**网格光标行走顺序**（2 列/3 列排布的导航顺序），而不是官方菜单顺序；
* 官方 v2.12 与 1108 的候选表**完全一致**（同一批偏移/内容）⇒ 二改没有动这类表。

⇒ 与 setp-parser 的结论一致：**sec0 内没有找到"按官方菜单顺序排列"的 13 项数组**；排列表候选都指向别的 UI 网格/初始化用途。


