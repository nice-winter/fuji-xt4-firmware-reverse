# 文档索引

> 笔记中的证据等级约定：**【确证】**=逐字节/双向验证过；**【强】**=多项独立证据；**【推测】**=未闭环；**【未定位】**=尚未找到。

## 总览

| 文档 | 内容 |
|---|---|
| [FIRMWARE-STRUCTURE.md](FIRMWARE-STRUCTURE.md) | **总文档**：容器头、7 个校验和、FFLZ 段、资源地图、语言池、FDL 包 |
| [CROSS-REF-CODEX.md](CROSS-REF-CODEX.md) | **交叉参考**：与本地详细研究快照 `xt4-codex` 的关系、主题地图、基准固件身份（读偏移前必看） |

## 专题笔记（`notes/`）

| 文件 | 摘要 |
|---|---|
| [00-ENV.md](notes/00-ENV.md) | 环境约定：目标固件校验值（含多份 DAT 的身份区分）、工具路径、目录分工、初始 recon 线索 |
| [01-container.md](notes/01-container.md) | 容器层：`os_type=6`、0x274 明文头、model-code、版本字段、主校验和公式、区域描述表 |
| [02-map.md](notes/02-map.md) | 全文件熵/magic/字符串测绘；镜像的 0x20000 网格布局、重复镜像块 |
| [03-prior-art.md](notes/03-prior-art.md) | 公开资料调研：fujihack wiki、Trammell Hudson、FFLZ 格式、fffw 头文件 |
| [06-diff-official.md](notes/06-diff-official.md) | 官方 v2.12 与二改固件的差异分析（机型名替换、新增文本池等） |
| [07-ui-text-sc.md](notes/07-ui-text-sc.md) | 简体中文文本池定位与结构：`0x1FB3244..0x1FC05F8`、4,041 条记录、槽位规则、PUA 图标 |
| [08-locale-patch-web-tool.md](notes/08-locale-patch-web-tool.md) | 语言补丁工具设计：自动检测、槽位校验、校验和重算、PUA 占位渲染、测试 |
| [09-setp-resource.md](notes/09-setp-resource.md) | SETP/UI 资源：解压段加载基址、`{name_ptr,index}` 枚举名表注册表、UI SETP ID 表 |
| [16-fdl-glyph-extract.md](notes/16-fdl-glyph-extract.md) | FDL 图标字体逆向：cmap 公式、loca 表、矢量轮廓指令集、提取结果与未解点 |
| [99-lead-findings.md](notes/99-lead-findings.md) | 早期关键发现：载荷 XOR 0xFF、0x20000 网格、内含相机资源 |

> 胶片模拟专题笔记 `11`–`15`（`11-filmsim-order-analysis.md`、`12-filmsim-bwfilter-removal.md`、
> `13-fsim-ui-code.md`、`14-fdl-fsim-tables.md`、`15-patch-no-reala-rightcol.md`）位于 `filmsim` 分支/本地，
> `main` 用 `.gitignore` 排除、未随 `main` 发布；其公开可读摘要与状态见
> [21-filmsim-ui-crosscheck.md](notes/21-filmsim-ui-crosscheck.md)。

## 交叉补强笔记（2026-11-13 新增，来源：`xt4-codex` 详细快照）

| 文件 | 摘要 |
|---|---|
| [20-container-packer-crosscheck.md](notes/20-container-packer-crosscheck.md) | 四机型容器/校验和对照、描述符表格式修正、LZ 页边界统计、离线回包编码器约束与逐字节回环 |
| [21-filmsim-ui-crosscheck.md](notes/21-filmsim-ui-crosscheck.md) | 胶片模拟多层结构互证、NN/REALA 移植路线与实机状态、右列移除补丁与替换路线的层次关系 |
| [22-flog2-iso-exposure.md](notes/22-flog2-iso-exposure.md) | F-Log2 为什么不是换曲线、XM5 原生 ISO/曝光/增益模型、XT4 候选演进与实机状态、已纠正的错误模型 |
| [23-jpeg-af-review-status.md](notes/23-jpeg-af-review-status.md) | JPEG 比例/尺寸、AF 追踪、即时检视/竖拍布局、启动失败归因的现状与边界 |
| [24-hw-candidate-status.md](notes/24-hw-candidate-status.md) | **候选固件状态矩阵**：包名/SHA/基底/改动/离线验证/实机反馈/状态 |

> 20–24 号笔记面向公开读者重写：只保留结论、方法、必要的短证据片段和 `xt4-codex` 路径引用，
> 不包含固件二进制、候选包或大段原始反编译。

> 注：编号不连续属正常——部分专题笔记为过程记录，未随本仓库发布。

## 快速跳转

* 只想改简中文本 → [07](notes/07-ui-text-sc.md) + `web/FWUP语言补丁工具.html`
* 想了解容器/校验和 → [01](notes/01-container.md) + [FIRMWARE-STRUCTURE.md](FIRMWARE-STRUCTURE.md)
* 想处理图标字形 → [16](notes/16-fdl-glyph-extract.md)
* 想弄清"哪份固件、哪个偏移" → [CROSS-REF-CODEX.md](CROSS-REF-CODEX.md) §1 + [00-ENV.md](notes/00-ENV.md)
* 想知道哪些候选包能刷 → [24](notes/24-hw-candidate-status.md)
