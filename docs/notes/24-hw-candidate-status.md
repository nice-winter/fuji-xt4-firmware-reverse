# 24 — 候选固件状态矩阵（X-T4）

> **用途**：一眼看出"哪个测试包能刷、哪个会失败、失败在什么场景"。
> **来源**：全部状态取自本地详细研究快照 `xt4-codex` 的包目录 README 与同目录状态文件
> （`实机通过.md` / `实机反馈*.md` / `NOT_DELIVERED.md` / `*.REJECTED_CAMERA_FAILURE.txt` / `*.WITHDRAWN_AS_REPAIR.txt`）。
> `xt4-codex` 不在本仓库内，下表"来源"列只给相对路径（行内代码），公开克隆后不存在。
>
> ⚠️ **铁律**：本仓库不提供任何固件文件。表里出现的每个包都对应一份 51,278,280 B 的 `FWUP0024.DAT`，
> 刷写前请自行用 `Get-FileHash` 核对 SHA-256 前 12 位；**SHA 不符 = 不是一个东西**。

---

## 0. 状态词表（只有 6 种）

| 状态 | 含义 |
|---|---|
| **稳定基底** | 用户实机确认可用，且被后续工作当作基线反复引用 |
| **实机通过** | 该包在**其目标场景**被用户实机确认；括号里是场景限定 |
| **实机失败** | 用户实机反馈目标未达成，或出现更严重回归（黑屏/锁死/严重偏暗） |
| **未实测** | 离线检查完成，但**没有**该包本体的实机记录（或只测了别的包） |
| **已撤回** | 曾经交付，后被明确撤回/降级为"仅供追溯"，不推荐刷入 |
| **未交付** | 生成了包但被离线审计或构建流程拦下，没有交到相机 |

> 场景限定写在"实机反馈"列，**不**改变状态词。"实机通过（场景）"不等于"全场景通过"。

---

## 1. 主表

### 1.1 NN/RA 与 F-Log2 / Auto ISO 曝光链

| 包短名 | SHA-256(前12) | 基底 | 关键改动 | 离线验证 | 实机反馈 | 状态 | 来源 |
|---|---|---|---|---|---|---|---|
| `9206a272` | `9206a2722c10` | F-Log2 底包 | 原位替换：SEPIA→Nostalgic Neg、Mono→Reala Ace；加载器移出启动 XN 区 | 32 窗口/634 指令 + 七校验 + 逐槽解码 | 启动与视频应用正常（后续包以其为底包） | 实机通过 | `xt4-codex/analysis/packer_research/XT4_NN_RA_INPLACE_9206a272/README.md` |
| `c4cd7ddd` | `c4cd7ddde77f` | `9206a272` | 仅改显示名称资源（6 个资源 ID）+ 容器校验 | 35 槽名称、7 校验、文件差异边界 | 用户反馈正常的"菜单改名版" | 实机通过 | `xt4-codex/analysis/packer_research/XT4_NN_RA_RENAMED_c4cd7ddd/README.md` |
| `920c020f` | `920c020ff313` | `c4cd7ddd` | 图形资源目录指针替换（NN/RA 图标呈现） | 7 校验 + 逐镜像逐字节一致 + 唯一对齐指针检查 | 已实机确认正常的双胶片展示包 | 实机通过 | `xt4-codex/analysis/packer_research/XT4_NN_RA_PRESENTATION_920c020f/README.md` |
| `afcec9f8` | `afcec9f840fa` | `920c020f` | 合并旧会话中已实机消除周期性闪烁的 meterfix/ReadyAe | 7 校验、逐槽解压回读 | 闪烁修复有实机依据；**合并包本身未实机** | 未实测 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_FLICKER_afcec9f8/README.md` |
| `0dd0b1d6` | `0dd0b1d60cbf` | `afcec9f8` | 恢复 32 处原调用、停用 17 个移植的 300 偏移适配器 | 离线通过（原码调用对照） | 只作为回退对照，撤回"修复包"称谓 | 已撤回 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_NATIVE_OFFSET_CANDIDATE_0dd0b1d6/README.md` + 同目录 `*.WITHDRAWN_AS_REPAIR.txt` |
| `427b77a7` | `427b77a743c1` | `0dd0b1d6` | 11 处改动：新增 68 B 函数 + 10 处 BL，Auto 基础值取 `max(base,867)` | 独立解码器重算 + 432 组 + 七校验 | 用户反馈相对正常；作为后续对照基底 | 稳定基底 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_AUTO1250_427b77a7/README.md`；改动复核 `xt4-codex/analysis/firmware_package_audit_20261028/auto1250_427b77a7/改动说明.md` |
| `5fac9ac2` | `5fac9ac20bc2` | `427b77a7` | 单阶段：三行 300 准备变化的实机实验 | 432 组调用/ABI + 48 组 builder | 用户实测"较好"，被 `2d1711cb` 取代 | 实机通过（相对） | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_SNAPSHOT_PREPARE300_TEST_5fac9ac2/README.md` |
| `2d1711cb` | `2d1711cbbd6c` | `5fac9ac2` | 配置生产时兜底 `max(base,867)`（覆盖快照复制路径） | 3024 组资格 getter/配置 producer + 96 对 builder | **用户原文"完美了"（2026-10-28）** | 稳定基底 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_SNAPSHOT_AUTO1250_TEST_2d1711cb/实机通过.md` |
| `c568ffef` | `c568ffef33ca` | `2d1711cb` | 查看助手 B/C 两组、两变体共 4 组 31 点表（170 B，取自 XM5） | 16 组原生 builder/getter/commit + 七校验 | 未实测本版查看助手变化 | 未实测 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_STABLE_ASSIST_c568ffef/README.md` |
| `25aead14` | `25aead1438a8` | `c568ffef` | 仅把机型名参数 X-T4→X-M5（2 字节）+ 重算校验 | 7 校验；全部压缩槽/代码逐字节不变 | 无该包实机记录 | 未实测 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_ASSIST_MODEL_XM5_25aead14/README.md` |
| `acbad3b2` | `acbad3b202b6` | `25aead14` | NN/RA 颜色规则修正（XM5 规则逐项对照） | 41472 组 film/mode/scene/value + 7 校验 | 作为多个后续包共同基底，未报告回归 | 稳定基底 | `xt4-codex/analysis/packer_research/XT4_NN_RA_COLOR_FIX_XM5_acbad3b2/README.md` |
| `65f44391` | `65f443918fe0` | `acbad3b2` | 窄范围 AF 闪亮诊断（历史帧资格，目标值 300） | 5184 组 ARM 调用/资格 + 144 组 AF 缓存消费 | 未实机 | 未实测 | `xt4-codex/analysis/packer_research/XT4_FLOG2_AF_OFFSET_TEST_65f44391/README.md` |
| `270fc149` | `270fc14937df` | `acbad3b2` | Auto 下限归一化（目标分支抬高到 867） | 2592 组归一化调用 + 64 组 builder | 未修复 Auto ISO 640 起跳（手动 1250 明显更亮） | 实机失败 | `xt4-codex/analysis/packer_research/XT4_FLOG2_AUTO1250_NORMALIZATION_TEST_270fc149/README.md` |
| `43098c17` | `43098c17e80a` | `acbad3b2` | 改 `0x2365700` 增益求和 + 辅助代码（类型 3 下限） | 51840 组 ABI/策略 + 120 组 builder | 显示 1250 但亮度不变 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_FLOG2_AUTO1250_TYPE3_TEST_43098c17/README.md` |
| `6a085b21` | `6a085b2117f6` | `acbad3b2` | 每帧完整重算下限记录（栈上局部配置） | 整表对照 + 排除配置 | 实机：仍 A1250 显示但亮度仍是 640 级 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_FLOG2_AUTO_NATIVE1250_TEST_6a085b21/README.md` |
| `cb1e0a93` | `cb1e0a9363ee` | `acbad3b2` | 行记录 `+0x34` 残量转 `+0x32`（保持 `+0x0e` 总量） | 离线对照 | 实机：A1250 显示，仍比手动 1250 暗约一档 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_FLOG2_AUTO_NATIVE1250_TEST_cb1e0a93/README.md` |
| `a2139129` | `a21391295a63` | `acbad3b2` | 实时分量 ISO 下限夹到手动 1250 对应值（667） | 12 组明暗 + 12 组排除 + 两 bank 首行 | 实机：**实际最低确实 1250**，但屏幕显示 A640 | 实机通过（限实际增益） | `xt4-codex/analysis/packer_research/XT4_FLOG2_AUTO_LIVE_COMPONENT_TEST_a2139129/README.md` |
| `7719fcc3` | `7719fcc32f4d` | `a2139129` | 结果同步：录像结果 builder 低端用原生手动 867 配置重建 | 27 组 builder/手动对照 + 13 排除 + ABI | 实机：**手动快门对、自动快门不对**（仍 A640） | 实机通过（限手动快门） | `xt4-codex/analysis/packer_research/XT4_FLOG2_AUTO_RESULT_SYNC_TEST_7719fcc3/README.md` |
| `618a3edd` | `618a3edd3074` | `7719fcc3` | 自动快门同步：`0x2379e48`→`0x24d5e40`，ISO 分量余额转快门分量 | 48 组 builder + 12 排除 + 8 组 M 实时回归 | **文档冲突**：本包 README 自述"未实测"，但 `jpeg_aspect_20261106/README.md` 与 `auto_iso_physical_20261106/NEXT_SESSION.md` 均记「视频 F-Log2 Auto ISO 已实测有效」 | 实机通过（限视频 Auto ISO，冲突待核） | `xt4-codex/analysis/packer_research/XT4_FLOG2_AUTO_SHUTTER_SYNC_TEST_618a3edd/README.md` |
| `803bb294` | `803bb2942db6` | `afcec9f8` | 实时 300 偏移单点补丁 | 3888 次合成 ARM + 15552 次辅助函数 | 已被记为"实机失败的实时偏移补丁" | 实机失败 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_LIVE_OFFSET_TEST_803bb294/README.md`；反证见 `0dd0b1d6` README |
| `86717e2b` | `86717e2b3739` | `afcec9f8` | 单条指令取消 F-Log2 特殊状态的 key10 切换 | 36 组上下文 + 72 次曲线/矩阵/提交 | 实机：半按变暗仍存在 → 实验无效，不叠加 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_CURVE_TRANSITION_TEST_86717e2b/README.md` |
| `747ff466` | `747ff46625f9` | `afcec9f8` | 捕获标志修复（7 短函数、9 调用点，保留 300 偏移） | 15552 次实时 + 864 次历史 ARM 执行 | 实机：自动曝光下预览/录像**严重偏暗** | 实机失败 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_CAPTURED_FLAG_747ff466/README.md` + 同目录 `*.REJECTED_CAMERA_FAILURE.txt` |
| `3c027cec` | `3c027cec07cc` | `afcec9f8` | 双历史同步（K 标记传递 + J 缓存 + 双 bank） | 四种标记/双 bank/完整 J→K 执行 | 实机：仍严重偏暗，半按仅瞬间变亮 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_HISTORY_SYNC_3c027cec/README.md` + 同目录 `*.REJECTED_CAMERA_FAILURE.txt` |
| `2dd7f28b` | `2dd7f28bedde` | `afcec9f8` 系 | 预览中性增益（修"返回 0"错误，改为 100） | 离线仿真 + 封包检查 | 实机：半按变暗仍存在，无严重异常 → 未解决目标 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_NN_RA_FLOG2_PREVIEW_NEUTRAL_TEST_2dd7f28b/README.md` |
| `19088f46` | `19088f46bfb2` | F-Log2 底包 | 双模拟 + B2 加载器（加载器在 `0x17192f0`） | 26 窗口/343 指令 + 7 校验 | 实机：背光亮但**黑屏、卡死、无法关机** | 实机失败 | `xt4-codex/analysis/packer_research/XT4_NN_RA_19088f46/README.md` |
| `7c8392ec` | `7c8392ecb968` | `19088f46` 修复线 | 加载器移出 XN 区 + hook 寄存器保护 | 9520/11760/23520/1680/705 组 + 29 窗口 493 指令 | 无本版实机启动记录 | 未实测 | `xt4-codex/analysis/packer_research/XT4_NN_RA_XN_FIXED_7c8392ec/README.md` |

### 1.2 JPEG 比例 / UI / AF / 检视链

| 包短名 | SHA-256(前12) | 基底 | 关键改动 | 离线验证 | 实机反馈 | 状态 | 来源 |
|---|---|---|---|---|---|---|---|
| `dfba5b47` | `dfba5b47cf9e` | `618a3edd` | 三项替换 M：L4:3 5536×4152 / L5:4 5200×4160 / L65:24 6240×2304 | 592 getter + 7 profile + 140 语言 + 七校验 | 仅 4:3 的 JPEG/回放正确；取景仍 3:2；5:4/65:24 无 AF 点、拍后锁死、写卡灯闪；三比例对焦黑白闪 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_JPEG_NATIVE_RATIOS_TEST_dfba5b47/README.md`；归因 `xt4-codex/analysis/jpeg_aspect_followup_20261107/HARDWARE_FEEDBACK.md` |
| `4f354c70` | `4f354c70148b` | `618a3edd` | 三比例挂原生 1:1 共用路径（含显示/FDI/reservation） | 独立全审 + REA 字节绑定 | 刷入后**开机全黑**，用户已刷回 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_JPEG_NATIVE_SQUARE_TEST_4f354c70/README.md`；审计 `xt4-codex/analysis/jpeg_boot_failure_20261107/README.md` |
| `30bd4706` | 未记录 | `4f354c70` 线 | 中间修复构建 | **被独立离线审计拒绝**（分类器多读一个 halfword） | 未交付、未实机 | 未交付 | `xt4-codex/analysis/packer_research/XT4_JPEG_NATIVE_SQUARE_TEST_30bd4706/NOT_DELIVERED.md` |
| `1012db4c` | `1012db4c4b41` | `618a3edd` | helper 移入可执行 padding，尾区只留 FDI 数据；保留原 query 守卫 | 独立审计 + 88 REA 源字节窗口 | 三新比例 JPEG 正常；取景仍 3:2、主摘要空、Q 仍 M、5:4/65:24 张数 0 | 实机通过（JPEG） | `xt4-codex/analysis/packer_research/XT4_JPEG_NATIVE_SQUARE_TEST_1012db4c/README.md` |
| `d4f7f93d` | `d4f7f93da049` | `1012db4c` | 显示 plane 矩形 + 6 个 UI 字段 + 计数数据字节（19 ops）；公共 `0x12eeaac` 无条件跳 image6 | 19 窗口 + 独立解包/七校验 | 刷入后**开机持续黑屏**；已知 1012 可正常开机 | 实机失败 | `xt4-codex/analysis/packer_research/XT4_JPEG_PREVIEW_UI_TEST_d4f7f93d/README.md`；审计 `xt4-codex/analysis/jpeg_d4_boot_failure_20261107/README.md` |
| `2ceee71d` | `2ceee71ddaa7` | `1012db4c` | 只 hook 已确认的 3 个 image6 显示调用点（局部 wrapper + 6 B count，14 ops），公共函数字节全还原 | 14 固定范围 + 7 校验 + REA 14 窗口 + 1600 组负对照 | 用户已确认**正常取景 + 三个新比例 JPEG 输出**；主摘要空、Q/图标仍 M、张数为保守 alias | 实机通过（取景/JPEG） | `xt4-codex/analysis/packer_research/XT4_JPEG_LOCAL_PREVIEW_TEST_2ceee71d/README.md` |
| `7be75eca` | `7be75eca6a8c` | `2ceee71d` | 图标资源解析、菜单/Q 图标引用、尺寸元数据、OSD 张数 selector、缓存 count helper | 原生 GVFF 解析 + 72 cost case + 12 OSD selector + 七校验 | 用户确认**主菜单、Q 菜单显示正确** | 实机通过（菜单/Q） | `xt4-codex/analysis/packer_research/XT4_JPEG_UI_COUNT_TEST_7be75eca/README.md` |
| `fcf7b9c1` | `fcf7b9c18a08` | `7be75eca` | 30 个拍摄状态 M 图标描述符改指 GFX 的 L 字形（数据 only） | 静态族/行分组 + GVFF 载荷逐字节一致 | 未刷入 | 未实测 | `xt4-codex/analysis/packer_research/XT4_JPEG_PREVIEW_STATUS_L_TEST_fcf7b9c1/README.md` |
| `50f6d54e` | `50f6d54ee8e6` | `fcf7b9c1` | Q 菜单原生样式 + 拍摄状态 M→L 数据引用 | 60 组菜单查表 + 26019 旧图标用例 + 32 REA 窗口 | 用户反馈"基本正常"；但新比例 AFC 追踪框向右下偏移 | 实机通过（基本） | `xt4-codex/analysis/packer_research/XT4_JPEG_Q_NATIVE_STYLE_TEST_50f6d54e/README.md` |
| `1fb55839` | `1fb55839c640` | `50f6d54e` | image7 UI 区域中心 fit 坐标修正（image7 变 185 B） | 72 组 UI getter + 36 组门禁 + 七校验 | 实机 **AFC 偏移未修**，标为 FAILED_HARDWARE | 实机失败 | `xt4-codex/analysis/packer_research/XT4_JPEG_AF_UI_REGION_TEST_1fb55839/README.md` |
| `76daac32` | `76daac3210ff` | `50f6d54e` | image7 348 B helper + 4 B 调用（bbox **目的**坐标转换） | 72/432 组 UI + 144/2304 组门控 + 独立解包 | 实机 AFC 仍偏（→ 转去查**源**区域） | 实机失败 | `xt4-codex/analysis/packer_research/XT4_JPEG_TRACKING_BBOX_DEST_TEST_76daac32/README.md` |
| `a7f896c5` | `a7f896c5814c` | `50f6d54e`（image7 沿用 76da 算法） | 4:3/5:4 **源**区域按原生 3:2 居中（`[36,27,568,426]`/`[54,27,532,426]`）；468 B helper + 4 B 调用 | 72 组 UI + 2304 组门控 + 两处固定范围 | **用户确认 AFC 已正常**；4:3 AF-S 增亮/不合焦未修 | 实机通过（AFC） | `xt4-codex/analysis/packer_research/XT4_JPEG_TRACKING_BBOX_SOURCE_TEST_a7f896c5/README.md`；状态 `xt4-codex/analysis/jpeg_af_tracking_20261108/afs_followup/CURRENT_STATUS.md` |
| `d014099a` | `d014099adee1` | `a7f896c5` | 61 B 原地改搜索轴分类器（exact 3:4 也走宽度裁切） | 5902 组分类器 + 160 组入口 + 七校验 | 实机 **4:3 AF-S 未修** | 实机失败 | `xt4-codex/analysis/packer_research/XT4_JPEG_AFS_43_SEARCH_AXIS_TEST_d014099a/README.md` |
| `a01e9785` | `a01e9785b1b9` | `a7f896c5` | +36 B helper：把局部统计副本 3:4 当 6:8（16×40→16×35 单元） | 176 组执行 + 77 组非 4:3 回归 + 七校验 | 实机 **4:3 AF-S 仍未修** | 实机失败 | `xt4-codex/analysis/packer_research/XT4_JPEG_AFS_43_STATS_SYNC_TEST_a01e9785/README.md` |
| `dfc98269` | `dfc982699161` | `a7f896c5`（**不累加** d014/a01） | 4:3 网格表 `0x13d9390` 列数 13→11，消除 `mls` 无符号下溢 | 72 组原生网格 + 180 组点展开 | 用户：**功能总体正常**；余新比例 + 即时检视（timed）损坏、连续 4:3 显示为 3:2 | 实机通过（总体） | `xt4-codex/analysis/packer_research/XT4_JPEG_AFS_43_GRID_UNDERFLOW_TEST_dfc98269/README.md`；状态 `xt4-codex/analysis/jpeg_af_tracking_20261108/afs_followup/CURRENT_STATUS.md` |
| `29377c8d` | `29377c8dd53e` | `dfc98269` | image6 六行 32 B 显示表改 1440 px pitch + 中心 ROI；image5 两 word 补 50/50 边界 | 56 组成对渲染 + 108 组 common/driver + 324 组 buffer28 pitch | **未刷入**（待实机 0.5/1.5 s、LCD/EVF） | 未实测 | `xt4-codex/analysis/packer_research/XT4_JPEG_REVIEW_LAYOUT_TEST_29377c8d/README.md`；根因 `xt4-codex/analysis/jpeg_portrait_review_20261111/DISPLAY_CONTRACT_ROOT_CAUSE.md` |
| `1a8f46fc` | `1a8f46fc699b` | `618a3edd` | 中间 1:1 共用路径构建 | 最终复核发现标定边距只读低 8 位 | 未交付、未实机 | 未交付 | `xt4-codex/analysis/packer_research/XT4_JPEG_NATIVE_SQUARE_TEST_1a8f46fc/NOT_DELIVERED.md` |
| `ccbf65d3` | 未记录 | `618a3edd` | 中间构建（三语言 L 标识排列） | — | 未交付（被 dfba5b47 取代） | 未交付 | `xt4-codex/analysis/packer_research/XT4_JPEG_NATIVE_RATIOS_TEST_ccbf65d3/NOT_DELIVERED.md` |

### 1.3 本仓库（`xt4`）自己的实机补丁

| 包短名 | SHA-256(前12) | 基底 | 关键改动 | 离线验证 | 实机反馈 | 状态 | 来源 |
|---|---|---|---|---|---|---|---|
| `patch_no_reala_rightcol` | 未记录（刷前自算） | 当前 `FWUP0024.DAT`（`dfc98269…`） | 清 SETP 1070 `value=7` 的子记录指针（still `0x4BB45C..F` + movie `0x4BB606`）+ 重算主校验 | DAT 只变 7 B；sec0 解压恰变 8 B；sec1/2/3 SHA 不变；R0..R5 全过 | **2026-11-09 上机：右列消失，REALA ACE 出图仍为彩色** | 实机通过 | `xt4/docs/notes/15-patch-no-reala-rightcol.md`、`xt4/out/patch_no_reala_rightcol.DAT` |

> 备注：本仓库不记录该 DAT 的 SHA，是因为它由本地脚本按当前工作副本生成；**每次生成都要重新核对**
> （只改 7 字节这一点可作为额外自检指标）。

---

## 2. 状态读取规则（重要）

1. **README 是生成时的快照，状态文件才是终态。** 同一个目录里若存在
   `实机通过.md` / `实机反馈*.md` / `NOT_DELIVERED.md` / `*.REJECTED_CAMERA_FAILURE.txt` / `*.WITHDRAWN_AS_REPAIR.txt`，
   一律以后者为准。典型例子：
   - `2d1711cb/README.md` 写"未实机验证"，但同目录 `实机通过.md` 记录用户"完美了" → 实际是**稳定基底**。
   - `a7f896c5/README.md` 写"尚未实机"，而 `afs_followup/CURRENT_STATUS.md` 记录用户确认 AFC 正常 → 实际**实机通过**。
   - `747ff466`、`3c027cec` 的 `README.md` 正文是"待实测"，但目录根有 `*.REJECTED_CAMERA_FAILURE.txt` → **实机失败**。
2. **"推迟验证"不等于"通过"。** 本表把"离线全过但没实机"的包一律标 `未实测`，即使它的离线证据很强
   （`29377c8d`、`7c8392ec`、`fcf7b9c1` 都是这一类）。
3. **"通过"按目标场景记。** `1012db4c` 通过的是"JPEG 输出"，不是"取景/UI"；`a2139129` 通过的是"实际增益"，
   不是"显示 ISO"。要判断能不能日常用，必须看场景限定列。
4. **基底列用于判断"这个结论能不能复用"**：同一基底上被推翻的改动（`d014099a`/`a01e9785` 相对 `a7f896c5`）
   通常说明该思路不成立，而不是"补丁没生效"。

---

## 3. SHA 前缀索引（快速反查；按链路分组，不严格排序）

```
0dd0b1d60cbf  afcec9f840fa   c4cd7ddde77f  c568ffef33ca   25aead1438a8
19088f46bfb2  270fc14937df   2d1711cbbd6c  2ceee71ddaa7   2dd7f28bedde
29377c8dd53e  3c027cec07cc   427b77a743c1  43098c17e80a   4f354c70148b
50f6d54ee8e6  5fac9ac20bc2   618a3edd3074  65f443918fe0   6a085b2117f6
747ff46625f9  76daac3210ff   7719fcc32f4d  7be75eca6a8c   7c8392ecb968
803bb2942db6  86717e2b3739   9206a2722c10  920c020ff313   1012db4c4b41
a01e9785b1b9  a21391295a63   a7f896c5814c  acbad3b202b6   cb1e0a9363ee
d014099adee1  d4f7f93da049   dfba5b47cf9e  dfc982699161   fcf7b9c18a08
1a8f46fc699b  1fb55839c640
```

> 未记录 SHA 的包：`30bd4706`、`ccbf65d3`、`patch_no_reala_rightcol`（见对应 NOT_DELIVERED / 生成脚本）。

---

## 4. 被实机推翻的结论清单（"别再重复这些"）

| 曾经的结论 | 实机结果 | 正确认识 |
|---|---|---|
| "离线 592 组 getter + 7 组 profile 全过 ⇒ 新比例可用" | `dfba5b47` 只 4:3 成立，5:4/65:24 直接锁死 | 离线只证明被测分段，不证明任务完成 |
| "改 UI 区域中心 fit 就能修 AFC 偏移" | `1fb55839` 失败 | 改的那段不是普通 AFC 最终映射 |
| "改矩形**目的**坐标就能修 AFC 偏移" | `76daac32` 失败；改**源**区域（`a7f896c5`）才成立 | 先确认是源还是目的，别猜倍率 |
| "4:3 AF-S 是搜索轴裁切缺失" | `d014099a` 失败 | 下游归一化会抵消局部差异 |
| "4:3 AF-S 是统计副本比例 alias" | `a01e9785` 失败 | 6:8 等价改写不是正确修法 |
| "补充尺寸表/白名单即可" | 编码器按面积缓存 profile，映射到同一 profile 会互相污染 | 必须分配独立 profile 状态 |
| "AFC 已修 ⇒ AF 全好" | 4:3 AF-S 仍需单独的网格下溢修复（`dfc98269`） | AFC 与 AF-S 是两条链 |
| "离线 worker 算术下溢 ⇒ 即时检视损坏根因" | 该 worker 的生产者写的是 `0x9c`（连续预览），不是 timed `0x9b` | 输入未观测时，算术复现只能当负对照 |
| "竖拍才有检视损坏" | 用户修正：横竖拍都会坏，仅 timed 模式 | 以最新用户口径为准 |
| "半按变暗靠 300 偏移/捕获标志/历史同步修" | `747ff466`、`3c027cec`、`803bb294`、`86717e2b`、`2dd7f28b` 连续实机失败 | 这条链的入口/状态语义仍未闭合 |
| "显示 1250 = 实际曝光 1250" | `6a085b21`/`cb1e0a93` 显示 1250 但亮度仍是 640 级 | 显示数字与增益提交是两条路径 |

---

## 5. 文档冲突（**不擅自裁决，按文件为准**）

| 冲突点 | 说法 A | 说法 B | 处理 |
|---|---|---|---|
| `618a3edd` 是否实机 | 包 README："没有实测本包"（生成时状态） | `jpeg_aspect_20261106/README.md` 记「视频 F-Log2 Auto ISO 已实测有效」；`auto_iso_physical_20261106/NEXT_SESSION.md` 同 | 标"实机通过（限视频 Auto ISO，冲突待核）"；**按后出记录**，但保留注释 |
| `2ceee71d` 能否正常开机 | `jpeg_aspect_20261106/NEXT_SESSION.md` 段落："不能称已经正常开机" | 包 README 顶部："用户已确认正常取景 + 三新比例 JPEG" | 按**包 README**（更新）；NEXT_SESSION 那段是交付时的历史记录 |
| `a7f896c5` 是否实机 | 包 README："尚未实机" | `afs_followup/CURRENT_STATUS.md`："User confirms AFC is fixed after a7f896c5" | 按 **CURRENT_STATUS.md** |
| `50f6d54e` 是"正常"还是"有缺陷" | 用户口径"基本正常" | 同一反馈里记录了新比例 AFC 右下偏移 | 两者都真：标"实机通过（基本）"并在实机反馈列写出缺陷 |
| `d4f7f93d` 的定位 | 交付时被当作"最新同步显示候选" | 此后实机黑屏、已撤回 | 按**实机失败**；历史段落的"最新"字样不可信 |
| `c4cd7ddd` 是否实机 | 包 README："本次改名包本身尚无实机 UI 渲染记录" | `920c020f/README.md`："基于用户已反馈正常的菜单改名版 `c4cd7ddd`" | 标"实机通过"，但注明**以 `920c020f` 的记录为准**；若后续证伪请改回"未实测" |

---

## 6. 使用建议

1. 想验证某个结论 → 先按 §1 找到包，再按"来源"列打开 codex 目录，先读状态文件再读 README。
2. 想复刻一个实验 → 看"基底"列，**必须从同一基底出发**，否则失败可能来自叠加的旧改动。
3. 想刷机 → 只有 `实机通过`/`稳定基底` 的包有机会；任何 `未实测` 的包都是"实验"，请保留已知可用回退版本。
4. 相关主题的结论细节见 [23 — JPEG/AF/检视/启动失败现状](23-jpeg-af-review-status.md)。
