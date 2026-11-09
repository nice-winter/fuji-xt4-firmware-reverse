# 文档索引

> 笔记中的证据等级约定：**【确证】**=逐字节/双向验证过；**【强】**=多项独立证据；**【推测】**=未闭环；**【未定位】**=尚未找到。

## 总览

| 文档 | 内容 |
|---|---|
| [FIRMWARE-STRUCTURE.md](FIRMWARE-STRUCTURE.md) | **总文档**：容器头、7 个校验和、FFLZ 段、资源地图、语言池、FDL 包 |

## 专题笔记（`notes/`）

| 文件 | 摘要 |
|---|---|
| [00-ENV.md](notes/00-ENV.md) | 环境约定：目标固件校验值、工具路径、目录分工、初始 recon 线索 |
| [01-container.md](notes/01-container.md) | 容器层：`os_type=6`、0x274 明文头、model-code、版本字段、主校验和公式、区域描述表 |
| [02-map.md](notes/02-map.md) | 全文件熵/magic/字符串测绘；镜像的 0x20000 网格布局、重复镜像块 |
| [03-prior-art.md](notes/03-prior-art.md) | 公开资料调研：fujihack wiki、Trammell Hudson、FFLZ 格式、fffw 头文件 |
| [06-diff-official.md](notes/06-diff-official.md) | 官方 v2.12 与二改固件的差异分析（机型名替换、新增文本池等） |
| [07-ui-text-sc.md](notes/07-ui-text-sc.md) | 简体中文文本池定位与结构：`0x1FB3244..0x1FC05F8`、4,041 条记录、槽位规则、PUA 图标 |
| [08-locale-patch-web-tool.md](notes/08-locale-patch-web-tool.md) | 语言补丁工具设计：自动检测、槽位校验、校验和重算、PUA 占位渲染、测试 |
| [09-setp-resource.md](notes/09-setp-resource.md) | SETP/UI 资源：解压段加载基址、`{name_ptr,index}` 枚举名表注册表、UI SETP ID 表 |
| [16-fdl-glyph-extract.md](notes/16-fdl-glyph-extract.md) | FDL 图标字体逆向：cmap 公式、loca 表、矢量轮廓指令集、提取结果与未解点 |
| [17-long-text-edits.md](notes/17-long-text-edits.md) | **超长修改**：文本池尾部后移（覆盖 FF 填充、文件尺寸不变）+ 明文/压缩段指针修正 |
| [99-lead-findings.md](notes/99-lead-findings.md) | 早期关键发现：载荷 XOR 0xFF、0x20000 网格、内含相机资源 |

> 注：编号不连续属正常——部分专题笔记为过程记录，未随本仓库发布。

## 快速跳转

* 只想改简中文本 → [07](notes/07-ui-text-sc.md) + `web/FWUP语言补丁工具.html`
* 文本比槽位长（超长修改）→ [17](notes/17-long-text-edits.md)
* 想了解容器/校验和 → [01](notes/01-container.md) + [FIRMWARE-STRUCTURE.md](FIRMWARE-STRUCTURE.md)
* 想处理图标字形 → [16](notes/16-fdl-glyph-extract.md)
