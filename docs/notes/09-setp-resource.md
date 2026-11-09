# 09 · SETP / UI 资源区解析：解压段加载基址与枚举名表注册表

> 对象：`FWUP0024.DAT`（只读，未修改任何 `.DAT`）。
> 派生数据：`out/fw/**`（由 `tools/decode_any.py` 生成）。
> 工具：`tools/setp_decode.py`（可复现本文全部结论）。
> 证据等级沿用 `FIRMWARE-STRUCTURE.md`：**【确证】/【强】/【推测】/【未定位】**。

---

## 0. 结论摘要

| # | 结论 | 强度 |
|---|---|---|
| 1 | **前提修正**：`decoded.bin` 的 `0x460000-0x4A0000`、`0x4C0000-0x580000` **不是**「tokenized SETP 资源」，而是 **FFLZ sec0 的压缩流本体**（`0x260288..0x5AA926`）——看到的截断 ASCII 串是 LZ 字面量 run 的拼接边界。 | 【确证】 |
| 2 | 真正的 SETP/UI 资源在**解压后的段**里：`sec0.bin` 与 `sec1.bin` 各有一大块 4 字节对齐、NUL 结尾的 ASCII 标识符池。sec1 池 = `0x6D8AB0..0x70AA2C`（204,668 B，12,623 个名字）。 | 【确证】 |
| 3 | **关键突破**：20 字节「解压段头」给出段的**加载基址**（第 2 个 u32；第 3 个 u32 恰好 = 段长度）。sec0 `base=0x01021000 size=0x714000`；sec1 `base=0x01E0F000 size=0x900000`。凭它把名字池里的裸 ASCII 解析成了**绝对地址引用**。 | 【确证】 |
| 4 | sec1 里有一张 **`(name_ptr, index)` 8 字节注册表**（`0x6C8150..0x6D8AA0`，7,774 条），按 run/小表串联；每张小表内 `index` 从 0 连续递增 ⇒ **index = 枚举值**，小表 = 某枚举的「枚举名表」，共 702 张。 | 【确证】 |
| 5 | `UI_SETP_*` 是另一套全局 ID 注册表（id 1..2122）@sec1 `0x6C9BD8..0x6CDE20`。 | 【确证】 |
| 6 | `sec0` 的名字池只有 1,254/24,620 个被引用（另一套较小的调试名注册表）；实际 UI 枚举注册表在 **sec1**。 | 【确证】 |

---

## 1. 前提修正：「tokenized 0x80/0x81 资源」其实是 FFLZ 压缩流

最初观察到 `decoded.bin` 的 `0x460000-0x4A0000` 有「ASCII 混 0x80/0x81 控制字节、串被截断」的形态，怀疑是某种「长度前缀 + 类型字节」的 tokenized 资源。**结论：不是。**

### 1.1 范围证据

FFLZ sec0 段头位于 decoded **`0x260274`**（`<5I`）：

```
unpacked   = 7,421,952 (0x714000)     ← 恰好等于 out/fw/sections/sec0.bin 长度
packed     = 3,450,526 (0x34A69E)
pages      = 211
page_size  = 0x4000 (16 KiB)
tag        = 4
token 流   = decoded 0x260288 .. 0x5AA926
```

`0x460000-0x4A0000` 与 `0x4C0000-0x580000` **都完整落在** `0x260288..0x5AA926` 内 ⇒ 那两片「资源」就是压缩流的中段。

### 1.2 语法证据（逐字节走 token）

以 `decoded 0x486343` 起为例：

```
decoded 0x486343:  0A 49 4C 4D 5F 50 52 4F 56 49 41 8B 4A 81 44 03 56 45 4C ...
                   ^^ = 0x0A < 0x80  ⇒ FFLZ 字面量 run，长度 10
                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ = "某 ASCII 片段"（10 字节）
                                         ^^^^^ = 0x8B 0x4A → 2 字节回溯 token
```

即 `0x80/0x81` 是 **LZ77 回溯 token**（`token>=0x80` 时 `length=B&0x0F, distance=((token&0x7F)<<4)|(B>>4)`，见 `FIRMWARE-STRUCTURE.md §7`），`<0x80` 是字面量 run 长度。所谓「被控制字节隔开的截断串」全是相邻**字面量 run 的拼接边界**，首字母等被回溯复制，所以看起来缺字。

复现：`python tools/setp_decode.py verify`（会打印上面的段头与字节走查）。

⇒ **真正的 UI/SETP 资源必须到 `out/fw/sections/sec{0,1,2,3}.bin` 里找。**

---

## 2. 真正的资源在哪：两个 ASCII 标识符池 + 段头里的加载基址

### 2.1 标识符池（NUL 结尾，4 字节对齐）

| 段 | 池范围（段内偏移） | 大小 | 名字数 |
|---|---|---|---|
| `sec0.bin` | `0x3EE0C8..0x48A73C` | 640,628 B | 24,620 |
| `sec1.bin` | `0x6D8AB0..0x70AA2C` | 204,668 B | 12,623 |

两段的池含同一族 UI 标识符：`UI_SETP_*`、`UI_MENUCOM_ITEM_*`、`UI_MENU_KIND_*`、`UI_Q_MENU_*`、`UI_FUNC_*` 等（`sec0` 另有大量图标/消息名）。

### 2.2 解压段头 = 加载基址（本专题新发现）

`secN.bin` 前 20 字节：

```
sec0: 00 00 00 00 | 00 10 02 01 | 00 40 71 00 | C4 10 29 01
      word0=0     base=0x01021000  size=0x714000  word3=0x012910C4
sec1: 00 00 00 00 | 00 F0 E0 01 | 00 00 90 00 | 60 DE E1 01
      word0=0     base=0x01E0F000  size=0x900000  word3=0x01E1DE60
```

`word2` 与真实解压长度**逐字节相等**，故 `word1` 解释为**加载虚拟基址**可信。§3 的注册表只有在用这个基址时才能全部解析成功（反过来也验证了基址正确）。

### 2.3 为什么之前找不到「指针引用」

- 直接搜 `u32 == 池内偏移`：`sec0`/`sec1` 都 **0 命中**（代码/数据里存的是**绝对地址**）。
- 用 §2.2 的基址换算成 VA 后再搜：`sec1` 每个名字**恰好 1 处命中**，且全部落在一张 8 字节记录表里 ⇒ 破案。
- `sec0` 的名字池只有少数被引用（另一套较小的调试名注册表），实际 UI 枚举注册表在 **sec1**。

---

## 3. sec1 的 `(name_ptr, index)` 注册表（本专题核心结构）

### 3.1 记录格式

```
struct Entry { u32 name_ptr_VA; u32 index; };   // 8 字节，表内连续
name_ptr_VA = sec1_base(0x01E0F000) + 名字在 sec1 内的偏移
```

- 表范围：`0x6C8150..0x6D8AA0`（紧邻名字池之前），共 **7,774** 条有效记录。
- 记录被切成 **27 个连续 run**；run 内再按 `index` 是否 +1 切分成 **702 张枚举名表**。
- 每张表内 `index = 0,1,2,…` ⇒ **index 就是该枚举的数值**。

两张主表（其余为几百张并列的枚举名表）：

| 表 | 段内偏移 | 条数 | index 范围 | 首个名字 |
|---|---|---|---|---|
| `UI_SETP_*` 全局 ID 表 | `0x6C9BD8..0x6CDE20` | 2,122 | 1..2122 | `UI_SETP_BKUP_VER` |
| 枚举名表串 | `0x6CDE30..0x6D8AA0` | 5,519 | 每表 0..N | `UI_MENUCOM_ITEM_ISO` |

> 注意：第 2 个 run 内 index 会反复从 0 开始，所以它**不是一张全局 ID 表**，而是几百张并列的枚举名表。

复现：`python tools/setp_decode.py registry`。

---

## 4. 与其它资源的关系

- 文本/标签由 **FDL Font 资源包**提供（UTF-16LE 文本池 + 图标 PUA 前缀），格式见 `16-fdl-glyph-extract.md`。
- 菜单实际渲染时还会用到 SETP 定义记录（32 B，含选项值表 / 消息表指针）；具体记录布局随 SETP 类型不同，本文只覆盖注册表这一层。

---

## 5. 复现

```powershell
$py = "python"    # 或设置 PYTHON_BIN

& $py tools\setp_decode.py verify    # 证明「tokenized 区」= FFLZ 压缩流（§1）
& $py tools\setp_decode.py pools     # 两段的 ASCII 名字池 + 段头基址（§2）
& $py tools\setp_decode.py registry  # 8 字节 (name_ptr,index) 注册表/枚举名表（§3）
& $py tools\setp_decode.py all       # 全部
```

产物只读：不写 `.DAT`；输出到 stdout（可重定向到 `out/`）。
