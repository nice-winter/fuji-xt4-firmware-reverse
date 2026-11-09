#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the inline <script> from web/index.html and syntax-check it with node."""
import io, re, subprocess, os, sys
import os


ROOT = os.environ.get("XT4_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "web", "index.html")
TMP = os.path.join(ROOT, "out", "_page_inline.js")
NODE = os.environ.get("NODE_BIN") or "node"

html = io.open(HTML, encoding="utf-8").read()
blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
print("inline script blocks:", len(blocks))
js = "\n".join(blocks)
io.open(TMP, "w", encoding="utf-8").write(js)
print("bytes:", len(js))
r = subprocess.run([NODE, "--check", TMP], capture_output=True, text=True)
print("node --check exit:", r.returncode)
if r.stdout.strip():
    print(r.stdout)
if r.stderr.strip():
    print(r.stderr)
os.remove(TMP)
sys.exit(r.returncode)
