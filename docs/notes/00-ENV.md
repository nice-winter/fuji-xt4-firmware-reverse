# 共享环境与约定 (Shared environment)

## 目标文件 (read-only, 绝不修改)
- Path: `C:\Users\90732\Desktop\dev\xt4\FWUP0024.DAT`
- Size: 51,278,280 bytes = `0x30E71C8`
- MD5: `73293B4F50269AD07FCD3AEF79B20D16`
- SHA-256: `618A3EDD307496E93CACB38F51AC128A904E2BB713DE9022D37BC8FE162C783F`
- 用户要求：**只做逆向分析与结构文档，不做任何改动**。所有脚本只读该文件，产物写到 out/ 或 notes/。

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
