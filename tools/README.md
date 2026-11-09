# tools — 分析 / 补丁工具链

> 所有脚本默认把**本仓库根目录**当作工作目录（可用环境变量 `XT4_ROOT` 覆盖）。
> 固件 `.DAT` 放仓库根目录即可；产物统一写到 `out/`（已忽略）。
> 依赖：Python 3.10+（`numpy`、`pillow`）；Node.js 仅前端测试需要（可用 `NODE_BIN` 指定）。

## 解码 / 格式

| 脚本 | 用途 |
|---|---|
| `decode_any.py <DAT> <outdir>` | 解任意 FWUP0024 type-6 固件：输出逻辑镜像 `decoded.bin` + 4 个 FFLZ 解压段 `sections/sec*.bin` |
| `decode_fflz.py` | 仅解 FFLZ 段的旧版脚本（保留作参考） |
| `fflz_trace.py` | **压缩流溯源**：给出解压后每个字节来自"字面量"还是"回溯引用"，用于判断能否原地打补丁 |
| `hdr.py` | 容器头解析/校验和验证（早期实现，`decode_any.py` 已覆盖大部分功能） |
| `diff_official.py` | 官方固件 vs 二改固件的段级/解压后差异 |

## SETP / UI 资源

| 脚本 | 用途 |
|---|---|
| `setp_decode.py` | 解压段加载基址、标识符池、`{name_ptr,index}` 枚举名表注册表、UI SETP ID 表（`verify` / `pools` / `registry` / `all`） |

## FDL Font 资源

| 脚本 | 用途 |
|---|---|
| `fdl_bundle.py` | FDL Font 包结构解析（`report` / `header` / `blocks` / `labels` / `entries` / `patchmap`） |
| `fdl_glyphs.py` | 图标字形提取（`report` / `export`）：cmap、loca 表、矢量轮廓 → PNG + sprite + JSON |

## 语言文本

| 脚本 | 用途 |
|---|---|
| `ui_extract_sc.py` | 提取简体中文文本池（TSV/TXT + 语言概览报告） |
| `ui_sc_inventory.py` | 简中池逐条清单（槽位/偏移） |
| `ui_charset.py` | 池内字符集统计（改文本时的"缺字形"风险提示） |
| `ui_pool_ranges.py` | 语言池边界/覆盖范围分析 |
| `ui_patch.py` | 命令行版文本补丁器（校验和重算 + 回读验证） |

## 前端工具构建 / 测试

| 脚本 | 用途 |
|---|---|
| `build_single_html.py` | 由 `web/index.html` + `web/patch-core.js` 生成单文件发行版 |
| `check_page.py` | 单文件版内联脚本语法检查 |
| `test_core_node.js` | 核心逻辑测试（真实固件：解析/检测/补丁/校验） |
| `test_page_node.js` | 页面 UI 流程冒烟测试（最小 DOM 模拟；可指定页面路径） |
| `test_both_versions.js` | 跨固件版本一致性测试 |
| `verify_js_patch.py` | 独立复核前端生成的补丁（校验和、分区校验、改动字节） |

## 约定

* **只读**输入固件：所有脚本只 `open(...,'rb')`，不会修改 `.DAT`。
* 派生数据写 `out/`，文档写 `docs/`。
* 一次性探针脚本（`_probe_*`、`setp_explore*`、`lead_*` 等）是逆向过程中的临时工具，
  已在 `.gitignore` 中排除，未随仓库发布。
