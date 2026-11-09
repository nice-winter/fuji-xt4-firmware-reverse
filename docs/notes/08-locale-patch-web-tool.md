# 08 — 固件语言补丁网页工具（HTML + JS）使用与实测报告

> 目标固件：`FWUP0024.DAT`（X-T4 二次构建，os=6 / v2.12 / 51,278,280 B / MD5 `695B0F76…`）
> 交付物：**纯前端单页工具**，无后端、无网络上传；拖入 `.DAT` → 逐条改简体中文 → 下载改好的 `.DAT`。
> 原始固件只读，工具不修改磁盘上的原文件。

---

## 1. 交付物

| 文件 | 说明 |
|---|---|
| `web/FWUP语言补丁工具.html` | **单文件版（推荐直接用）**：内联了全部逻辑，双击用浏览器打开即可 |
| `web/index.html` + `web/patch-core.js` | 开发版（两文件放同一目录也能用，便于阅读/改代码） |
| `tools/build_single_html.py` | 把开发版打包成单文件（改完 `web/` 后运行一次即可） |
| `tools/test_core_node.js` | 核心逻辑测试（对真实固件跑：解析/检测/改写/校验） |
| `tools/test_page_node.js` | 页面级冒烟测试（用最小 DOM 桩在 Node 里跑整条 UI 流程，含下载与 JSON 导入导出） |
| `tools/test_both_versions.js` | 版本无关性检查（同一套代码跑 早期版 / 当前版 两个固件） |
| `tools/verify_js_patch.py` | 用 Python 独立复核 JS 生成的补丁文件（校验和/文本回读/差异字节） |
| `out/patched_js.DAT` | 测试产物：JS 工具生成的补丁固件（4 条文本被改） |
| `out/js_patch_verify.txt` | 上面文件的 Python 独立复核结果 |

---

## 2. 使用方法（5 步）

1. 用 Chrome / Edge 打开 `web/FWUP语言补丁工具.html`（双击即可，无需服务器）。
2. 把 `FWUP0024.DAT` 拖进虚线框（或点击选择文件）。工具会自动解析并列出检测到的 27 个语言文本池。
3. 「选择要编辑的语言文本池」里默认已选 **简体中文 ★推荐**（4,041 条记录；也可改其它语言）。
4. 在「编辑文本」里搜索/翻页，把「新文本」输入框改成想要的文字：
   * 每行显示 `槽位 12B/5字`，即这条最多能写几个汉字（等长或缩短都安全，可在槽位内加长）；
   * 超长/非法字符会立刻标红并**不参与生成**（不会偷偷用旧值）；
   * 「导出修改 JSON」/「导入修改 JSON」支持批量维护替换表。
5. 点「生成并下载 .DAT」→ 得到 `FWUP0024.DAT`（同尺寸、校验和已重算），把文件按官方流程放 SD 卡刷机即可。

页面右下会打印日志：文件大小是否未变、校验和 原→新、校验回读、文本回读、实际改动字节数、逐条回读结果。

---

## 3. 自动检测原理（为什么换版本也能用）

页面**不写死任何偏移**，全部现场推导：

1. **容器头**：`u32@0` = `os_type`（6）→ `codeSize=512`；`version1/version2/checksum/end` 位于 `4+codeSize+{0,4,8,12}`；头长 = `codeSize+20`。
2. **载荷起点**：枚举候选 `[0x274, headerSize, 0x214, 0x378, headerSize+0x60]`，对每个候选把 `file[payloadOffset:]` 做 `XOR 0xFF` 解码，然后在头部 u32 里找「主载荷长度 L」，用**校验和公式反证**：
   `checksum == 0xFFFFFFFF − Σ(逻辑载荷[0:L])`。
   对 FWUP0024 系列（type 6）实际命中 `payloadOffset=0x274`、`L=0x2FC0020`。
3. **语言文本池**：在载荷里找 `"FDL Font\0"` 资源包 → 只在包内做 4 KiB 窗口的字符统计（汉字/假名/谚文/西里尔/阿拉伯/泰文/拉丁）→ 合并候选区 → 在候选区内按 `UTF-16LE + 0x0000` 抽字符串 → **覆盖率过滤**（真实文本池 ≈ 0.84–0.93；字体位图区 ≈ 0.45–0.50，会被剔除）→ 按记录间隙聚类 → 去掉零散噪声记录。
4. **简体/繁体判别**：统计「仅简体字」与「仅繁体字」出现次数（如 设/設、关/關、选/選、镜/鏡…），多数决定 `zh-Hans` / `zh-Hant`。
5. **改写**：按记录「槽位」写入新的 UTF-16LE + `0x0000`，槽位剩余补 0；随后重算 `0x20C` 主校验和，并把载荷逐字节取反写回，保持文件尺寸不变。尾部 6 个 region 校验和不受影响（都在主载荷之后）。

---

## 4. 实测结果（本轮全部跑过）

### 4.1 版本无关性（`tools/test_both_versions.js`）

| 固件 | 校验和 | 载荷起点 | 主载荷 | 检测池 | 简体中文池 | 记录数 | 含汉字 |
|---|---|---|---|---|---|---|---|
| `FWUP0024.DAT` | `0x56B4BFF5` | `0x274` | `0x2FC0020` | 27 | `0x1FB3244..0x1FC05F8` | 4,041 | 3,160 |
| `FWUP0024.DAT` | `0x56BA65C6` | `0x274` | `0x2FC0020` | 27 | `0x1FB3244..0x1FC05F8` | 4,041 | 3,160 |

两次分析各约 0.79 s（Node/桌面端；浏览器同量级）。两版固件的简体中文池**逐字节相同**，所以测试可互换。

### 4.2 核心逻辑测试（`tools/test_core_node.js`，对 当前二改）

```
OK os_type == 6 / version == 2.12 / payload offset == 0x274 / main body == 0x2FC0020 / 校验和公式验证通过
OK SC pool = 0x1FB3244..0x1FC05F8, 4,041 条记录, 3,160 条含汉字
OK 4 条编辑全部应用（含 1 条等长、1 条加长到槽位上限、1 条缩短）
OK 文件大小不变 / checksum 回读一致 / 文本回读全部匹配
changed bytes: 15 in 4 runs
```

### 4.3 页面级测试（`tools/test_page_node.js`，DOM 桩模拟真实操作）

- 拖入固件 → 信息面板 9 项、语言池表 27 行、自动选中「简体中文 · 4,041 条」；
- 首页 100 行、搜索/分页/状态标记正常；
- 改一条 → 「已修改 1 条」→ 点「只校验」→ 日志显示：文件大小未变、校验和 `0x56BA65C6 → 0x56BA6539`、回读通过、改动 5 B；
- 输入超长文本 → 立刻拦截「需要 50B，槽位 12B（最多 5 字）」，且**不计入待应用修改**；
- 点「生成并下载」→ 捕获到的 Blob 为 51,278,280 B、校验和有效、含新文本；
- 「导出修改 JSON」→ 正确输出 1 条 `{offset, payload_offset, lang, old, new}`。
- **单文件版与开发版均全部通过**（`ALL PAGE CHECKS PASSED`）。

### 4.4 独立复核（Python，`tools/verify_js_patch.py` 对 `out/patched_js.DAT`）

```
文件大小：51,278,280 → 相同
主校验和：0x56BA65AD（重算=字段，OK）
R0..R5 六个 region 校验和：全部 OK
差异：15 字节 / 4 段（0x20C、文本 4 处）
文本回读：自动对焦模式 / 传感器除尘 / 信息显示改 / 删除数据 —— 全部正确
池内其余字节与原始一致：54,182 / 54,196
```

---

## 5. 能力与限制

**能做**
- 任意 X-T4 `FWUP0024` type-6 固件（自动检测，不依赖版本号）；
- 任意语言池（简中/繁中/日/韩/俄/阿/泰/拉丁…），默认简中；
- 等长替换、缩短、在槽位内加长；批量导入/导出替换表；下载完整 `.DAT`；
- 自动重算校验和并在下载前**回读验证**。

**不能做（当前版本）**
- 超出「槽位」的长文本（会挤掉下一条，需要重排整个池并更新所有引用，当前工具不做）；
- 新增字符串/新条目（没有解出字符串引用索引）；
- 修改字体（字形在同一个 `FDL Font` 包的另一块位图表里，字符→字形映射未解）；
- 修改非文本内容（代码/压缩段）。

**注意事项**
- 只能尽量用池内已出现的字符（页面会提示该池共用了多少个不同字符；简中池为 1,134 个）。用生僻字可能显示为空白/方框。
- 文本是**预换行片段**，替换时保持接近的显示宽度（汉字/全角=2 列）可避免菜单排版溢出。
- 单字 PUA（`U+E1xx`、`U+F0xx–F7xx`）是内嵌图标 token，不要删。
- 刷机前保留原文件与官方固件（`out/official/FWUP0024.DAT`）以便回退。

---

## 6. 代码结构（`web/patch-core.js`）

| 方法 | 作用 |
|---|---|
| `parseHeader(u8)` | 解析 os_type / codeSize / 版本 / 校验和 / 头长 |
| `decodePayload(u8, off)` | XOR 0xFF 解码载荷 |
| `detectMainBody(payload, ck, headerU32s)` | 用校验和反证主载荷长度 L |
| `findFdlBundles(payload)` | 找 `"FDL Font"` 资源包 |
| `detectPools(payload)` | 窗口统计 + 抽字符串 + 覆盖率过滤 + 聚类 → 语言池列表 |
| `extractStrings / classifyStrings / langLabel` | 字符串与语言分类 |
| `applyEdits(payload, edits, rec)` | 槽位校验 + 原位写入（剩余补 0） |
| `buildPatched(orig, state)` | 重算校验和、取反写回完整文件 |
| `verifyPatched(out, state, edits)` | 回读校验和与文本 |
| `charsetOf(strings)` | 统计池内字符集（提示缺字形风险） |

页面只负责 DOM/交互，核心逻辑 100% 在这一个文件里，便于以后复用（例如做个命令行版或批量脚本）。

---

## 7. 复现命令

```powershell
$py   = "C:\Users\90732\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$node = "C:\Users\90732\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe"
cd C:\Users\90732\Desktop\dev\xt4

# 生成单文件版
& $py tools\build_single_html.py

# 核心测试（真实固件）
& $node tools\test_core_node.js

# 页面 UI 流程测试（开发版 + 单文件版）
& $node tools\test_page_node.js
& $node tools\test_page_node.js "web\FWUP语言补丁工具.html"

# 版本无关性
& $node tools\test_both_versions.js FWUP0024.DAT FWUP0024.DAT

# 独立复核 JS 生成的补丁
& $py tools\verify_js_patch.py
```

---

## 8. 后续可扩展

1. **字符串引用索引**：解出来之后就能新增/重排字符串（而不是只能原位改），也能做「整段翻译导入」。
2. **字体 cmap**：解出字符→字形映射后，可支持生僻字（或从其它语言池借字形）。
3. **显示宽度规则**：统计同组片段宽度，给「加长」做自动换行提示。
4. **命令行版**：核心文件已可直接被 Node 引入，加个小 CLI 即可做批量/CI 化处理。

---

## 9. PUA 内嵌图标的显示（2026-11-09 追加）

**问题**：简体中文池里有 394 个不同的 PUA 字符（U+E120..E13x、U+F000..F7FF），它们是固件里的内嵌小图标码位；浏览器没有这些字形 → 全部显示成方块（tofu）。不影响文本编辑，但看不清。

**已做的处理（`web/index.html`）**：
* 新增 `renderPua(text)`：把 PUA 字符渲染成小徽章 `<span class="gl ph">`（显示码位末两位，例如 `\uf2ef` → `EF`），并带 tooltip（`固件图标 U+F2EF`）。
* 「原文本」单元格改用 `innerHTML = renderPua(r.text)`；编辑输入框下方新增 `.inprev` 实时预览（输入时同步刷新），这样编辑框里的原字符看不见时，下面能看清有几个图标、在什么位置。
* 已预留真实字形接口：

```js
var GLYPHS = {};   // "F2EF" -> {x,y,w,h}   （sprite 内位置/尺寸）
var SPRITE = '';   // "data:image/png;base64,..."
window.fillGlyphSprite({ sprite: SPRITE, glyphs: GLYPHS });  // 调用后自动重渲染
```

`renderPua()` 在 `GLYPHS`/`SPRITE` 存在时自动切换成 `background-image + background-position` 的真实图标；没有时保持徽章占位。所以**字体字形提取完成后，只需把数据填进这两个变量**，页面即从"徽章"升级为"真图标"。

**测试**：`tools/test_page_node.js` 的最小 DOM shim 需要支持 `innerHTML` 的文本抽取，已加 `stripHtml()`；开发版/单文件版均 `ALL PAGE CHECKS PASSED`。

**字体格式**：FDL Font 是私有图文格式（非 TTF），逆向进展见 `16-fdl-glyph-extract.md`。
