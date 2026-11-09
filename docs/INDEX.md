# 文档索引

> 笔记中的证据等级约定：**【确证】**=逐字节/双向验证过；**【强】**=多项独立证据；**【推测】**=未闭环；**【未定位】**=尚未找到。

## 总览

| 文档 | 内容 |
|---|---|
| [FIRMWARE-STRUCTURE.md](FIRMWARE-STRUCTURE.md) | **总文档**：容器头、7 个校验和、FFLZ 段、资源地图、语言池、SETP、FDL 包 |

## 专题笔记（`notes/`）

| 文件 | 摘要 |
|---|---|
| [00-ENV.md](notes/00-ENV.md) | 环境约定：目标固件校验值、工具路径、目录分工、初始 recon 线索 |
| [01-container.md](notes/01-container.md) | 容器层：`os_type=6`、0x274 明文头、model-code、版本字段、主校验和公式、区域描述表 |
| [02-map.md](notes/02-map.md) | 全文件熵/magic/字符串测绘；镜像的 0x20000 网格布局、重复镜像块 |
| [03-prior-art.md](notes/03-prior-art.md) | 公开资料调研：fujihack wiki、Trammell Hudson、FFLZ 格式、fffw 头文件 |
| [06-diff-official.md](notes/06-diff-official.md) | 官方 v2.12 与二改固件的差异分析（"X-T4→X-M5"、新增文本池等） |
| [07-ui-text-sc.md](notes/07-ui-text-sc.md) | 简体中文文本池定位与结构：`0x1FB3244..0x1FC05F8`、4,041 条记录、槽位规则、PUA 图标 |
| [08-locale-patch-web-tool.md](notes/08-locale-patch-web-tool.md) | 语言补丁工具设计：自动检测、槽位校验、校验和重算、PUA 占位渲染、测试 |
| [09-setp-resource.md](notes/09-setp-resource.md) | SETP/UI 资源：段加载基址、`{name_ptr,index}` 注册表、胶片模拟枚举名表、SETP ID 表 |
| [11-filmsim-order-analysis.md](notes/11-filmsim-order-analysis.md) | 胶片模拟"槽位"与菜单顺序分析：枚举顺序 ≠ 菜单顺序、排除的假设清单 |
| [12-filmsim-bwfilter-removal.md](notes/12-filmsim-bwfilter-removal.md) | BW 滤镜子选项（+R/+Ye/+G）定位：为什么清文本无效、二改的"换皮"手法 |
| [13-fsim-ui-code.md](notes/13-fsim-ui-code.md) | 胶片模拟选择界面数据链：SETP 1070 的 12 项表 + 子 SETP 1071/1072（右列来源）【确证】 |
| [14-fdl-fsim-tables.md](notes/14-fdl-fsim-tables.md) | FDL Font 包结构、35 个语言块、8B 消息记录 / 12B 布局条目、二改写入位置 |
| [15-patch-no-reala-rightcol.md](notes/15-patch-no-reala-rightcol.md) | **已上机验证的补丁**：清 4 字节子 SETP 指针 → 移除 REALA ACE 右列（附完整验证与风险） |
| [16-fdl-glyph-extract.md](notes/16-fdl-glyph-extract.md) | FDL 图标字体逆向：cmap 公式、loca 表、矢量轮廓指令集、提取结果与未解点 |
| [99-lead-findings.md](notes/99-lead-findings.md) | 早期关键发现：载荷 XOR 0xFF、0x20000 网格、内含相机资源 |

> 注：编号 04/05/10 为分工占位号，未产出独立笔记。

## 快速跳转

* 只想改简中文本 → [07](notes/07-ui-text-sc.md) + `web/FWUP语言补丁工具.html`
* 想了解容器/校验和 → [01](notes/01-container.md) + [FIRMWARE-STRUCTURE.md](FIRMWARE-STRUCTURE.md)
* 想动胶片模拟菜单 → [13](notes/13-fsim-ui-code.md) + [15](notes/15-patch-no-reala-rightcol.md)
* 想处理图标字形 → [16](notes/16-fdl-glyph-extract.md)
