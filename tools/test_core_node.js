#!/usr/bin/env node
/* Node test for web/patch-core.js against the real modified build firmware. */
'use strict';
const fs = require('fs');
const path = require('path');
const core = require(path.join(__dirname, '..', 'web', 'patch-core.js'));

const DAT = path.join(__dirname, '..', 'FWUP0024.DAT');
const OUT = path.join(__dirname, '..', 'out', 'patched_js.DAT');

function hex(n) { return '0x' + (n >>> 0).toString(16).toUpperCase().padStart(8, '0'); }
function assert(cond, msg) {
  if (!cond) { console.error('FAIL: ' + msg); process.exitCode = 1; }
  else console.log('  OK  ' + msg);
}

console.log('== load ==');
const buf = new Uint8Array(fs.readFileSync(DAT));
console.log('file:', DAT.split(path.sep).pop(), buf.length, 'bytes');

console.log('== analyze ==');
const t0 = Date.now();
const st = core.analyze(buf);
console.log('  analyze took', Date.now() - t0, 'ms');
console.log('  header:', JSON.stringify({
  os: st.header.os, version: st.header.versionText, checksum: hex(st.header.checksum),
  payloadOffset: hex(st.payloadOffset), mainBodyLen: st.mainBodyLen ? hex(st.mainBodyLen) : null
}));
assert(st.header.os === 6, 'os_type == 6');
assert(st.header.versionText === '2.12', 'version == 2.12');
assert(st.payloadOffset === 0x274, 'payload offset == 0x274');
assert(st.mainBodyLen === 0x2FC0020, 'main body length == 0x2FC0020');
assert(st.checksumOk === true, 'checksum formula validated');

console.log('== pools ==');
console.log('  detected', st.pools.length, 'pools');
for (const p of st.pools) {
  console.log('   ', hex(p.start), hex(p.start + 0x274), '..', hex(p.end + 0x274),
    core.langLabel(p.lang).padEnd(10), 'records=' + p.strings.length,
    'coverage=' + p.coverage.toFixed(2));
}
const sc = core.pickBestPool(st.pools, 'zh-Hans');
if (!sc) { console.error('FAIL: no Simplified Chinese pool detected'); process.exit(1); }
console.log('  SC pool: file', hex(sc.start + 0x274), '..', hex(sc.end + 0x274),
  'bytes=' + (sc.end - sc.start), 'records=' + sc.strings.length);
assert(sc.start + 0x274 === 0x1FB3244, 'SC pool starts at file 0x1FB3244');
assert(sc.end + 0x274 === 0x1FC05F8, 'SC pool ends at file 0x1FC05F8');
assert(sc.strings.length === 4041, 'SC pool has 4041 records');
const cjkCount = sc.strings.filter(s => /[\u4E00-\u9FFF]/.test(s.text)).length;
assert(cjkCount === 3160, 'SC pool has 3160 CJK strings (got ' + cjkCount + ')');

console.log('== edit ==');
const rec = {};
for (const s of sc.strings) rec[s.off] = { slot: s.slot, text: s.text };
const body = st.payload;
const edits = [
  { off: 0x1FB3244 - 0x274, text: '自动对焦模式' },        // unchanged
  { off: 0x1FB3254 - 0x274, text: '传感器除尘' },          // same length
  { off: 0x1FB32B4 - 0x274, text: '信息显示改' },          // +1 char, within slot
  { off: 0x1FB332C - 0x274, text: '删除数据' },            // shorter
];
const results = core.applyEdits(body, edits, rec);
for (const r of results) console.log('   ', hex(r.off + 0x274), r.ok ? 'OK  ' : 'FAIL', r.msg || (r.oldText + ' -> ' + edits.find(e => e.off === r.off).text));
assert(results.every(r => r.ok), 'all edits applied');

console.log('== build patched file ==');
const patched = core.buildPatched(buf, st);
console.log('  new checksum field:', hex(patched.checksum));
assert(patched.buf.length === buf.length, 'file size unchanged');

console.log('== verify ==');
const ver = core.verifyPatched(patched.buf, st, edits);
console.log('  checksum field/calc:', hex(ver.checksumField), '/', hex(ver.checksumCalc));
assert(ver.checksumOk, 'checksum round-trip OK');
assert(ver.allReadBackOk, 'edited strings read back OK');
for (const rb of ver.readBack) console.log('   ', hex(rb.off + 0x274), JSON.stringify(rb.text), rb.match ? 'match' : 'MISMATCH');

fs.writeFileSync(OUT, Buffer.from(patched.buf));
console.log('== written', OUT, '==');

/* diff summary */
let diffs = 0, runs = 0, inRun = false;
for (let i = 0; i < buf.length; i++) {
  const d = buf[i] !== patched.buf[i];
  if (d) { diffs++; if (!inRun) { runs++; inRun = true; } }
  else inRun = false;
}
console.log('changed bytes:', diffs, 'in', runs, 'runs');
