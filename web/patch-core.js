/*
 * FWUP0024 language-patch core (browser + Node)
 * ------------------------------------------------------------------
 * Pure logic, no DOM.  The page (index.html) only does UI.
 *
 * File model (verified on X-T4 FWUP0024 aefix_1106 / affix_1108):
 *   bytes 0x000 .. payloadOffset-1   plaintext container header
 *   bytes payloadOffset .. EOF       firmware payload, bit-inverted (XOR 0xFF)
 *   payload[0 .. mainBodyLen)        protected by the checksum field in the header
 *                                   checksum = 0xFFFFFFFF - (sum of logical bytes) mod 2^32
 *   localisation text                "FDL Font" bundles inside the payload;
 *                                    each language owns a block of NUL-terminated
 *                                    UTF-16LE strings (2/4-byte aligned records)
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.FwPatchCore = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var CODE_SIZES = { 1: 64, 2: 128, 3: 512, 4: 512, 5: 512, 6: 512, 7: 512, 8: 512 };
  var FDL_MAGIC = [0x46, 0x44, 0x4C, 0x20, 0x46, 0x6F, 0x6E, 0x74, 0x00]; // "FDL Font\0"

  /* ------------------------------------------------------------------ bytes */
  function u32(d, o) {
    return (d[o] | (d[o + 1] << 8) | (d[o + 2] << 16) | (d[o + 3] << 24)) >>> 0;
  }
  function w32(d, o, v) {
    d[o] = v & 0xFF; d[o + 1] = (v >>> 8) & 0xFF;
    d[o + 2] = (v >>> 16) & 0xFF; d[o + 3] = (v >>> 24) & 0xFF;
  }
  function u16(d, o) { return d[o] | (d[o + 1] << 8); }

  /* --------------------------------------------------------- char classes */
  function allowedUnit(c) {
    if (c >= 0x20 && c <= 0x7E) return true;              // ASCII printable
    if (c >= 0x00A0 && c <= 0x00FF) return true;          // Latin-1
    if (c === 0x00B0 || c === 0x00D7 || c === 0x2103) return true;
    if (c >= 0x0370 && c <= 0x03FF) return true;          // Greek
    if (c >= 0x0400 && c <= 0x04FF) return true;          // Cyrillic
    if (c >= 0x0590 && c <= 0x05FF) return true;          // Hebrew
    if (c >= 0x0600 && c <= 0x06FF) return true;          // Arabic
    if (c >= 0x0900 && c <= 0x097F) return true;          // Devanagari
    if (c >= 0x0E00 && c <= 0x0E7F) return true;          // Thai
    if (c >= 0x2000 && c <= 0x206F) return true;          // general punctuation
    if (c >= 0x2460 && c <= 0x24FF) return true;          // circled numbers
    if (c >= 0x3000 && c <= 0x303F) return true;          // CJK punctuation
    if (c >= 0x3040 && c <= 0x30FF) return true;          // kana
    if (c >= 0x3400 && c <= 0x4DBF) return true;          // CJK ext A
    if (c >= 0x4E00 && c <= 0x9FFF) return true;          // CJK
    if (c >= 0xAC00 && c <= 0xD7AF) return true;          // Hangul
    if (c >= 0xD800 && c <= 0xDFFF) return false;         // no surrogates
    if (c >= 0xE000 && c <= 0xF8FF) return true;          // PUA (inline glyph refs)
    if (c >= 0xFF00 && c <= 0xFFEF) return true;          // fullwidth forms
    return false;
  }

  var SIMP_ONLY = new Set(('设关 闭 择 图 线 电 车 门 马 鸟 鱼 风 飞 东 乐 书 买 卖 开 时 间 问 题 显 数 据 删 确 认 选 单 语 画 质 镜 头 对 闪 灯 连 滤 胶 拟 录 摄 传 输 转 换 后 从 来 个 们 会 动 员 银 钟 钢 铁 长 阳 阴 际 陆 陈 险 队 阶 难 雪 云 雾 静 响 页 顺 须 领 颜 饭 饮 驾 验 骑 鸡 鹅 鹰 黄 齐 齿 龙 龟 边 达 过 还 这 进 连 远 违 软 载 车 轮 转 轻 较 输 辑 辞 农 冲 决 况 冻 净 减 凑 几 凤 凭 凯 击 划 刘 则 刚 创 别 到 剧 办 务 动 劳 势 勋 匀 区 医 华 协 单 卖 卫 厂 历 压 厌 厅 县 参 双 发 变 叠 叶 号 叹 吗 听 启 员 呐 呜 响 哑 唤 啊 唱 喷 吗 嘱 团 园 围 图 圆 圣 场 坏 块 坚 坛 坝 坟 坠 垄 型 垒 垦 垫 场 声 壳 处 备 复 够 头 夹 夺 奋 奖 妆 妇 妈 娱 婴 媳 嫁 嫌 孙 学 宁 宝 实 宠 审 宪 宫 宽 宾 对 寻 导 寿 将 尔 尘 尝 尧 尸 尽 层 届 属 岁 岂 岗 岛 岭 峡 崭 巩 币 帅 师 帐 带 帮 广 庆 库 应 废 开 异 弃 张 弹 强 归 当 录 彻 径 忆 忧 怀 态 怜 总 恋 恳 恶 恼 悦 悬 惊 惧 惨 惭 惯 愿 懒 戏 战 户 扑 执 扩 扫 扬 扰 抚 抛 抢 护 报 担 拟 拢 拣 拥 拨 择 挂 挤 挥 捞 损 换 据 捷 授 掉 掌 排 掘 挂 采 释 钟 钥 钢 钱 铁 铜 银 铺 链 销 锁 锅 锋 错 键 镇 镜 长 门 闪 闭 问 间 闻 阁 阅 队 阳 阴 陆 陈 险 随 隐 难 雏 雾 静 页 顺 须 项 顾 顿 预 领 频 题 颜 额 风 飞 饭 饮 饰 饱 饺 馆 马 驱 驶 驻 驾 骂 验 骑 骄 骗 骤 骨 高 鱼 鲜 鸟 鸡 鸣 鹅 鹰 黄 黑 齐 齿 龙 龟'));
  var TRAD_ONLY = new Set(('設關閉擇圖線電車門馬鳥魚風飛東樂書買賣開時間問題顯示數據刪確認選單語畫質鏡頭對閃燈連濾膠擬錄攝傳輸轉換後來個們會動員銀鐘鋼鐵長陽陰際陸陳險隊階難雪雲霧靜響頁順須領顏飯飲駕驗騎雞鵝鷹黃齊齒龍龜邊達過還這進遠違軟載輛輪轉輕較輸輯辭農衝決況凍淨減湊幾鳳憑凱擊劃劉則剛創別到劇辦務勞勢勳勻區醫華協單衛廠歷壓厭廳縣參雙發變疊葉號嘆嗎聽啟員吶嗚響啞喚啊唱噴囑團園圍圓聖場壞塊堅壇壩墳墜壟型壘墾墊聲殼處備復夠頭夾奪奮獎妝婦媽娛嬰媳嫁嫌孫學寧寶實寵審憲宮寬賓尋導壽將爾塵嘗堯屍盡層屆屬歲豈崗島嶺峽嶄鞏幣帥師帳帶幫廣慶庫應廢異棄張彈強歸當錄徹徑憶憂懷態憐總戀懇惡惱悅懸驚懼慘慚慣願懶戲戰戶撲執擴掃揚擾撫拋搶護報擔攏揀擁撥揀掛擠揮撈損據捷授掉掌排掘採釋鑰錢銅鋪鏈銷鎖鍋鋒錯鍵鎮鏡閃聞閣閱隨隱雛項顧頓預頻額飾飽餃館驅駛駐罵騙驟鮮鳴'));

  function isCJK(c) { return c >= 0x4E00 && c <= 0x9FFF; }
  function isKana(c) { return c >= 0x3040 && c <= 0x30FF; }
  function isHangul(c) { return c >= 0xAC00 && c <= 0xD7AF; }
  function isCyr(c) { return c >= 0x0400 && c <= 0x04FF; }
  function isArab(c) { return c >= 0x0600 && c <= 0x06FF; }
  function isThai(c) { return c >= 0x0E00 && c <= 0x0E7F; }
  function isLatinLetter(c) { return (c >= 0x41 && c <= 0x5A) || (c >= 0x61 && c <= 0x7A); }

  /* -------------------------------------------------------------- strings */
  function decodeString(payload, off, end) {
    var chars = [], p = off, c;
    while (p + 1 < end) {
      c = payload[p] | (payload[p + 1] << 8);
      if (c === 0) {
        return { text: String.fromCharCode.apply(null, chars), len: (p - off) + 2 };
      }
      if (!allowedUnit(c) || chars.length > 500) return null;
      chars.push(c);
      p += 2;
    }
    return null;
  }

  /* -------------------------------------------------------------- header */
  function parseHeader(buf) {
    if (buf.length < 0x40) throw new Error('文件太小，不是 FWUP 固件');
    var os = u32(buf, 0);
    var codeSize = CODE_SIZES[os];
    if (!codeSize) throw new Error('未知的 os_type = ' + os + '（本工具支持 1..8）');
    var version1 = u32(buf, 4 + codeSize);
    var version2 = u32(buf, 4 + codeSize + 4);
    var checksum = u32(buf, 4 + codeSize + 8);
    var tail = u32(buf, 4 + codeSize + 12);
    var headerSize = codeSize + 20;
    // model code: 512 (or 64/128) bytes of ASCII-hex, may itself be hex text
    var modelRaw = '';
    for (var i = 4; i < 4 + codeSize; i++) {
      var b = buf[i];
      modelRaw += (b >= 32 && b < 127) ? String.fromCharCode(b) : '.';
    }
    var versionText = version1 + '.' + (version2 < 16 ? '0' : '') + version2.toString(16).toUpperCase();
    return {
      os: os, codeSize: codeSize, version1: version1, version2: version2,
      versionText: versionText, checksum: checksum, tail: tail,
      headerSize: headerSize, checksumOffset: 4 + codeSize + 8,
      modelRaw: modelRaw
    };
  }

  /* ----------------------------------------------------- payload / checksum */
  function decodePayload(buf, payloadOffset) {
    var n = buf.length - payloadOffset;
    var p = new Uint8Array(n);
    for (var i = 0; i < n; i++) p[i] = buf[payloadOffset + i] ^ 0xFF;
    return p;
  }

  function checksumOf(payload, len) {
    var s = 0;
    for (var i = 0; i < len; i++) s += payload[i];
    s = s % 4294967296;
    return ((0xFFFFFFFF - s) + 4294967296) % 4294967296;
  }

  function encodeFile(orig, payloadOffset, checksumOffset, payload) {
    var out = new Uint8Array(orig.length);
    out.set(orig.subarray(0, payloadOffset), 0);
    for (var i = 0; i < payload.length; i++) out[payloadOffset + i] = payload[i] ^ 0xFF;
    return out;
  }

  /* main-body length = first region offset; find it by matching the checksum */
  function detectMainBody(payload, checksum, headerU32s) {
    var STEP = 4096;
    var n = payload.length;
    var pref = new Float64Array(Math.floor(n / STEP) + 2);
    var s = 0;
    for (var i = 0; i < n; i++) {
      s += payload[i];
      if (((i + 1) % STEP) === 0) pref[(i + 1) / STEP] = s;
    }
    var cands = {}, list = [];
    for (var k = 0; k < headerU32s.length; k++) {
      var v = headerU32s[k];
      if (v > 0 && v <= n && !cands[v]) { cands[v] = 1; list.push(v); }
    }
    list.push(0x2FC0020);             // known fallback for this generation
    list.sort(function (a, b) { return a - b; });
    for (var j = 0; j < list.length; j++) {
      var L = list[j];
      if (L <= 0 || L > n) continue;
      var base = Math.floor(L / STEP);
      var sum = base < pref.length ? pref[base] : 0;
      for (var q = base * STEP; q < L; q++) sum += payload[q];
      var ck = ((0xFFFFFFFF - (sum % 4294967296)) + 4294967296) % 4294967296;
      if (ck === checksum) return { len: L, sum: sum % 4294967296 };
    }
    return null;
  }

  /* ------------------------------------------------------- FDL bundles */
  function findFdlBundles(payload) {
    var out = [], n = payload.length;
    var L = FDL_MAGIC.length;
    for (var i = 0; i + L <= n; i++) {
      if (payload[i] !== 0x46) { continue; }
      var ok = true;
      for (var j = 1; j < L; j++) { if (payload[i + j] !== FDL_MAGIC[j]) { ok = false; break; } }
      if (ok) { out.push(i); i += L - 1; }
    }
    return out;
  }

  /* --------------------------------------------------- text-pool detection */
  function windowCounts(payload, start, end) {
    var c = { text: 0, han: 0, kana: 0, hangul: 0, cyr: 0, arab: 0, thai: 0, latin: 0, nul: 0, units: 0 };
    for (var p = start; p + 1 < end; p += 2) {
      var u = payload[p] | (payload[p + 1] << 8);
      c.units++;
      if (u === 0) { c.nul++; continue; }
      if (!allowedUnit(u)) continue;
      c.text++;
      if (isCJK(u)) c.han++;
      else if (isKana(u)) c.kana++;
      else if (isHangul(u)) c.hangul++;
      else if (isCyr(u)) c.cyr++;
      else if (isArab(u)) c.arab++;
      else if (isThai(u)) c.thai++;
      else if (isLatinLetter(u)) c.latin++;
    }
    return c;
  }

  function extractStrings(payload, start, end) {
    var out = [], off = start;
    while (off + 1 < end) {
      var r = decodeString(payload, off, end);
      if (r && r.text.length) { out.push({ off: off, nbytes: r.len, text: r.text }); off += r.len; }
      else off += 2;
    }
    for (var i = 0; i < out.length; i++) {
      var next = i + 1 < out.length ? out[i + 1].off : out[i].off + out[i].nbytes;
      out[i].slot = next - out[i].off;
    }
    return out;
  }

  function clusterByGap(list, maxGap) {
    if (!list.length) return [];
    var clusters = [[list[0]]];
    for (var i = 1; i < list.length; i++) {
      var prev = clusters[clusters.length - 1];
      var last = prev[prev.length - 1];
      if (list[i].off - (last.off + last.nbytes) <= maxGap) prev.push(list[i]);
      else clusters.push([list[i]]);
    }
    return clusters;
  }

  function langCharTester(lang) {
    if (lang === 'zh-Hans' || lang === 'zh-Hant') return isCJK;
    if (lang === 'ja') return function (u) { return isKana(u) || isCJK(u); };
    if (lang === 'ko') return function (u) { return isHangul(u) || isCJK(u); };
    if (lang === 'ru') return isCyr;
    if (lang === 'ar') return isArab;
    if (lang === 'th') return isThai;
    return isLatinLetter;
  }

  function classifyStrings(strings) {
    var c = { total: 0, han: 0, simp: 0, trad: 0, kana: 0, hangul: 0, cyr: 0, arab: 0, thai: 0, latin: 0, chars: 0 };
    for (var i = 0; i < strings.length; i++) {
      var t = strings[i].text;
      c.total++;
      for (var j = 0; j < t.length; j++) {
        var u = t.charCodeAt(j);
        c.chars++;
        if (isCJK(u)) { c.han++; if (SIMP_ONLY.has(t[j])) c.simp++; else if (TRAD_ONLY.has(t[j])) c.trad++; }
        else if (isKana(u)) c.kana++;
        else if (isHangul(u)) c.hangul++;
        else if (isCyr(u)) c.cyr++;
        else if (isArab(u)) c.arab++;
        else if (isThai(u)) c.thai++;
        else if (isLatinLetter(u)) c.latin++;
      }
    }
    var lang = 'xx';
    if (c.hangul > c.chars * 0.10) lang = 'ko';
    else if (c.kana > c.chars * 0.05) lang = 'ja';
    else if (c.han > c.chars * 0.10) lang = (c.simp > c.trad) ? 'zh-Hans' : 'zh-Hant';
    else if (c.cyr > c.chars * 0.30) lang = 'ru';
    else if (c.arab > c.chars * 0.30) lang = 'ar';
    else if (c.thai > c.chars * 0.30) lang = 'th';
    else if (c.latin > c.chars * 0.30) lang = 'en';
    return { counts: c, lang: lang };
  }

  function langLabel(lang) {
    return {
      'zh-Hans': '简体中文', 'zh-Hant': '繁體中文', 'ja': '日本語', 'ko': '한국어',
      'ru': 'Русский', 'ar': 'العربية', 'th': 'ไทย', 'en': 'Latin / English', 'xx': '未知'
    }[lang] || lang;
  }

  /**
   * Detect every localisation text pool in the payload.
   * Strategy: only look inside "FDL Font" bundles -> 4 KiB window language
   * statistics -> candidate zones -> string extraction -> coverage filter
   * (real pools >= ~0.9, font bitmap areas <= ~0.5) -> gap clustering.
   */
  function detectPools(payload, opts) {
    opts = opts || {};
    var minCoverage = opts.minCoverage || 0.70;
    var minRecords = opts.minRecords || 40;
    var W = 4096;
    var bundles = findFdlBundles(payload);
    if (!bundles.length) bundles = [0];
    var pools = [];
    for (var bi = 0; bi < bundles.length; bi++) {
      var bs = bundles[bi];
      var be = (bi + 1 < bundles.length) ? bundles[bi + 1] : payload.length;
      var zones = [], cur = null;
      for (var off = bs; off + W <= be; off += W) {
        var c = windowCounts(payload, off, off + W);
        var strong = (c.han > W / 2 * 0.15) || (c.kana > W / 2 * 0.15) ||
                     (c.hangul > W / 2 * 0.15) || (c.cyr > W / 2 * 0.15) ||
                     (c.arab > W / 2 * 0.15) || (c.thai > W / 2 * 0.15) ||
                     (c.latin > W / 2 * 0.35 && c.text > W / 2 * 0.55);
        if (strong) {
          if (cur && off - cur.end <= W) cur.end = off + W;
          else { cur = { start: off, end: off + W }; zones.push(cur); }
        }
      }
      for (var zi = 0; zi < zones.length; zi++) {
        var zs = Math.max(0, zones[zi].start - W), ze = Math.min(payload.length, zones[zi].end + W);
        var all = extractStrings(payload, zs, ze);
        if (all.length < minRecords) continue;
        var span = 0;
        for (var k = 0; k < all.length; k++) span += all[k].nbytes;
        var coverage = span / (ze - zs);
        if (coverage < minCoverage) continue;
        var clusters = clusterByGap(all, 64);
        clusters.sort(function (a, b) { return b.length - a.length; });
        var best = clusters[0];
        var cls = classifyStrings(best);
        // trim leading/trailing records that carry no character of the pool language
        // (font bitmap tables next to the pool can decode as short junk strings)
        var has = langCharTester(cls.lang);
        var first = -1, last = -1;
        for (var ri = 0; ri < best.length; ri++) {
          var ht = false;
          for (var rj = 0; rj < best[ri].text.length; rj++) {
            if (has(best[ri].text.charCodeAt(rj))) { ht = true; break; }
          }
          if (ht) { if (first < 0) first = ri; last = ri; }
        }
        if (first >= 0 && (first > 0 || last < best.length - 1)) {
          var s0 = best[first].off;
          var e0 = best[last].off + best[last].nbytes;
          best = best.filter(function (r) { return r.off >= s0 && r.off < e0; });
        }
        var startOff = best[0].off;
        var lastRec = best[best.length - 1];
        pools.push({
          start: startOff, end: lastRec.off + lastRec.nbytes, lang: cls.lang,
          counts: cls.counts, coverage: coverage, strings: best,
          bundle: bs
        });
      }
    }
    // drop pools contained in a bigger one with the same language family
    pools.sort(function (a, b) { return b.strings.length - a.strings.length; });
    var out = [];
    for (var i = 0; i < pools.length; i++) {
      var p = pools[i], dup = false;
      for (var j = 0; j < out.length; j++) {
        var q = out[j];
        var overlap = Math.min(p.end, q.end) - Math.max(p.start, q.start);
        if (overlap > 0 && overlap > (p.end - p.start) * 0.5) { dup = true; break; }
      }
      if (!dup) out.push(p);
    }
    out.sort(function (a, b) { return a.start - b.start; });
    return out;
  }

  function pickBestPool(pools, lang) {
    lang = lang || 'zh-Hans';
    var best = null;
    for (var i = 0; i < pools.length; i++) {
      if (pools[i].lang === lang && (!best || pools[i].strings.length > best.strings.length)) best = pools[i];
    }
    return best || pools[0] || null;
  }

  /* --------------------------------------------------------------- edits */
  function encodeUtf16LE(text) {
    var out = new Uint8Array(text.length * 2);
    for (var i = 0; i < text.length; i++) {
      var c = text.charCodeAt(i);
      out[2 * i] = c & 0xFF;
      out[2 * i + 1] = (c >>> 8) & 0xFF;
    }
    return out;
  }

  function charsetOf(strings) {
    var set = new Set();
    for (var i = 0; i < strings.length; i++) {
      var t = strings[i].text;
      for (var j = 0; j < t.length; j++) set.add(t[j]);
    }
    return set;
  }

  /**
   * edits: [{off, text}]  (off = payload-relative offset of the record)
   * rec:   map off -> {slot, text} from the selected pool
   */
  function applyEdits(payload, edits, rec) {
    var results = [];
    for (var i = 0; i < edits.length; i++) {
      var e = edits[i];
      var r = rec[e.off];
      if (!r) { results.push({ off: e.off, ok: false, msg: '记录不存在（可能选错了语言池）' }); continue; }
      var enc;
      try { enc = encodeUtf16LE(e.text); } catch (err) { results.push({ off: e.off, ok: false, msg: '编码失败' }); continue; }
      if (enc.length === 0) { results.push({ off: e.off, ok: false, msg: '不能为空' }); continue; }
      var bad = null;
      for (var ci = 0; ci < e.text.length; ci++) {
        var cu = e.text.charCodeAt(ci);
        if (!allowedUnit(cu)) { bad = e.text[ci] + ' (U+' + cu.toString(16).toUpperCase() + ')'; break; }
      }
      if (bad) { results.push({ off: e.off, ok: false, msg: '包含不支持的字符：' + bad }); continue; }
      if (enc.length + 2 > r.slot) {
        results.push({ off: e.off, ok: false, msg: '太长：需要 ' + (enc.length + 2) + ' B，槽位只有 ' + r.slot + ' B（最多 ' + Math.floor((r.slot - 2) / 2) + ' 字）' });
        continue;
      }
      for (var q = 0; q < enc.length; q++) payload[e.off + q] = enc[q];
      for (var z = e.off + enc.length; z < e.off + r.slot; z++) payload[z] = 0;
      results.push({ off: e.off, ok: true, slot: r.slot, used: enc.length + 2, oldText: r.text });
    }
    return results;
  }

  /* ------------------------------------------------------------- one-shot */
  function analyze(buf) {
    var header = parseHeader(buf);
    var headerU32s = [];
    var lim = Math.min(buf.length, 0x400);
    for (var o = 0; o + 4 <= lim; o += 4) headerU32s.push(u32(buf, o));
    var payloadOffset = null, mainBody = null;
    var candidates = [0x274, header.headerSize, 0x214, 0x378, header.headerSize + 0x60];
    for (var i = 0; i < candidates.length; i++) {
      var po = candidates[i];
      if (po <= 0 || po >= buf.length) continue;
      var pay = decodePayload(buf, po);
      var mb = detectMainBody(pay, header.checksum, headerU32s);
      if (mb) { payloadOffset = po; mainBody = mb; break; }
    }
    if (payloadOffset === null) {
      // fall back: assume type-6 layout and report checksum mismatch
      payloadOffset = header.headerSize + 0x60;
      var pay2 = decodePayload(buf, payloadOffset);
      var mb2 = detectMainBody(pay2, header.checksum, headerU32s);
      if (mb2) mainBody = mb2;
    }
    var payload = decodePayload(buf, payloadOffset);
    var pools = detectPools(payload);
    return {
      header: header, payloadOffset: payloadOffset, payload: payload,
      mainBodyLen: mainBody ? mainBody.len : null,
      checksumOk: !!mainBody,
      pools: pools
    };
  }

  function buildPatched(orig, state) {
    var ck = checksumOf(state.payload, state.mainBodyLen);
    var out = encodeFile(orig, state.payloadOffset, state.header.checksumOffset, state.payload);
    w32(out, state.header.checksumOffset, ck);
    return { buf: out, checksum: ck };
  }

  function verifyPatched(outBuf, state, edits) {
    var header = parseHeader(outBuf);
    var payload = decodePayload(outBuf, state.payloadOffset);
    var ck = checksumOf(payload, state.mainBodyLen);
    var readBack = [];
    for (var i = 0; i < edits.length; i++) {
      var e = edits[i];
      var r = decodeString(payload, e.off, Math.min(payload.length, e.off + 4096));
      readBack.push({ off: e.off, text: r ? r.text : null, match: !!r && r.text === e.text });
    }
    return {
      checksumField: header.checksum,
      checksumCalc: ck,
      checksumOk: header.checksum === ck,
      versionText: header.versionText,
      readBack: readBack,
      allReadBackOk: readBack.every(function (x) { return x.match; }),
      sizeOk: outBuf.length === (state.origLength || outBuf.length)
    };
  }

  return {
    CODE_SIZES: CODE_SIZES,
    parseHeader: parseHeader,
    decodePayload: decodePayload,
    checksumOf: checksumOf,
    detectMainBody: detectMainBody,
    findFdlBundles: findFdlBundles,
    detectPools: detectPools,
    pickBestPool: pickBestPool,
    extractStrings: extractStrings,
    classifyStrings: classifyStrings,
    charsetOf: charsetOf,
    applyEdits: applyEdits,
    analyze: analyze,
    buildPatched: buildPatched,
    verifyPatched: verifyPatched,
    langLabel: langLabel,
    allowedUnit: allowedUnit
  };
});
