# 16 — FDL Font 字形/位图提取：PUA 图标 → PNG + sprite sheet

> 目标：`FWUP0024_affix_1108.DAT`（X-T4 二改，os=6，v2.12 派生）；逻辑镜像 `out/f1108/decoded.bin`
> 对照：`out/fofficial/decoded.bin`（官方）
> 全程**只读**两个 `.DAT`（只 `open(...,"rb")`），产物只写 `out/glyphs/`、`out/_glyph_p*.txt`、`tools/fdl_glyphs.py`
> 工具：`tools/fdl_glyphs.py`（`report` / `export`）；探针：`tools/_glyph_p1..p19.py`
> 标记：【确证】= 双向验证 / 精确断言；【强】= 多项独立证据；【推测】= 未证实。

---

## 0. 结论摘要（先看这里）

| # | 结论 | 强度 |
|---|---|---|
| 1 | **字形不是位图，是矢量轮廓**（stroke/path 指令流）。之前笔记 14 里“+0x39E00 的 u32 表 / 0x00593000 空字形”是对同一条目表的**错位解读**。 | 确证 |
| 2 | **字形偏移表**：bundle+`0x384D4`..`0x3DCEC`，**5638 条 × 4B**，格式 `{u8 flag, u24 end_offset}`（LE）。end_offset 单调不减；`last = 414,933` = 字形数据区长度；表尾 +1 字节 pad 后即数据区。 | 确证 |
| 3 | **字形数据区**（blob）：bundle+`0x3DCED`..`0xA31C2`，`414,933 B`；**正好接在 `info` payload 之前**（`0x3DCED+0x654D5 = 0xA31C2`）。 | 确证 |
| 4 | **cmap = `glyph_id = 码位 - 0xE120`**。表 5638 条 ⇒ 覆盖 `U+E120..U+F725`；简体中文池里实际用到的 **394 个 PUA 码位**的 min/max 跨度恰为 `5637 = 5638-1`，且 **394/394 全部落在“有轮廓”的字形上**（随机命中概率 ≈ 0.21³⁹⁴ ≈ 0）。 | 确证 |
| 5 | **字形记录 framing**：`simple = {u16 0x00FA, u16 len, data[len]}`；`complex = {u16 flags, u16 advance, u16 n, <chunks>}`（chunk = `{u16 0x00FA,u16 len,data}`，可多段拼接）；`empty = {u16 flags,u16 advance,0,0}`。无 `unknown`，4439 空 + 930 simple + 269 complex = 5638。 | 确证 |
| 6 | **路径指令集**（11 个 opcode，变长）：`B5/92/96 = [op][arg][x][y]`（1 点）；`9A/9B/9E/9F = [op][arg][count][(x,y)×count]`；`03/07/70 = [op][arg]`；`35 = [op][arg][u16][u16]`（罕见）。按此文法 **1187/1199** 条有轮廓的字形可完整解析（12 条用到 `0x35` 特殊形式/截断）。 | 强 |
| 7 | 坐标系：画布 **256×256**（x,y 均为 1 字节，实测 0..254），y 轴方向未最终确认（导出同时给了原样/可翻转两版）。单元格在 12B 布局条目里记为 100×100。 | 强 |
| 8 | **渲染语义仍有不确定**：`0x92/0x96` 的点是 on-curve 还是控制点、`arg` 的语义（同一字形里 arg 呈 `(i,i+1)` 递增，像“点序号”而非几何量）、轮廓内点序/填充规则均未定。因此导出提供 **fill / stroke 两种 sprite**，几何（点坐标、轮廓分段、轮廓数）是可信的，绘制细节标【推测】。 | 推测 |
| 9 | 提取结果：394 个 PUA 码位 → **391 个成功导出 PNG**（3 个是设计上的空字形：`U+E120`、`U+F1CA`、`U+F1DB`，只有 advance 没有轮廓）。 | 确证 |

---

## 1. 包内几何（bundle #0，decoded `0x1DA0274`，长 `0x980000`）

复现：`python tools/fdl_glyphs.py report` → `out/glyphs/fdl_glyph_report.txt`

```
bundle+0x00000  "FDL Font\0"
bundle+0x0001C  36B 描述区：
                26 f7 4c 00 | 00 00
                | off=0x3DCED id=0x4E pad=0
                | off=0x3DCED id=0x51 pad=0
                | off=0x3DCED id=0x04 pad=0x0100
                | off=0xA323E id=0
                ← 3 个记录都指向「字形表末尾/数据区起点」0x3DCED，
                  最后一个指向「info payload 末尾」0xA31C2+0x7C=0xA323E
bundle+0x00040  "info" + {u32 off=0xA31C2, u32 size=0x7C}
bundle+0x384D4  字形偏移表 5638×4B            ← 0x80..0x384D4 全 0
bundle+0x3DCED  字形数据区 414,933 B
bundle+0xA31C2  info payload（ICON_NEW-UCS-CNS / Standard\Unicode\UCS-CNS / 0100 / 202212201341）
bundle+0xA323E  u16 度量表（advance 类数值：0x0258=600, 0x0320=800, 0x03E8=1000, 0x0190=400 …）
bundle+0xC0000  8B 标签记录表 {u16 style=MSG_STYLES, u16 1, u32 text_off}
bundle+0xE99xx  共享 UTF-16 文本池（例：0xE4000 日语文本）
0x1E9E000       35 个 0x40000 语言块
```

**官方 vs 二改**：偏移表**表头完全相同**；二改在 blob 内 `bundle+0x9DAE9`（= blob offset 392,700）**插入 477 (=0x1DD) 字节**新字形数据，因此
info payload 从官方 `0xA2FE5` 后移到 `0xA31C2`（差 0x1DD），官方 blob 长 `0xA2FE5-0x3DCED = 414,456`，二改 `414,933 = 414,456+477` ✓。
这也解释了 diff 只出现 5 段：插入点之后的内容整体平移（+0x3D169 段 = 被改写的表尾 736 条）。

---

## 2. 字形偏移表（loca 等价物）

```
表项 (4B, LE): { u8 flag, u24 end_offset }
  end_offset = 该字形记录在 blob 内的**结束**偏移（累计量）
  字形 i 的记录 = blob[end[i-1] .. end[i])   (i=0 时起点 0)
  end[5637] = 414,933 = blob 长度（已与 info 起点对齐验证）
```
* `flag` 只有 0/1 两个值（0: 5361 条，1: 277 条，1 集中在索引 0..276 与个别末尾）。语义未知【推测：字形类别（是否为“组件/复合”字形）】。
* 5637 个 delta 中 **4431 个为 0** ⇒ 4431 个字形 id 与前一 id 共用同一偏移（= 没有独立轮廓的空字形）；**1206 个 delta > 0** ⇒ 1206 个独立记录。
* 记录种类统计（全 5638 个 id）：`empty 4439 / simple 930 / complex 269 / unknown 0`。

---

## 3. 字形记录格式

全部 little-endian：

```
simple : u16 0x00FA | u16 len | data[len]                       ← 1 段
complex: u16 flags  | u16 advance | u16 n | <chunks, 共 n 字节>   ← 可多段
chunk  : u16 0x00FA | u16 len | data[len]      （chunk 可连续出现，data 需拼接）
empty  : u16 flags  | u16 advance | 0x0000 | 0x0000               ← 6B，只有 advance
```
* `simple` 等价于「只有 chunk 的 complex」，所以实现里统一按 chunk 流解析。
* `complex.flags` 实测 ∈ {0,1,2,3,4,6,0xFFFF}【语义未知】。
* `complex.advance` / `empty.advance` ∈ {208,408,409,415,416,500,625,818,826,830,831,833,834,1000}；
  500 出现 191 次、1000 出现 36 次；单位【推测】1/1000 em。
* 大字形会被切成多段（例：gid 4507 记录 828B = `FA/178` + `FA/642` 两 chunk）。

---

## 4. cmap：`glyph_id = 码位 - 0xE120`【确证】

证据链：
1. 表长固定 5638；SC 池里 394 个 PUA 码位 min=`U+E120`、max=`U+F725`，**max-min = 5637 = 5638-1**；
2. 在 `base=0xE120` 下 394 个 id 全部 **0..5637**，且 **394/394 命中“有轮廓”的字形**（有轮廓 id 只占全表 21.4%）；
3. 备注 14 里点名的码位也全部落在有轮廓字形上：`U+F1B5→4245`、`U+F1B3→4243`、`U+F1B4→4244`、`U+F2EF→4559`、`U+F2F7..F2FA→4567..4570`、`U+F06D→3917`、`U+F06A→3914`、`U+F06F→3919`、`U+F056→3894`、`U+F445→4901`（二改新增 REALA）、`U+F3EE→4814`（二改新增 NOSTALGIC）；
4. 未用到的码位落在“共用偏移的空字形”区间，与“字体按连续码位区间建表、未定义者给空轮廓”一致。

> 因此前端只需 `id = cp - 0xE120` 即可定位字形；**不需要额外 cmap 表**（包里也确实没有）。

---

## 5. 路径指令集（path byte stream）

| opcode | 形式 | 字节数 | 说明 |
|---|---|---|---|
| `0xB5` | `[B5][arg][x][y]` | 4 | arg 只见到 `0x00` 和 `0x10`；`B5 00` 恒为「轮廓起点」(moveTo)，`B5 10` 恒为紧随其后的第 2 点 |
| `0x92` | `[92][arg][x][y]` | 4 | 1 点；arg 在同字形内常呈 `02,23,34,45…`（(i,i+1) 递增） |
| `0x96` | `[96][arg][x][y]` | 4 | 1 点；同上 |
| `0x9A` | `[9A][arg][cnt][(x,y)×cnt]` | 3+2·cnt | cnt 全为**偶数**（2/4/6/8/10/12/14/16） |
| `0x9B` | `[9B][arg][cnt][(x,y)×cnt]` | 3+2·cnt | cnt 全为**奇数**（1/3/5/7/9/11/15） |
| `0x9E` | 同 0x9A | 3+2·cnt | cnt 偶数 |
| `0x9F` | 同 0x9B | 3+2·cnt | cnt 奇数 |
| `0x03` | `[03][arg]` | 2 | 轮廓终止（arg 形如 `0x_1`，高 nibble 递增） |
| `0x07` | `[07][arg]` | 2 | 字形/轮廓终止（绝大多数字形以此结尾） |
| `0x70` | `[70][arg]` | 2 | 轮廓终止（arg 恒 0x00） |
| `0x35` | `[35][arg][u16][u16]` | 6 | 罕见（12 条路径），未解；出现即视为“跳过” |

* 解析率：**1187/1199 条有轮廓字形完整解析**（12 条含 `0x35` 或字节截断，导出时记为 fail）。
* 轮廓切分：`B5 00` 起新轮廓；`03 / 07 / 70` 结束轮廓；其余指令的点按出现顺序追加到当前轮廓。
* 点坐标：1 字节 x、1 字节 y，实测 0..254，画布按 **256×256** 处理。
* 典型轮廓（4 点矩形件，如 `U+E12D` 一类）：
  `B5 00 (124,8) | B5 10 (142,120) | 92 02 (142,8) | 03 21 | 96 03 (124,120) | 07 31`
* 弧线用 `0x9A/0x9B/0x9E/0x9F` 的连续点近似（例：`9A 02 08` + 8 点 = 一段圆角/圆弧，点序平滑，证明 run 内点序正确）。

### 5.1 仍未定（**这是本任务的遗留难点**）
1. `0x92/0x96` 的 arg.nibble 呈 `(0,2),(2,3),(3,4)…(9,A)` 递增，看起来像**运行点序号**而不是几何量；其点也可能是**控制点**（二次 Bézier）。未找到反例可判定。
2. 同一轮廓内点序：对 4 点“矩形件”，存储顺序是 `(左上, 右下, 右上, 左下)`，直接连成多边形会形成**蝴蝶结**；若按 `p0,p2,p1,p3` 重排则是正常梯形。说明 **arg 里很可能带有连接顺序信息**（或 `03` 之后的点应插到 `B5 10` 前）。
3. `fill` vs `stroke`：两种都导出。`fill` 更接近“实心图标”，但受 (2) 影响会出现楔形空洞；`stroke` 现有产物看起来更像线稿图标。
4. 手上有力证据但未用的下一步：**用 `sec1` 里的 ARM32 渲染器**（找引用 `0x1DDxxxx` 字形表/`0x...` 度量的代码，反汇编 opcode 分派）可 10 分钟内定死 (1)(2)(3)。定位提示：字形表 decoded `0x1DD8748`（=bundle+0x384D4），blob `0x1DDDF61`，info `0x1E43436`；需要先把 decoded→运行时地址映射（note 02：sec0 域 ≈ `0x00Exxxxx`）确定。

### 5.2 做过的否定实验（避免重复走弯路）
* **“按质心角度排序点序”**（试图把 4 点矩形还原成正常梯形）：对 `U+F1B5/U+F445/U+F3EE/U+F06D/F2FA/F056` 等图标反而更差
  （凸包排序会丢掉真正的凹陷/开口），产物留在 `out/_preview_ordering_test.png`（第 2/4 行）。⇒ 点序本身**不是**简单的乱序，arg 承载的是更细的连接/曲线信息。
* **“按 u32 读偏移表”/“按固定 4B 指令切路径”**：分别在 §7.1/§7.3 记录，均为错误方向。
* **“fill 用角度排序、stroke 用原序”混合**：四组对照见 `out/_preview_ordering_test.png`，raw-fill / raw-stroke 仍是最接近图标观感的两版。
* 观感提示：raw-fill 的锯齿/条纹不是噪声 —— 该字体的图标轮廓本身常以**细长锯齿条**表示实心条带（例如 `U+E12D` 是一条斜向条带），
  在小尺寸下 fill 后即成为实心；只是部分字形因 (1)(2) 仍有跨接长线。


---

## 6. 提取结果（`out/glyphs/`）

```
out/glyphs/
  glyph_UE120_fill.png … glyph_UF725_stroke.png   每码位 2 张（fill / stroke），共 391×2 = 782 张
  sprite_fill.png    + sprite_fill.json            20 列网格，格子 cell_w×cell_h
  sprite_stroke.png  + sprite_stroke.json
  glyph_index.tsv   codepoint / glyph_id / kind / advance / ncontours / npoints / bbox256 / decoded
  glyph_map.json    {"0xf1b5": {gid, kind, advance, ncontours, npoints, bbox, decoded}, ...}
  preview_known_icons.png   10 个已知图标（含二改新增 REALA/NOSTALGIC）的 fill/stroke 对照
  fdl_glyph_report.txt
```

JSON 约定（`sprite_*.json`，键 = `"0x<小写码位>"`）：
```json
{ "0xf2ef": {"x":123,"y":45,"w":211,"h":198,"cell_w":219,"cell_h":206,
             "ox":30,"oy":17 } }
```
* 图中图标实际像素 = `(x, y, w, h)`；
* `ox/oy` = 该字形内容在原始 **256×256 画布**内的左上角（前端若要“同基线对齐”，把图标按 `ox/oy` 放回 256 网格即可，缩放 `100/256` 就是 100×100 单元格下的位置）；
* `cell_w/cell_h` 便于调试网格。

统计：`decoded=391`，失败/空 = 3（`U+E120`、`U+F1CA`、`U+F1DB` —— 只有 advance 的空字形，非解析失败）。
所有 394 个码位都写进了 `glyph_index.tsv`（含失败的 3 条，`decoded=no`）。

---

## 7. 踩坑 / 与旧笔记的冲突

1. **旧笔记 14 的“u32 表 / 0x00593000 空字形”是错位解读**：该处真实格式是 `{u8 flag, u24 end_offset}`，
   `00 30 59 00` = `flag=0, end=0x5930=22832`（很多空字形共用它）；`0x...05` 里的 `05` 是 `end_offset` 的最高字节，
   不是类型。表起点是 **0x384D4**（不是 0x39E00），全表 **5638 条**（旧笔记的“1114 条”只扫到一部分）。
2. **“重复很多次的表项 = 空字形”方向对，但不能按 u32 读**：按 u32 读会让 offset 出现 5.8M/92M 之类荒谬值。
3. **`0x9A/0x9B` 的第三个字节是 count**（不是坐标）。第一版按“2 字节 op+arg + 2 字节点”硬解析会把坐标误当 opcode，得到的 op 集合爆炸（254 种）；
   正确文法下只有 11 种 opcode。
4. **大字形是多 chunk 拼接的**（`FA/len` 可重复），只看第一个 len 会误判为 framing 错误（曾漏掉 3 个码位）。
5. **官方/二改对比别按“插入”思维做 diff**：二改在 blob 中间插了 0x1DD 字节，所有后续偏移平移，单看字节 diff 会得到 5 段“大改”，
   实际是 1 次插入 + 表尾 736 条被重写（这也说明二改新增字形落在 blob 尾部原本的空字形槽位）。
6. **`empty` 字形有两种**：零长度（offset 与前一 id 相同）和 6 字节 stub（带 advance，如 `00 00 f4 01 00 00` = adv 500）。两者都要当“无轮廓”。
7. 无 cmap 表：不要再在头区找 `cmap/glyf/loca` 之类的 4 字节 tag —— 头区非零字节只有 magic、36B 描述区、`info` 记录。

---

## 8. 复现

```bat
:: 结构报告
C:\Users\90732\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe tools\fdl_glyphs.py report
:: 导出 PNG + sprite + JSON（389..391 个）
C:\Users\90732\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe tools\fdl_glyphs.py export
:: 探针（证据链，产物 out/_glyph_p*.txt / out/_sheet_*.png）
::  p1 头区/ASCII tag；p3 表几何 + 8 个 bundle 头；p4 表+blob 边界+PUA 扫描；
::  p5 占用图/记录 dump；p9/p10 framing+启发式渲染；p12/p13 文法 bootstrap；
::  p14/p15 指令形态搜索；p16 cmap 验证；p17~p19 渲染对照
```
稳定性保证：`glyph_table()` 内有断言 —— 表尾+1 必须等于 blob 起点、`blob+414933` 必须等于 info payload 起点；
cmap 断言 —— 394 个码位映射后必须全部命中“有轮廓”的 id。

---

## 9. 下一步（按价值排序）

1. **反汇编渲染器**（sec1 ARM32）确定 `0x92/0x96/0x9x` 的点类型与 arg 语义，即可把图标从“近似线稿”升级为“像素级正确”。
2. 若只要“能看”：直接用 `sprite_stroke.*`（线稿观感更接近图标），前端按 `ox/oy` 对齐 256 网格、再缩放到 100×100 单元格。
3. `flag=1` 的 277 条（索引 0..276）大概率是**复合/组件字形**，值得单独确认（可能与 `0x35` 指令有关）。
4. 其余 7 个 FDL bundle 是**同格式、不同字号的同一字体家族**（表也是 `{u8,u24}`，如 bundle#1 表起点 +0xC0、数据起点 0x3FC3D），
   若要更小尺寸的图标可从那里取（各自 cmap 基址需另测）。

---

## 10. Lead 追加试验：渲染语义仍不对，暂不嵌入页面（2026-11-09）

对 `tools/fdl_glyphs.py` 导出的 sprite 做了抽样目视：**几何可信但绘制结果不可用** —— 简单图标恰好对（如 `U+E130` 是个包裹/箱子、`U+F179` 是圆点），复杂图标出现大面积碎线/交叉（见 `out/_glyph_sample_grid.png`、`out/_preview_ordering_test.png`）。

Lead 试过并**否定**的修正假设（脚本：`tools/_glyph_semantics_test.py`、`tools/_glyph_skipb5_test.py`）：

| 假设 | 结果 |
|---|---|
| 点坐标按 `delta` 累加 | 无效（累加后超出 256 画布） |
| 点按 ctrl/on 交替做二次贝塞尔 | 无效（形状更乱） |
| 忽略 `B5` 记录（当作 glyph 级提示，非路径点） | **部分有效**：`U+E130` 等简单图标变干净；复杂图标仍有交叉 |
| 按质心角度重排点序 | 无效（更差，已在 agent 侧验证） |

结论：**轮廓点序 / 曲线类型 / `arg` 语义** 仍未定死；在反汇编渲染器之前，这些 sprite **不适合**放进网页（比方块更难看）。

页面当前策略：`web/index.html` 用「徽章占位」渲染 PUA（`renderPua`），并预留 `fillGlyphSprite()` 接口；
一旦渲染语义解出，把 `sprite_*.png` + `sprite_*.json` 填进去即可（前端按 `ox/oy` 对齐 256 网格缩放）。

相关产物：`out/_glyph_sample_grid.png`、`out/_glyph_skipb5_test.png`、`out/_glyph_contact_stroke_skipb5.png`。
