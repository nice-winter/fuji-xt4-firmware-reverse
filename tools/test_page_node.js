#!/usr/bin/env node
/* Minimal-DOM smoke test: run web/index.html's inline app script in Node,
   feed it the real modified build firmware, edit a string, and press "只校验". */
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const CORE = require(path.join(ROOT, 'web', 'patch-core.js'));

/* ------------------------------- tiny DOM ------------------------------- */
function El(tag) {
  this.tagName = (tag || 'div').toUpperCase();
  this.children = [];
  this._text = '';
  this._html = '';
  this.className = '';
  this.style = {};
  this._listeners = {};
  this.value = '';
  this.checked = false;
  this.disabled = false;
  this.files = [];
}
El.prototype.appendChild = function (c) { this.children.push(c); return c; };
El.prototype.removeChild = function (c) { this.children = this.children.filter(x => x !== c); };
El.prototype.remove = function () { };
El.prototype.insertAdjacentHTML = function () { };
El.prototype.querySelector = function () { return new El('span'); };
El.prototype.querySelectorAll = function () { return []; };
El.prototype.addEventListener = function (ev, fn) { (this._listeners[ev] = this._listeners[ev] || []).push(fn); };
El.prototype.dispatch = function (ev) { (this._listeners[ev] || []).forEach(f => f.call(this, { preventDefault() { }, target: this })); };
El.prototype.click = function () { this.dispatch('click'); };
function stripHtml(v) {
  return String(v)
    .replace(/<[^>]*>/g, '')
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&amp;/g, '&');
}
Object.defineProperty(El.prototype, 'innerHTML', {
  get() { return this._html; },
  set(v) { this._html = String(v); this._text = stripHtml(v); this.children = []; }
});
Object.defineProperty(El.prototype, 'textContent', {
  get() { return this._text + this.children.map(c => c.textContent).join(''); },
  set(v) { this._text = String(v); this.children = []; }
});
El.prototype.classList = {
  add() { }, remove() { }, contains() { return false; }, toggle() { }
};

const byId = {};
const IDS = ['drop', 'file', 'fileErr', 'infoSection', 'infoGrid', 'infoNote', 'poolSection',
  'poolsWrap', 'editorSection', 'poolName', 'search', 'onlyEdited', 'onlyCJK', 'pageSize',
  'btnExportJson', 'importJson', 'btnImportJson', 'btnResetAll', 'editStat', 'editorWrap',
  'rows', 'pager', 'prevPage', 'pageInfo', 'nextPage', 'charHint', 'outSection',
  'btnApply', 'btnCheck', 'applyHint', 'applyResult', 'log'];
IDS.forEach(id => { byId[id] = new El('div'); });
byId.pageSize.value = '100';

setupGlobals();
function setupGlobals() {
  global.window = global;
  global.FwPatchCore = CORE;
  global.document = {
    getElementById: id => byId[id] || (byId[id] = new El('div')),
    createElement: tag => new El(tag),
    body: new El('body'),
    querySelector: () => new El('div')
  };
  global.alert = msg => console.log('[alert]', msg);
  global.confirm = () => true;
}

/* ------------------------------- load page ------------------------------ */
const PAGE = process.argv[2] ? path.resolve(process.argv[2]) : path.join(ROOT, 'web', 'index.html');
console.log('page under test:', PAGE);
const html = fs.readFileSync(PAGE, 'utf8');
const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
if (blocks.length < 1) { console.error('no inline script found'); process.exit(1); }
blocks.forEach(b => eval(b));

/* ------------------------------- run flow ------------------------------- */
const buf = new Uint8Array(fs.readFileSync(path.join(ROOT, 'FWUP0024.DAT')));
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const fakeFile = { name: 'FWUP0024.DAT', arrayBuffer: () => Promise.resolve(ab) };

let failed = 0;
function check(cond, msg) {
  console.log((cond ? '  OK  ' : '  FAIL ') + msg);
  if (!cond) failed++;
}

console.log('== simulate file load ==');
byId.file.files = [fakeFile];
byId.file.dispatch('change');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

(async () => {
  await sleep(3500);
  check(byId.infoGrid.children.length >= 8, 'info grid rendered (' + byId.infoGrid.children.length + ' cells)');
  const poolTable = byId.poolsWrap.children[0];
  const poolBody = poolTable && poolTable.children.find(c => c.tagName === 'TBODY');
  check(!!poolBody && poolBody.children.length >= 20,
    'pool table rendered (' + (poolBody ? poolBody.children.length : 0) + ' rows)');
  check(/简体中文/.test(byId.poolName.textContent), 'SC pool auto-selected: ' + byId.poolName.textContent.slice(0, 40));

  const tbody = byId.rows;
  check(tbody.children.length === 100, 'first page shows 100 rows (' + tbody.children.length + ')');

  // find the row whose original text is 传感器清洁 (2nd row) and edit it
  let target = null;
  for (const tr of tbody.children) {
    if (tr.children[3] && tr.children[3].textContent === '传感器清洁') { target = tr; break; }
  }
  check(!!target, 'found row with 传感器清洁');
  if (target) {
    const inp = target.children[4].children[0];
    inp.value = '传感器除尘';
    inp.dispatch('input');
    check(/已修改 1 条/.test(byId.editStat.textContent), 'edit registered: ' + byId.editStat.textContent);
    check(/已修改/.test(target.children[5].textContent), 'row status shows 已修改');
  }

  // press "只校验" (no download)
  console.log('== press 只校验 ==');
  byId.btnCheck.dispatch('click');
  const logTxt = byId.log.textContent;
  console.log('---- log ----\n' + logTxt + '-------------');
  check(/通过/.test(logTxt), 'log reports checksum/read-back OK');
  check(/未改变/.test(logTxt), 'log reports file size unchanged');
  check(byId.applyResult.children.length > 0, 'result box rendered');

  // oversize guard: try a too-long replacement
  console.log('== oversize guard ==');
  const inp2 = target.children[4].children[0];
  inp2.value = '这是一个特别特别长的替换文本用来触发超长保护机制';
  inp2.dispatch('input');
  check(/太长|⚠/.test(target.children[5].textContent), 'oversize edit rejected: ' + target.children[5].textContent.slice(0, 60));
  check(/已修改 0 条/.test(byId.editStat.textContent), 'invalid edit not counted: ' + byId.editStat.textContent);

  // restore a valid edit and test the real download path (Blob capture)
  console.log('== download path (生成并下载) ==');
  inp2.value = '传感器除尘';
  inp2.dispatch('input');
  check(/已修改 1 条/.test(byId.editStat.textContent), 'valid edit restored: ' + byId.editStat.textContent);
  const captured = { blob: null, name: null };
  const origCreate = URL.createObjectURL;
  URL.createObjectURL = b => { captured.blob = b; return 'blob:test'; };
  URL.revokeObjectURL = () => { };
  byId.btnApply.dispatch('click');
  URL.createObjectURL = origCreate;
  check(!!captured.blob, 'download blob created');
  if (captured.blob) {
    const bytes = new Uint8Array(await captured.blob.arrayBuffer());
    check(bytes.length === buf.length, 'downloaded file size unchanged (' + bytes.length + ')');
    const ckField = (bytes[0x20C] | (bytes[0x20D] << 8) | (bytes[0x20E] << 16) | (bytes[0x20F] << 24)) >>> 0;
    const payload = CORE.decodePayload(bytes, 0x274);
    const ckCalc = CORE.checksumOf(payload, 0x2FC0020);
    check(ckField === ckCalc, 'download checksum valid (0x' + ckField.toString(16).toUpperCase() + ')');
    const rb = CORE.extractStrings(payload, 0x1FB3254 - 0x274, 0x1FB3264 - 0x274)[0];
    check(!!rb && rb.text === '传感器除尘', 'download contains edited text: ' + (rb && rb.text));
  }

  // export JSON path
  console.log('== export JSON path ==');
  const cap2 = { blob: null };
  URL.createObjectURL = b => { cap2.blob = b; return 'blob:test2'; };
  byId.btnExportJson.dispatch('click');
  URL.createObjectURL = origCreate;
  if (cap2.blob) {
    const j = JSON.parse(await cap2.blob.text());
    check(j.length === 1 && j[0].new === '传感器除尘', 'exported JSON has 1 edit: ' + JSON.stringify(j[0]).slice(0, 80));
  } else check(false, 'export JSON blob created');

  console.log(failed === 0 ? '\nALL PAGE CHECKS PASSED' : '\n' + failed + ' PAGE CHECK(S) FAILED');
  process.exit(failed === 0 ? 0 : 1);
})();