# 共享环境与约定 (Shared environment)

## 目标文件 (read-only, 绝不修改)
- Path: `C:\Users\90732\Desktop\dev\xt4\FWUP0024.DAT`
- Size: 51,278,280 bytes = `0x30E71C8`
- SHA-256（实际工作副本，2026-11-13 核对）: `dfc9826991610aaa6c46f7c390c55019c1b8b57255c27ca72051434ef9d71ae3`
- 用户要求：**只做逆向分析与结构文档，不做任何改动**。所有脚本只读该文件，产物写到 out/ 或 notes/。

> ⚠️ 本节原记录（MD5 `73293B4F50269AD07FCD3AEF79B20D16`、SHA-256 `618A3EDD…`）对应的是
> `FWUP0024_aefix_1106.DAT`（「早期二改 / AE 修正」版），该文件现仍在工作区但**已不是** `FWUP0024.DAT` 的内容。
> 两条记录都保留：旧记录的偏移结论适用于 `aefix_1106`（=`618a3edd`），当前工作副本换成 1108 版后，
> 做 diff/补丁前必须重新核对 SHA。完整身份对照见 `../CROSS-REF-CODEX.md` §1。

### 工作区内的多份 X-T4 DAT（身份区分）
| 文件 | SHA-256 | 角色 |
|---|---|---|
| `FWUP0024_aefix_1106.DAT` | `618a3edd3074…62c783f` | 「早期二改」；与 `xt4-codex` 的 `XT4_FLOG2_AUTO_SHUTTER_SYNC_TEST_618a3edd` 同一文件（F-Log2 自动快门同步测试候选） |
| `FWUP0024.DAT` / `FWUP0024_affix_1108.DAT` | `dfc982699161…9d71ae3` | 当前 1108 工作副本（codex 侧身份：JPEG AF 网格修正测试包 `dfc98269`）；11–16 号笔记写作期的对照目标，其中 11–15 未随 `main` 发布 |
| `out/official/FWUP0024_v212_official.DAT` | `853d273b5603…ed93bc5` | 富士官方 v2.12；`xt4-codex` 的「原厂」基准 |

> 口径：**同一偏移在不同身份的文件里含义可能不同**。文档中凡出现"本文件"，以该篇笔记开头声明的
> 目标 SHA 为准；没有声明的，按写作时间粗分（11-06 及以前 → `aefix_1106`；11-08 及以后 → 1108 工作副本）。
> `08` 号笔记声明的 MD5 `695B0F76…` 未在本次身份表中定位（疑为语言补丁输出件），以该篇自述为准。

## Python
`C:\Users\90732\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe` (3.12.14, numpy 2.3.5, pandas, Pillow)
调用示例：`& "C:\Users\90732\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe" tools\xxx.py`

## 目录分工（避免写冲突）
- `00-ENV.md`  Lead 独占
- `01-container.md`, `tools/hdr.py`  → container-analyst
- `02-map.md`, `tools/scan.py`, `out/map.csv` → region-mapper
- `03-prior-art.md` → web-researcher
- `notes/04-*.md`, `tools/*` → 其他成员各自新建文件，文件名带自己前缀

## 已确认线索（Lead 初步 recon，2026-11-06）
```
00000000  06 00 00 00 33 30 33 30 33 30 33 35 33 36 33 30  |....303030353630|
```
- 偏移 0x00: u32 LE = 6（疑似表项数/块数）
- 偏移 0x04..0x203（512 字节）：全部是 ASCII 十六进制字符（'0'-'9'），内容 =
  `3030303536303031303030353630303230303035363030343030303536303039 ...`（后面大量 '0' 填充）
- 偏移 0x204: `02 00 00 00`, 0x208: `12 00 00 00`(18), 0x20C: `F5 BF B4 56`
- 偏移 0x20C 之后出现二进制数据，多次出现 `54 EF 09 03` / `54 EF 0C 03` 这类 u32（疑似指针/地址）。
- 0x27C 附近出现 `55 55 55 55 AA AA AA AA` 测试图样。
- 文件尾部（最后 ≥0x1000 字节）全 0，说明尾部无 MD5 footer（与 iT30Pro 不同）。
