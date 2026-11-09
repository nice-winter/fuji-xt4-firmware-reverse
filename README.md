# Fujifilm X-T4 固件逆向笔记与简体中文补丁工具

> 对富士 X-T4 固件（`FWUP0024` 系列，v2.12 派生）的**静态逆向分析**记录，以及一个可直接使用的
> **简体中文 UI 文本本地化补丁工具**（纯前端、单文件 HTML）。
>
> ⚠️ **仓库不含任何固件文件**。固件版权归富士胶片所有；请自行准备合法获取的固件。
> 本项目仅用于个人学习/研究，刷机有风险，造成的一切后果自负。

---

## 1. 这个仓库有什么

| 内容 | 说明 |
|---|---|
| **格式文档** | 容器头、校验和（7 个）、FFLZ 压缩段、FDL Font 资源包、SETP/UI 资源表、语言文本池、胶片模拟枚举表 |
| **语言补丁工具** | `web/FWUP语言补丁工具.html`：拖入固件 → 自动定位语言池 → 原位改文本 → 重算校验和 → 下载完整固件 |
| **分析/补丁脚本** | `tools/`：解包解码、压缩流溯源、SETP 解析、字形提取、官方/二改 diff、已验证的胶片模拟补丁 |
| **研究笔记** | `docs/notes/`：逐专题的过程与结论（含证据强度标注：确证/强/推测/未定位） |

### 解出来的关键结构（摘要）

* 文件头 **0x274 字节明文**；其后载荷 **逐字节 XOR 0xFF** 存储。
* 头部：`os_type=6`、512 B model-code、`version=2.12`、主校验和 @`0x20C`、`0xFF6DB51F` 标记、R0..R5 区域描述表。
* 校验和：`checksum = 0xFFFFFFFF − Σ(逻辑载荷[0:0x2FC0020])`（主区），另有 6 个分区校验；已全部验证。
* 4 个 **FFLZ** 压缩段（LZ77 变体：`<0x80` 为字面量长度，否则为 `长度=b&0x0F / 距离=((tok&0x7F)<<4)|(b>>4)`），解压后共 ~33.5 MB。
* **8 个 `"FDL Font"` 资源包**：内含图标字体（**矢量轮廓**，非位图；cmap 经验公式 `glyph_id = 码位 − 0xE120`）。
* **SETP/UI 资源表**：`{u32 name_ptr_VA; u32 index}` 注册表（index=枚举值）、32 B SETP 定义记录（含选项值表 / 消息表指针）。
* 简中语言池：文件 `0x1FB3244..0x1FC05F8`（54,196 B，4,041 条记录 / 3,160 条中文串 / 1,133 个不同汉字）。

---

## 2. 仓库结构

```
.
├── README.md
├── docs/
│   ├── FIRMWARE-STRUCTURE.md      # 总文档：容器 / 校验和 / 段 / 资源地图
│   └── notes/                     # 专题笔记（00-ENV, 01-container, ... 16-fdl-glyph-extract）
├── tools/                         # 分析 & 补丁工具链（见 tools/README.md）
└── web/
    ├── index.html                 # 开发版页面
    ├── patch-core.js              # 核心逻辑（解包/定位/校验/生成补丁）
    └── FWUP语言补丁工具.html       # 单文件发行版（无外部依赖，双击可用）
```

---

## 3. 快速开始

### 3.1 语言补丁工具（推荐先用这个）

直接用浏览器打开 `web/FWUP语言补丁工具.html`：

1. 拖入固件（如 `FWUP0024_affix_1108.DAT`）；
2. 工具自动解析容器、反推载荷长度、找 FDL 包、识别语言池并选中**简体中文**；
3. 在列表里改文本（槽位长度有校验，超长会提示）；
4. 点「生成并下载」得到完整补丁固件（大小不变、校验和已重算）；
5. 刷回相机前请保留原始固件用于回退。

> 说明：文本中的 `U+E000..U+F8FF` 是固件内嵌图标字形，浏览器无字形会显示方块；
> 页面已做了占位徽章渲染 + 编辑框实时预览（后续可替换为真实字形，见 §5）。

### 3.2 命令行分析

依赖：Python 3.10+、`numpy`、`pillow`；Node.js（仅跑前端测试时需要）。

```bash
# 可选：指定固件根目录（默认 = 本仓库根目录）
export XT4_ROOT="$PWD"        # Windows: set XT4_ROOT=%CD%

# 1) 解包：逻辑镜像 + 4 个 FFLZ 段
python3 tools/decode_any.py FWUP0024_affix_1108.DAT out/f1108

# 2) 结构自检（段头 / 基址 / 注册表）
python3 tools/setp_decode.py verify

# 3) FDL 字体包 + 字形提取
python3 tools/fdl_glyphs.py report
python3 tools/fdl_glyphs.py export     # 输出 out/glyphs/

# 4) 官方固件 vs 二改固件差异
python3 tools/diff_official.py
```

生成物统一写到 `out/`（已在 `.gitignore` 中忽略）。

### 3.3 跑测试

```bash
node tools/test_core_node.js                              # 核心逻辑（真实固件）
node tools/test_page_node.js                              # 页面 UI 流程（开发版）
node tools/test_page_node.js "web/FWUP语言补丁工具.html"   # 页面 UI 流程（单文件版）
node tools/test_both_versions.js FWUP0024_aefix_1106.DAT FWUP0024_affix_1108.DAT
python3 tools/verify_js_patch.py                          # 独立复核 JS 生成的补丁
```

---

## 4. 文档索引

见 [`docs/INDEX.md`](docs/INDEX.md)（按主题列出全部笔记与结论摘要）。

最值得先看的几篇：

* [`docs/FIRMWARE-STRUCTURE.md`](docs/FIRMWARE-STRUCTURE.md) — 总格式文档
* [`docs/notes/07-ui-text-sc.md`](docs/notes/07-ui-text-sc.md) — 简中文本池的定位与结构
* [`docs/notes/08-locale-patch-web-tool.md`](docs/notes/08-locale-patch-web-tool.md) — 补丁工具设计与实现
* [`docs/notes/15-patch-no-reala-rightcol.md`](docs/notes/15-patch-no-reala-rightcol.md) — 已验证的"胶片模拟子选项"数据补丁（4 字节级）
* [`docs/notes/16-fdl-glyph-extract.md`](docs/notes/16-fdl-glyph-extract.md) — FDL 图标字体格式（矢量轮廓）逆向

---

## 5. 已知限制 / 未解点

1. **图标字形渲染语义未闭环**：cmap/loca/记录 framing/指令集已解出，但轮廓点序与曲线类型尚未确定，
   直出图形有交叉瑕疵（见 `docs/notes/16-fdl-glyph-extract.md` §10）。页面暂用占位徽章。
2. **胶片模拟 Q 菜单**的"平坦 18 项值表"深度共享 FFLZ 回溯引用，原地改会污染同字节的兄弟表；
   要彻底处理需重压缩 sec0（方案已写进 `docs/notes/15-patch-no-reala-rightcol.md` §7）。
3. 工具只针对 **X-T4 / FWUP0024 v2.12 派生**固件验证；其它机型/版本可能格式不同（可作参考）。
4. 语言池记录是**预切片段**，只能在原槽位内改文本；新增/重排字符串需先解出字符串引用索引（未做）。

---

## 6. 参考资料

* fujihack wiki — <https://wiki.fujihack.org/>
* Trammell Hudson — Fujifilm 固件 XOR 0xFF 存储等公开分析
* EnglandLobster/fujifilm-firmware-tools — FFLZ 压缩格式参考
* fffw（Fuji firmware research）中 `xt4/0212` 的公开头文件（UI_SETP/msgid 命名参考）

---

## 7. 免责声明

* 本仓库**不包含、也不再分发任何固件二进制**；文中出现的偏移、表结构均来自对自有固件的静态分析。
* 所有修改固件的操作均存在变砖风险；请在理解风险的前提下自行决定，并保留官方固件用于回退。
* 本项目与富士胶片无关联；相关商标、固件版权归其所有者。
