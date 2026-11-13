# 与 `xt4-codex` 详细研究快照的交叉参考

> 本页为 2026-11-13「交叉补强」新增。目的：把本地详细研究快照 `xt4-codex`（不随本仓库发布）里
> 已经沉淀、可公开表述的结论，接进本仓库的公开笔记体系，并标明每条结论的证据来源与强度。
>
> - `xt4`（本仓库，公开）：精选后的格式文档、工具和可复现结论，面向公开读者。
> - `xt4-codex`（本地快照，2026-11-12 整理，非公开）：更接近原始研究过程的文本、反编译/汇编片段、
>   离线执行记录、REA 证据、候选固件状态和实机反馈记录。本文中一律用行内代码标注其路径，
>   **不提供可点击链接**（它不在本仓库内，公开克隆后不存在）。
>
> 两边的证据分级沿用本仓库约定：**【确证】**＝逐字节/双向验证；**【强】**＝多项独立证据；
> **【推测】**＝未闭环；**【未定位】**＝尚未找到。另外区分四类来源：
> **静态证据** → **受控原生执行**（合成 RAM/局部函数）→ **离线包检查**（解包回读/七校验）→ **实机反馈**。
> 越往后越接近"相机真的这样工作"，但不等于全部场景成立。

---

## 0. 一分钟版

1. `xt4-codex` 是本仓库的"详细版"，本仓库是它的"公开提炼版"。**详细版结论更多，但状态更新更快、
   也更容易过时**：同一个候选包在 README 里可能写着"未实测"，而在同目录的 `实机通过.md` /
   `实机反馈.md` / `REJECTED_*` 文件里已经被推翻或确认。读 codex 先看状态文件，再看报告。
2. 本次新增 5 篇公开笔记，把 codex 里跨主题的硬结论接了进来：

   | 笔记 | 主题 | 来源主线（codex 路径，行内代码） |
   |---|---|---|
   | [20-container-packer-crosscheck.md](notes/20-container-packer-crosscheck.md) | 四机型容器/校验和、描述符表、LZ 页边界、离线回包编码器 | `xt4-codex/analysis/container_research/`、`xt4-codex/tools/packer_research/` |
   | [21-filmsim-ui-crosscheck.md](notes/21-filmsim-ui-crosscheck.md) | 胶片模拟枚举/菜单/图标/字体，NN+RA 移植路线与实机状态 | `xt4-codex/analysis/gamma_research/filmsim/` |
   | [22-flog2-iso-exposure.md](notes/22-flog2-iso-exposure.md) | F-Log2 曲线/矩阵/尾参数、ISO 准入、曝光与增益链 | `xt4-codex/analysis/xm5_native_exposure_20261028/` 等 |
   | [23-jpeg-af-review-status.md](notes/23-jpeg-af-review-status.md) | JPEG 比例/尺寸、AF 与追踪、即时检视、启动失败 | `xt4-codex/analysis/jpeg_*` |
   | [24-hw-candidate-status.md](notes/24-hw-candidate-status.md) | **候选固件状态矩阵**（哪些实机通过/失败/未测） | `xt4-codex/analysis/packer_research/` 各包状态文件 |

3. 最重要的一条工程纪律：**读/改任何偏移之前，先确认固件文件的 SHA-256**。本工作区同时存在
   官方版、二次构建版和测试候选版，偏移相同不代表内容相同（见 §1）。

---

## 1. 基准固件身份（读任何偏移前先核对）

本工作区里出现过的 X-T4 固件身份如下（路径为工作区相对路径）：

| 名称 | SHA-256 | 出现位置 | 说明 |
|---|---|---|---|
| **官方 v2.12** | `853d273b5603d3a2b93493f0ebd6a762b0b4b6bdc70317777775ae5f8ed93bc5` | `xt4-codex` 几乎所有离线回包/比较的「原厂」基准；本仓库 `out/official/FWUP0024_v212_official.DAT` | 富士官方发布件。codex 的 packer 只接受这个 SHA 作为原厂输入 |
| **`aefix_1106`（本仓库旧文档称「早期二改」）** | `618a3edd307496e93cacb38f51ac128a904e2bb713de9022d37bc8fe162c783f` | 本仓库 `FWUP0024_aefix_1106.DAT`；codex 的 `XT4_FLOG2_AUTO_SHUTTER_SYNC_TEST_618a3edd` 包 | **两处记录同一 SHA，即同一个文件**。codex 侧身份是「F-Log2 Auto ISO 自动快门同步测试候选」，本仓库早期文档把它当作匿名「早期二改 / AE 修正」分析 |
| **当前工作副本** | `dfc9826991610aaa6c46f7c390c55019c1b8b57255c27ca72051434ef9d71ae3` | 本仓库 `FWUP0024.DAT` 与 `FWUP0024_affix_1108.DAT`（同一文件） | 1108 版（codex 侧身份：JPEG AF 网格修正测试包 `dfc98269`）。11–16 号笔记写作期的对照目标；其中 11–15 未随 `main` 发布。与上两行不同，**不要混用偏移结论** |

相关笔记的基准对照：

- `07`、`11`–`16` 的目标是**二次构建/测试候选**（`06-diff-official.md` 里的"本文件"＝ `aefix_1106` / `618a3edd`），
  不是官方 GitHub 发布件。
- `out/official/FWUP0024_v212_official.DAT` 是官方 v2.12，可用于复算 codex 报告里的官方基准结论。
- `xt4-codex` 的绝大多数容器/校验和/packer 结论以**官方 v2.12** 为输入；F-Log2/胶片模拟候选包则以
  一连串测试包为基底（`packer_research/` 目录名里的短 SHA 即基底或产物标识）。写文档或做 diff 时
  必须把"基准"和"产物"分开列。

> 历史遗留：`docs/notes/00-ENV.md` 原先把目标文件写成 `618a3edd`，但工作区实际 `FWUP0024.DAT`
> 是 `dfc98269`。本次已在 `00-ENV.md` 补正，保留旧记录作为历史线索。

---

## 2. 主题地图：本仓库入口 ↔ codex 入口

> 说明：`notes/11`–`15` 属胶片模拟专题，位于 `filmsim` 分支/本地，未随 `main` 发布；`16`、`09`、`07`、`08` 在 `main` 可见。
> 表中凡指向 11–15 的行，以行内代码表示，公开克隆后请到 `filmsim` 分支查看。`20`–`24` 为本次交叉补强新增。

| 主题 | 本仓库（公开） | `xt4-codex`（详细，行内代码路径） | 现状 |
|---|---|---|---|
| 两层容器 / XOR 0xFF / 0x20000 网格 | `FIRMWARE-STRUCTURE.md` §2、`notes/01-container.md`、`notes/02-map.md` | `xt4-codex/analysis/container_research/结构与校验研究.md` | 一致；codex 用四机型实际字节建立范围校验 |
| 7 个校验和 | `FIRMWARE-STRUCTURE.md` §6、`notes/01-container.md` | 同上；`xt4-codex/tools/container_research/inspect_containers.py` | 一致（`~sum(raw XOR 0xff) & 0xffffffff`）；codex 扩展到 X-H2S/X-T5/X-M5，并发现后三机尾部 72 字节 DER 形状段 |
| 描述符表 | `FIRMWARE-STRUCTURE.md` §4 段表 #5（旧描述较粗） | 同上「现代描述符格式修正」 | codex 修正：X-T4 为 36 B/9×u32，根 `0x140274`，候选运行地址 `0x00e20000`；新三机 64 B/8×u64 |
| FFLZ 解压 | `FIRMWARE-STRUCTURE.md` §7、`tools/decode_fflz.py` | `xt4-codex/analysis/container_research/`（LZ 页边界）；`xt4-codex/tools/packer_research/README.md` | 一致；codex 复算 19 条流、无 token 跨 0x4000 页，并做出逐字节回环编码器 |
| 离线回包 / 重压缩 | `tools/fflz_rebuild.py`、`tools/fflz_trace.py`、`notes/15` | `xt4-codex/tools/packer_research/fflz_encode.c`、`xt4_packer.py`、`run_validation.py`、`analysis/packer_research/validation.json` | codex 的编码器约束集与回环验证，正好覆盖本仓库 2026-11-11「重叠 copy 导致相机无响应」的教训 |
| FDL Font 包 / 图标字形 | `notes/14`、`notes/16`、`tools/fdl_bundle.py`、`tools/fdl_glyphs.py` | codex 包内 `FDL Font` 字符串与 `xt4-codex/tools/filmsim_research/patch_film_icon_font.py` | 本仓库的包结构/纹理提取更细；codex 的图标补丁思路可互证 |
| SETP / UI 注册表 / 简中文本池 | `notes/09`、`notes/07`、`notes/08`、`web/FWUP语言补丁工具.html` | codex 侧分散在 filmsim/UI 脚本；无同等的语言池工具 | 本仓库这块更完整，可反向补强 codex |
| 胶片模拟枚举/菜单/右列 | `notes/11`–`15` | `xt4-codex/analysis/gamma_research/filmsim/`（含 `b1plus/`、`NN_RA_*`） | 本仓库 15 号补丁**实机通过**（2026-11-09）；codex 侧 NN/RA 路线另有实机反馈，见 21 号笔记 |
| NN / REALA 移植 | （原无） | `xt4-codex/analysis/gamma_research/filmsim/移植方案记录.md`、`b1plus/`、`chain_closure/` | 见 [21](notes/21-filmsim-ui-crosscheck.md) |
| F-Log2 曲线/矩阵/尾参数 | （原无） | `xt4-codex/analysis/gamma_research/完整处理链与修改清单.md`、`首次烧录前修改审查.md` | 见 [22](notes/22-flog2-iso-exposure.md) |
| ISO 准入 / 模式偏移 / Auto 下限 | （原无） | `xt4-codex/analysis/gamma_research/iso_research/`、`xt4-codex/analysis/auto_iso_physical_20261106/`、`xt4-codex/analysis/firmware_package_audit_20261028/` | 见 [22](notes/22-flog2-iso-exposure.md) |
| 曝光/增益链与半按 | （原无） | `xt4-codex/analysis/xm5_native_exposure_20261028/`、`exposure_iso_halfpress_20261028/` | 见 [22](notes/22-flog2-iso-exposure.md) |
| JPEG 比例/尺寸/菜单 | （原无） | `xt4-codex/analysis/jpeg_aspect_20261106/`、`jpeg_aspect_followup_20261107/`、`gfx_aspect_donor_20261107/` | 见 [23](notes/23-jpeg-af-review-status.md) |
| AF / 追踪 | （原无） | `xt4-codex/analysis/jpeg_af_tracking_20261108/`、`jpeg_af_search_gain_20261108/` | 见 [23](notes/23-jpeg-af-review-status.md) |
| 即时检视 / 竖拍布局 | （原无） | `xt4-codex/analysis/jpeg_instant_review_20261111/`、`jpeg_portrait_review_20261111/` | 见 [23](notes/23-jpeg-af-review-status.md) |
| 启动失败归因 | （原无） | `xt4-codex/analysis/jpeg_boot_failure_20261107/`、`jpeg_d4_boot_failure_20261107/` | 见 [23](notes/23-jpeg-af-review-status.md) |
| 候选包状态总表 | （原无） | `xt4-codex/analysis/packer_research/*/README.md` + 各状态文件 | 见 [24](notes/24-hw-candidate-status.md) |

---

## 3. 已经可以当作"硬结论"的部分（两项目互证）

以下结论在本仓库和 `xt4-codex` 中都有独立记录，可以放心引用：

1. 文件头 **0x274** 字节明文，其后载荷**逐字节 XOR 0xFF**；校验和只有以 0x274 为起点才命中。
2. 主校验和 `0xFFFFFFFF − Σ(bytes)`（对逻辑字节求和；R2/R3 两段例外，对存储字节求和）。
3. 载荷按 **0x20000（128 KiB）网格**布局；FFLZ 段头 20 B，`page_size=0x4000`，`tag=4`（X-T4）。
4. FFLZ token 流必须**整体连续解码**；硬件逐 16 KiB 页喂入，编码器保证无 token 跨页。
5. 完整重编码的四条硬约束（codex packer）：距离 3..2047、长度 1..15 且 **len ≤ distance**（无自重叠）、
   等长取最近距离、页边界规则；满足约束时 codex 能把四个原始槽位**逐字节还原**并让整份 DAT 相同。
6. 描述符表：X-T4 记录 36 B/9 个 u32，根 `0x140274`；新三机 64 B/8 个 u64（不是 72 B）。
7. 胶片模拟是"枚举 / UI 注册表 / 文本 / 图标 / 菜单绑定"多层结构，不能只看一层（本仓库 11–14 号）。
8. 右列 `+R/+Ye/+G` 是 B&W 家族的 enum 变体（8/9/10/11、ACROS 19/20/21/22），
   最小移除法是清 SETP 1070 子指针（本仓库 15 号，**实机通过**）。
9. 改压缩流的字面量前必须用 `tools/fflz_trace.py` 判断 literal vs copy；改 copy 字节会污染共享源。

---

## 4. 使用 codex 时必须知道的边界

1. **快照会过时**：codex 是 2026-11-12 的文本快照，状态类信息（实机通过/失败/撤回）以各包目录里的
   最新状态文件为准，不以 README 生成时的描述为准。
2. **合成 RAM ≠ 相机**：codex 大量结论来自 Unicorn 局部执行或人工构造的 RAM/消息对象，报告里会写
   "合成输入""host 衔接"。引用时必须保留这个限定，不能升级成"整机已验证"。
3. **不能外推机型**：四机型容器结构相近但 origin/描述符/尾段不同；X-T4 的偏移结论不要套到 X-M5 等。
4. **认证问题未闭合**：X-T4 没有新机同形的 DER 尾段，但这**不证明**相机端没有其它认证/验签路径。
5. **公私有别**：`xt4-codex` 含详细反编译、候选固件引用和私人工作路径，**不得**整段搬进公开仓库；
   本仓库只保留结论、方法、可复现命令和必要的短证据片段。

---

## 5. 后续同步建议

- codex 侧新增/推翻结论时，优先同步三处：本页主题地图、对应编号笔记（20–23）、
  [24 状态矩阵](notes/24-hw-candidate-status.md)（状态变化最频繁）。
- 新增公开结论时，至少在正文里给一条可回溯的 codex 路径 + 该结论的证据类别（静态/原生执行/离线包/实机）。
- 本仓库**不收录**：官方/修改固件、候选固件包、解包镜像、私人生成脚本路径、未脱敏的原始证据大文件。
- 反向补强（本仓库 → codex）的入口见 `xt4-codex/CROSSREF_XT4_PUBLIC.md`。
