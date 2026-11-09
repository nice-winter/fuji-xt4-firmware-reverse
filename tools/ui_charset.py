#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character set + language-block survey for the localisation area."""
import io, collections
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEC = os.path.join(ROOT, "out", "decoded.bin")
d = open(DEC, "rb").read()

# ---- SC character set (what the SC font is guaranteed to render) ----------
rows = []
for line in io.open(os.path.join(ROOT, "out", "ui_sc_strings.tsv"), encoding="utf-8").read().splitlines()[1:]:
    parts = line.split("\t")
    if len(parts) >= 5:
        rows.append(parts[4])
chars = collections.Counter(ch for s in rows for ch in s)
out = io.open(os.path.join(ROOT, "out", "ui_sc_charset.txt"), "w", encoding="utf-8")
out.write("# distinct characters used by the Simplified-Chinese UI block (%d chars)\n" % len(chars))
out.write("# one char per line with frequency\n")
for ch, n in chars.most_common():
    out.write("%s\t%d\tU+%04X\n" % (ch, n, ord(ch)))
out.close()
print("SC charset: %d distinct characters (saved out/ui_sc_charset.txt)" % len(chars))

# ---- locate other language blocks by characteristic vocabulary -----------
def find(word):
    b = word.encode("utf-16le")
    locs = []
    i = -1
    while True:
        i = d.find(b, i + 1)
        if i < 0:
            return locs
        locs.append(i)

rep = io.open(os.path.join(ROOT, "out", "ui_lang_blocks.txt"), "w", encoding="utf-8")
probes = [
    ("SC 简体", ["设置", "关闭", "选择", "图像", "自动", "相机"]),
    ("TC 繁體", ["設定", "關閉", "選擇", "自動", "相機", "選單"]),
    ("JP 日本語", ["カメラ", "シャッター", "オート", "モード", "メニュー"]),
    ("EN English", ["SHUTTER", "CAMERA", "SET UP", "AUTO", "MENU"]),
    ("DE/FR Latin", ["Kamera", "Appareil", "MENU", "Auto"]),
]
for name, words in probes:
    allhits = []
    for w in words:
        allhits += find(w)
    if not allhits:
        rep.write("%s: no hits\n" % name)
        continue
    c = collections.Counter(x // 0x10000 * 0x10000 for x in allhits)
    top = sorted(c.items(), key=lambda kv: -kv[1])[:8]
    rep.write("%s: %d hits, buckets %s\n" % (name, len(allhits), [(hex(k), v) for k, v in top]))
rep.close()
print(io.open(os.path.join(ROOT, "out", "ui_lang_blocks.txt"), encoding="utf-8").read())
