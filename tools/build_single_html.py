#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a single self-contained HTML (core JS inlined) from web/index.html."""
import io, subprocess, sys, os

ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "web", "index.html")
CORE = os.path.join(ROOT, "web", "patch-core.js")
SINGLE = os.path.join(ROOT, "web", "FWUP语言补丁工具.html")
NODE = os.environ.get("NODE_BIN") or "node"

html = io.open(INDEX, encoding="utf-8").read()
core = io.open(CORE, encoding="utf-8").read()

needle = '<script src="./patch-core.js"></script>'
if needle not in html:
    print("ERROR: script tag not found")
    sys.exit(1)
out = html.replace(needle, "<script>\n/* ---- patch-core.js (inlined) ---- */\n" + core + "\n</script>")
io.open(SINGLE, "w", encoding="utf-8").write(out)

print("index.html      : %d bytes" % len(html.encode("utf-8")))
print("patch-core.js   : %d bytes" % len(core.encode("utf-8")))
print("single file     : %s (%d bytes)" % (SINGLE, len(out.encode("utf-8"))))

# syntax check every inline block
import re
import os
blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", out, re.S)
print("inline blocks   :", len(blocks))
tmp = os.path.join(ROOT, "out", "_single_block.js")
rc = 0
for i, b in enumerate(blocks):
    io.open(tmp, "w", encoding="utf-8").write(b)
    r = subprocess.run([NODE, "--check", tmp], capture_output=True, text=True)
    print("  block %d: %d bytes, node --check -> %s" % (i, len(b), "OK" if r.returncode == 0 else "FAIL"))
    if r.returncode != 0:
        print(r.stderr)
        rc = 1
os.remove(tmp)
sys.exit(rc)
