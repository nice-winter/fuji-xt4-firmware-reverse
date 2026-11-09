#!/usr/bin/env node
/* Version-independence check: run core detection on both firmware builds. */
'use strict';
const fs = require('fs');
const path = require('path');
const core = require(path.join(__dirname, '..', 'web', 'patch-core.js'));

const files = process.argv.slice(2);
for (const f of files) {
  const u8 = new Uint8Array(fs.readFileSync(f));
  const t0 = Date.now();
  const st = core.analyze(u8);
  const sc = core.pickBestPool(st.pools, 'zh-Hans');
  const cjk = sc ? sc.strings.filter(s => /[\u4E00-\u9FFF]/.test(s.text)).length : 0;
  console.log(path.basename(f));
  console.log('  size=%d  os=%d  version=%s  checksum=0x%s  payloadOffset=0x%s  mainBody=0x%s  verified=%s',
    u8.length, st.header.os, st.header.versionText, st.header.checksum.toString(16).toUpperCase(),
    st.payloadOffset.toString(16).toUpperCase(), st.mainBodyLen.toString(16).toUpperCase(), st.checksumOk);
  console.log('  pools=%d  SC=%s..%s  records=%d  CJK=%d  (%d ms)',
    st.pools.length,
    sc ? '0x' + (sc.start + st.payloadOffset).toString(16).toUpperCase() : '-',
    sc ? '0x' + (sc.end + st.payloadOffset).toString(16).toUpperCase() : '-',
    sc ? sc.strings.length : 0, cjk, Date.now() - t0);
}
