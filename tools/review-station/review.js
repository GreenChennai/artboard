/* review.js — 审片台播放器
 *
 * 前提（main.js 已确认）：整片没有 rAF 循环，只暴露
 *     window.SEEK(t)      同步渲染一帧
 *     window.MV = { duration, fps:60, moves, hits, cuts, flash, ... }
 * 所以"播放"就是自己按 performance.now 推进 t 再调 SEEK，
 * "拖时间条"就是直接 SEEK(那个时刻) —— 与渲 PNG 走的是同一条路径。
 */
(function () {
  "use strict";

  /* 查控件。缺元素时返回一个"什么都吃"的存根，而不是抛
   * "Cannot set properties of null" —— 那样 init() 会**静默半瘫**：
   * 后面所有接线都不执行，页面看着正常但按钮全不响应（最难查的一类故障）。
   * 缺失的 id 记进 MISSING，init 末尾汇总显示。 */
  var MISSING = {};
  var STUB = null;
  function mkStub() {
    var f = function () { return STUB; };
    return new Proxy({}, {
      get: function (t, k) {
        if (k === "style" || k === "classList" || k === "dataset" ||
            k === "children" || k === "firstChild") return STUB;
        if (k === "length" || k === "clientWidth" || k === "offsetWidth") return 0;
        if (k === "textContent" || k === "innerHTML" || k === "value") return "";
        return f;
      },
      set: function () { return true; }
    });
  }
  var $ = function (id) {
    var e = document.getElementById(id);
    if (e) return e;
    MISSING[id] = 1;
    if (!STUB) STUB = mkStub();
    return STUB;
  };
  var DUR = 211.913;

  var S = {
    t: 0, playing: false, speed: 1, loop: false,
    last: 0, raf: 0, ms: 0, errs: [],
    scale: "fit", diffMode: "side", refOn: false,
    audioOn: true, drift: 0, lod: "全量", fps: 60
  };

  /* 性能面板的读数（放顶层：window.__rv 要用） */
  function perfLine() {
    var b = 1000 / S.fps;
    return [
      "最近一帧    " + S.ms.toFixed(1) + " ms",
      "滑动平均    " + PERF.avg.toFixed(1) + " ms   预算 " + b.toFixed(1) + " ms",
      "档位计数    " + PERF.drawn + " 渲染 / " + PERF.skip + " 跳帧",
      "帧率锁      " + S.fps + " fps   ±1 帧 " + (1000 / S.fps).toFixed(2) + " ms",
      "最慢一帧    " + PERF.worst.toFixed(1) + " ms",
      "当前档位    " + S.lod +
        (PERF.auto ? "（自适应 1/" + PERF.tuneAdec + " + 缓存" + PERF.tuneReuse + " 帧）" : ""),
    ].join("\n");
  }
  function paintPerf() { var b = $("pf-box"); if (b) b.textContent = perfLine(); }

  /* ══════════════ 字幕：渲染层 / 字幕轴 / 编辑器 ══════════════
   * 三件事：
   *  ① **渲染层**：审片台自己的字幕（影片那份画在 canvas 上，这里不碰它），
   *    固定在底部安全区，字号/颜色/描边/背景/行距/对齐/位置都能调。
   *  ② **字幕轴**：时间条下面多一条轨，与时间轴**同一套 left/宽度映射**，
   *    块可以拖（改 t0）、拖右边缘（改时长）、选中编辑。
   *  ③ **编辑器**：逐字时间足够细 —— 每段自带 t/e（92 段、1~2 秒一段），
   *    所以拆分按字符比例插值；开头退格 = 并入上一段；中间 Enter = 拆成两句。
   *  数据落盘：review/字幕轨.json（服务端 action=subs），
   *  也能直接导出 review/world.execute(me);.zh.srt。
   */
  /* ⚠️ 字体名这里必须用**单引号**：这些字符串会被塞进
   * style="font:34px …" 的双引号属性里，用双引号会把属性提前截断
   * （症状：字幕能显示但字号/位置/描边全部没生效）。
   * 注意这跟 film.css 无关 —— 影片那份字体是 canvas 的 ctx.font。 */
  var FONTS = {
    yh: "\'Microsoft YaHei\', \'微软雅黑\', \'PingFang SC\', sans-serif",
    src: "\'Noto Sans SC\', \'Source Han Sans SC\', \'Microsoft YaHei\', sans-serif",
    mono: "\'Fira Code\', \'JetBrains Mono\', monospace",
    serif: "\'Songti SC\', \'SimSun\', \'Noto Serif SC\', serif"
  };
  /* 默认外观按"通用字幕"：白字、**描边关**、底部安全距离 64px。
   * 描边默认关是刻意的 —— 通用字幕不需要描边；要强调某句时再在
   * 「外观与位置」里开。（用户 2026-10-06 的要求） */
  var SUB = {
    on: true, sel: -1, lines: [], file: "—", lang: "en",
    /* 自动保存**默认关**：关着时改动只在预览里，必须点「保存字幕」才写文件 */
    autoSave: false, saving: false,
    st: { font: "yh", size: 34, color: "#ffffff", stroke: 0, strokeColor: "#000000",
          bg: "#000000", bga: 0, pad: 6, bottom: 64, align: "center",
          lh: 1.35, maxw: 1500 }
  };
  var SUB_STYLE_DEFAULT = JSON.parse(JSON.stringify(SUB.st));

  /* ────────────── 字幕文件（轨）管理 ──────────────
   * 原来的"中文 / English"下拉是死功能（两条轨都来自 SRT 探测，实际内容一样），
   * 换成真正的"字幕文件切换"：内置影片歌词 + 工程 review 里的 .srt/.vtt/.ass
   * + 本机临时导入的任意文件，任意两个都能来回切换编辑与对比。
   * 每个文件各自记住自己的行与外观（切换时把当前份存回去）。 */
  SUB.files = {};
  SUB.cur = "film";
  var TRACK_MAX = 24;              /* 磁盘上最多列这么多个文件，够用 */

  function trackKey(name) { return name.replace(/[^a-zA-Z0-9_.\-]/g, "_"); }
  function cloneLines(ls) {
    return ls.map(function (l) {
      return { id: l.id, t: l.t, e: l.e, s: l.s, y: l.y };
    });
  }
  function subStash() {           /* 把当前份存回 files[cur] */
    var f = SUB.files[SUB.cur];
    if (!f) return;
    f.lines = cloneLines(SUB.lines);
    f.st = JSON.parse(JSON.stringify(SUB.st));
  }
  function subStashAll() { subStash(); saveSubs(); }
  function trackList() {
    return Object.keys(SUB.files).map(function (k) { return SUB.files[k]; });
  }
  function subFileOptions() {
    var sel = $("sb-file");
    if (!sel) return;
    var h = [], cur = SUB.cur;
    var list = trackList().sort(function (a, b) {
      if (a.kind === "film") return -1;
      if (b.kind === "film") return 1;
      return a.name < b.name ? -1 : 1;
    });
    for (var i = 0; i < list.length; i++) {
      var f = list[i];
      var mark = f.kind === "film" ? "内置" : (f.kind === "local" ? "本机" : "工程");
      /* 磁盘文件在切过去时才读，没读过的别显示成「0 段」（看着像空文件） */
      var cnt = (f.kind === "disk" && !f.lines.length)
        ? "未读" : (f.lines.length + " 段");
      h.push('<option value="' + f.key + '"' + (f.key === cur ? " selected" : "") +
        ">" + esc(f.name) + "（" + mark +
        (f.fmt ? " " + f.fmt.toUpperCase() : "") + " · " + cnt +
        (f.dirty ? " · 已改" : "") + "）</option>");
    }
    sel.innerHTML = h.join("");
  }
  function subFileInfo() {
    var box = $("sb-info");
    if (!box) return;
    var over = SUB.lines.filter(function (l) { return l.e > DUR + 1e-6; });
    var bi = SUB.lines.filter(function (l) { return /\n/.test(l.s || ""); });
    var past = SUB.lines.filter(function (l) { return l.t >= DUR - 1e-6; });
    var f = SUB.files[SUB.cur];
    box.innerHTML = "当前：<b>" + esc(f ? f.name : "—") + "</b> · " +
      SUB.lines.length + " 段 · 片长 " + DUR.toFixed(2) + "s" +
      (bi.length
        ? ' · <span style="color:#7ee787">双语 ' + bi.length + " 段含换行" +
          "（Alt+Enter 插入换行）</span>"
        : "") +
      (over.length
        ? ' · <span style="color:#ffb454">超出片长 ' + over.length + " 条" +
          (past.length ? "（其中 " + past.length + " 条整条在片外，导出时会丢弃）" : "") +
          "</span>"
        : " · 全部在片长内");
  }
  function subSwitchFile(key, quiet) {
    if (key === SUB.cur) return;
    var f0 = SUB.files[key];
    if (!f0) { log("没有这个字幕文件：" + key); return; }
    /* 工程里还没读过的文件：先读再切（否则切过去是一片空） */
    if (f0.kind === "disk" && !f0.lines.length && f0.url) {
      subLoadDisk(f0.key).then(function (ok) {
        if (ok) subSwitchFile(key, quiet);
        else log("读不到 " + f0.name + "，仍在当前文件");
      });
      return;
    }
    subStash();
    var f = SUB.files[key];
    SUB.cur = key;
    SUB.lines = f.lines;
    if (f.st) SUB.st = f.st;
    paintSubBar(); paintSubList(); paintSubs(); subSel(-1);
    subFileOptions(); subFileInfo();
    if (!quiet && !SUB.autoSave && f.unsaved) {
      log("⚠ " + f.name + " 有未保存的改动（自动保存关着）—— 内容还在页面上，" +
          "切回来点「保存字幕」才会写文件");
    }
    paintSaveState();
    cfgTouch();                 /* 记住上次打开的是哪个文件 */
    if (!quiet) {
      log("切换到字幕文件：" + f.name + "（" + f.lines.length + " 段）");
    }
  }
  function subAddFile(name, kind, url, lines) {
    var key = kind + ":" + trackKey(name);
    if (SUB.files[key]) { subSwitchFile(key); return key; }
    SUB.files[key] = { key: key, name: name, kind: kind, url: url || "",
                        lines: lines || [], st: null, dirty: false };
    subFileOptions();
    log("已加入字幕文件：" + name + "（" + (lines || []).length + " 段）");
    return key;
  }
  function subLoadDisk(key) {
    var f = SUB.files[key];
    if (!f || f.kind !== "disk" || !f.url) return Promise.resolve(false);
    return api(f.url).then(function (r) {
      if (!(r && r.ok)) {
        log("读不到 " + f.name + "（" + ((r && r.error) || "未知") + "）");
        return false;
      }
      var ps = parseSub(r.text, f.name);
      f.fmt = ps.fmt;
      f.lines = ps.lines;
      f.dirty = false;
      if (key === SUB.cur) {
        SUB.lines = f.lines;
        paintSubBar(); paintSubList(); paintSubs();
      }
      subFileOptions(); subFileInfo();
      if (!f.lines.length) {
        /* 0 条必须说清楚，否则"切了没反应"会被当成界面坏了 */
        log("⚠ " + f.name + "：识别为 " + ps.fmt.toUpperCase() +
            "，但**一条字幕都没解析出来**（文件 " + r.text.length +
            " 字节）。请确认它是可解析的字幕文件。");
        err(f.name + " 解析出 0 条字幕");
        return true;
      }
      log(f.name + "：" + ps.fmt.toUpperCase() + " · 读到 " + f.lines.length +
          " 段" + (ps.fmt === "ass" ? "（ASS 样式未导入，只取时间与文本）" : ""));
      return true;
    });
  }
  function subScanDisk() {
    return api("../tools/review_server.py?action=subfiles").then(function (r) {
      if (!(r && r.ok)) return;
      var fs = (r.files || []).slice(0, TRACK_MAX), n = 0;
      fs.forEach(function (x) {
        var key = "disk:" + trackKey(x.name);
        if (SUB.files[key]) return;
        SUB.files[key] = { key: key, name: x.name, kind: "disk", url: x.url,
                           lines: [], st: null, dirty: false, size: x.size };
        n++;
      });
      if (n) { subFileOptions(); log("工程里发现 " + n + " 个字幕文件，可直接切换编辑"); }
    });
  }
  function subImportLocal(file) {
    var rd = new FileReader();
    rd.onload = function () {
      var ps = parseSub(String(rd.result || ""), file.name);
      if (!ps.lines.length) {
        log("⚠ " + file.name + "：识别为 " + ps.fmt.toUpperCase() +
            "，但没解析出字幕");
        err(file.name + " 里没有可解析的字幕");
        return;
      }
      log("导入 " + file.name + "：" + ps.fmt.toUpperCase() + " · " +
          ps.lines.length + " 段");
      var key = subAddFile(file.name, "local", "", ps.lines);
      SUB.files[key].fmt = ps.fmt;
      subSwitchFile(key);
      subFileOptions(); subFileInfo(); paintSubBar(); paintSubList(); paintSubs();
    };
    rd.readAsText(file, "utf-8");
  }

  /* ── 撤销栈：拆分 / 并入 / 删除 / 改时间 / 改文本 都能 Ctrl+Z ── */
  var UNDO = [];
  function pushUndo(tag) {
    /* 空轨不压栈：否则"撤销"会回到一个空字幕轨，等于把整条轨删了 */
    if (!SUB.lines.length) return;
    UNDO.push({ tag: tag || "", lines: SUB.lines.map(function (l) {
      return { id: l.id, t: l.t, e: l.e, s: l.s, y: l.y }; }), sel: SUB.sel });
    if (UNDO.length > 60) UNDO.shift();
    var c = $("dk-count");
    if (c) c.textContent = "";
  }
  function undo() {
    if (!UNDO.length) { log("没有可撤销的字幕操作"); return; }
    var u = UNDO.pop();
    SUB.lines = u.lines;
    subSel(u.sel);
    paintSubBar(); paintSubs(); paintSubList();
    log("已撤销：" + (u.tag || "上一步"));
  }

  function subsFromFilm() {
    var L = (window.FILM && window.FILM.lyrics) || [];
    SUB.lines = L.map(function (l, i) {
      return { id: "L" + i, t: l.t, e: (l.e == null ? l.t + 2 : l.e), s: l.s, y: 0 };
    }).sort(function (a, b) { return a.t - b.t; });
  }
  /* ══════════════ 字幕文件解析：SRT / VTT / ASS(SSA) ══════════════
   * 按**内容**判别格式（同一扩展名里也可能塞着别的格式），扩展名只作兜底。
   * 之前只有 SRT 解析器：`.ass` 里根本没有 `-->`，一条都匹配不到 → 0 段，
   * 而 0 段时界面几乎没变化，看起来就像"切了没反应"。 */
  function subClean(t) {
    return String(t || "")
      .replace(/^\uFEFF/, "")            /* BOM */
      .replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  }
  function subTime(t) {
    /* 统一吃 0:00:01,390 / 0:00:01.390 / 0:00:01.39（ASS 厘秒）/ 1:23:45 */
    var m = /(?:(\d+):)?(\d{1,2}):(\d{1,2})[,.](\d{1,3})/.exec(t);
    if (!m) return null;
    var frac = m[4] || "0";
    while (frac.length < 3) frac += "0";          /* .39 → 390ms */
    return (+(m[1] || 0)) * 3600 + (+m[2]) * 60 + (+m[3]) +
           (+frac) / 1000;
  }
  function subPickCjk(arr) {
    var cjk = arr.filter(function (x) { return /[\u4e00-\u9fff]/.test(x); });
    return (cjk.length ? cjk : arr).join(" ").replace(/\s+/g, " ").trim();
  }
  function subId(i) { return "L" + i + "_" + Date.now().toString(36); }

  /* ---- SRT / VTT：靠 `-->` 时间行 ---- */
  function parseCue(text) {
    var out = [], blocks = text.split(/\n\s*\n/);
    for (var i = 0; i < blocks.length; i++) {
      var lines = blocks[i].split("\n").filter(function (x) {
        return x.trim() !== ""; });
      if (!lines.length) continue;
      var hi = 0;
      if (lines[0].indexOf("-->") < 0) {
        /* VTT 的 cue 标识行 / SRT 的序号行 */
        if (lines.length > 1 && lines[1].indexOf("-->") >= 0) hi = 1;
        else continue;                             /* NOTE / STYLE / 头部 */
      }
      var ab = lines[hi].split("-->");
      var t0 = subTime(ab[0]), t1 = subTime(ab[1] || "");
      if (t0 == null || t1 == null) continue;
      /* ⚠️ 用 "\n" 连接各行而不是 " "：双语字幕（.zh-en.srt / .zh.ass）
       * 每条 cue 是"英文一行 + 中文一行"，压成空格就毁掉了对照关系。 */
      var body = lines.slice(hi + 1)
                  .map(function (x) {
                    return x.replace(/<[^>]+>/g, "")   /* VTT 富文本标签 */
                            .replace(/[ \t]+$/, "");
                  })
                  .join("\n")
                  .replace(/[ \t]{2,}/g, " ")
                  .replace(/^\n+|\n+$/g, "");
      if (!body.trim()) continue;
      out.push({ id: subId(out.length), t: t0, e: t1, s: body, y: 0 });
    }
    return out;
  }

  /* ---- ASS / SSA：Events 段的 Dialogue 行 ----
   * ⚠️ 必须**先用正则把 start / end 整体摘出来**，不能一上来就按逗号切字段：
   * 本工程里的 .ass 是当年由 SRT 转出的，时间码写成了 SRT 风格的逗号毫秒
   * `Dialogue: 0,00:00:00,030,00:00:01,390,lyric,,0,0,0,,文本`
   * 按逗号切会把时间戳自己切开 → 字段错位 → 正文取不到 → **一条都解析不出来**。 */
  var ASS_HEAD = /^Dialogue\s*:\s*[^,]*,\s*[0-9:.,]+\s*,\s*[0-9:.,]+\s*,\s*([\s\S]*)$/i;
  /* ⚠️ 时间戳正则必须精确：早先用 /[0-9]+:[0-9:.,]+/g，字符类里含逗号，
   * 会把**两个**时间戳吃成一个匹配 → 只匹配到 1 个 → 整行放弃解析。 */
  var ASS_TIME = /\d{1,3}:\d{1,2}:\d{1,2}(?:[.,]\d{1,3})?/g;
  function parseAss(text) {
    var out = [], fields = null, sec = "";
    var lines = text.split("\n");
    for (var i = 0; i < lines.length; i++) {
      var ln = lines[i].trim();
      if (!ln) continue;
      var sm = /^\[([^\]]+)\]/.exec(ln);
      if (sm) { sec = sm[1].toLowerCase(); continue; }
      if (/^format\s*:/i.test(ln) && sec === "events") {
        fields = ln.slice(ln.indexOf(":") + 1).split(",")
                   .map(function (x) { return x.trim().toLowerCase(); });
        continue;
      }
      if (!/^dialogue\s*:/i.test(ln)) continue;
      var m = ASS_HEAD.exec(ln);
      if (!m) continue;
      var times = ln.slice(ln.indexOf(":") + 1).match(ASS_TIME) || [];
      if (times.length < 2) continue;
      var t0 = subTime(times[0]), t1 = subTime(times[1]);
      if (t0 == null || t1 == null) continue;
      /* 尾巴里跳过 Text 之前的字段，剩下的就是正文（允许含逗号） */
      /* 尾巴里要跳过的字段数 = Text 在 Format 里的下标 − 3
       * （layer / start / end 已经被上面的正则整体吃掉了） */
      var pre = (fields ? fields.indexOf("text") : 9) - 3;
      if (!(pre >= 0)) pre = 0;
      var rest = m[1], k;
      for (k = 0; k < pre; k++) {
        var c = rest.indexOf(",");
        if (c < 0) { rest = ""; break; }
        rest = rest.slice(c + 1);
      }
      var txt = (rest || "")
        .replace(/\{[^}]*\}/g, "")              /* 覆盖标签 {\i1} */
        .replace(/\\h/g, " ")                   /* 硬空格 */
        .replace(/[ \t]{2,}/g, " ")              /* ① 先归一横向空白 */
        .replace(/[ \t]*\\[Nn][ \t]*/g, "\n")     /* ② \N 折行 → 真换行 */
        .replace(/[ \t]+\n/g, "\n")              /* ③ 收拾换行两侧 */
        .replace(/\n[ \t]+/g, "\n")
        .replace(/\n{2,}/g, "\n")
        .replace(/^\s+|\s+$/g, "");
      /* ⚠️ 顺序很重要：\s 里含 \n，所以"横向空白归一"必须在"\N → 换行"
         之前做完；早先把 \s+ 放在后面，把刚生成的换行又压回了空格。 */
      if (!txt) continue;
      out.push({ id: subId(out.length), t: t0, e: t1, s: txt, y: 0 });
    }
    return out;
  }

  function subFormat(text, name) {
    var ext = (String(name || "").match(/\.([a-z0-9]+)$/i) || [])[1];
    ext = (ext || "").toLowerCase();
    if (/^\s*WEBVTT/i.test(text)) return "vtt";
    if (/^\s*\[Script Info\]/im.test(text) ||
        /^\s*\[V4\+? Styles\]/im.test(text)) return "ass";
    if (ext === "ass" || ext === "ssa") return "ass";
    if (ext === "vtt") return "vtt";
    if (ext === "srt") return "srt";
    return text.indexOf("-->") >= 0 ? "srt" : "ass";
  }
  function parseSub(text, name) {
    var t = subClean(text), fmt = subFormat(t, name);
    var lines = fmt === "ass" ? parseAss(t) : parseCue(t);
    return { fmt: fmt, lines: lines };
  }
  /* 兼容旧调用点 */
  function parseSrt(txt) { return parseSub(txt, "x.srt").lines; }

  function subAt(t) {
    for (var i = 0; i < SUB.lines.length; i++) {
      var l = SUB.lines[i];
      if (t >= l.t && t < l.e) return l;
    }
    return null;
  }
  function subCss(ov) {
    var st = SUB.st;
    return "font:" + st.size + "px " + FONTS[st.font] +
      ";color:" + st.color +
      ";line-height:" + st.lh +
      ";text-align:" + st.align +
      ";max-width:" + st.maxw + "px" +
      ";padding:" + st.pad + "px " + (st.pad + 6) + "px" +
      ";background:rgba(" + hex2rgb(st.bg) + "," + (st.bga / 100).toFixed(2) + ")" +
      (st.stroke > 0 ? (";-webkit-text-stroke:" + st.stroke + "px " + st.strokeColor) : "") +
      ";bottom:" + (st.bottom + (ov && ov.y || 0)) + "px";
  }
  function hex2rgb(h) {
    h = String(h).replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return ((n >> 16) & 255) + "," + ((n >> 8) & 255) + "," + (n & 255);
  }
  function esc(t) {
    return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* 每帧只更新"当前该显示的那一条"，DOM 复用，不重建列表 */
  var subLastKey = "";
  function paintSubs() {
    var lay = $("rv-sublayer");
    if (!lay) return;
    if (!SUB.on) {
      if (subLastKey !== "off") { lay.innerHTML = ""; subLastKey = "off"; }
      return;
    }
    var l = subAt(S.t);
    var key = l ? (l.id + "|" + l.s.length + "|" + l.s) : "";
    if (key === subLastKey) return;
    subLastKey = key;
    if (!l) { lay.innerHTML = ""; return; }
    lay.innerHTML = '<div class="sb-line" style="' + esc(subCss(l)) + '">' + esc(l.s) + "</div>";
  }

  /* 字幕轴：块 = 一段；宽度按时间映射，与主时间条一致 */
  function paintSubBar() {
    var bar = $("rv-subbar");
    if (!bar) return;
    if (!SUB.on || !SUB.lines.length) {
      bar.innerHTML = '<div id="rv-subbar-empty">字幕（点「字幕」页开启）</div>';
      return;
    }
    var h = ['<div id="rv-subbar-empty" hidden></div>'];
    for (var i = 0; i < SUB.lines.length; i++) {
      var l = SUB.lines[i];
      var a = posOf(l.t), w = Math.max(0.2, (l.e - l.t) / viewSpan() * 100);
      if (a > 102 || a + w < -2) continue;             /* 视野外不画 */
      h.push('<i data-i="' + i + '" class="' +
        (i === SUB.sel ? "on sel-edge " : "") +
        (l.e > DUR + 1e-6 ? "over " : "") +
        (subDrag && subDrag.i === i && subDrag.snapped ? "snap " : "") +
        (SUB.on ? "" : "off") + '" style="left:' + a + "%;width:" + w + '%" title="' +
        esc(fmt(l.t) + " " + l.s) + '"><b>' + esc(l.s.slice(0, 18)) + "</b><u></u></i>");
    }
    bar.innerHTML = h.join("");
  }
  /* 列表每一条都能直接改字 —— 不再有"选中段 + 文本框"那一套。
   * 两类高亮必须区分开：
   *   rv-cur  正在播放的那句（蓝，与时间轴播放头同色系）
   *   rv-sel  你选中的那句（琥珀，编辑对象）
   * 之前两者共用 rv-cur，扫一眼分不清"正在放"和"正在改"。 */
  function paintSubList() {
    var box = $("sb-list");
    if (!box) return;
    if (!SUB.lines.length) {
      box.innerHTML = '<div class="rv-dim" style="padding:8px">没有字幕。点「重置」从影片歌词导入。</div>';
      return;
    }
    var cur = subAt(S.t);
    box.innerHTML = SUB.lines.map(function (l, i) {
      return '<div class="rv-item' + (i === SUB.sel ? " rv-sel" : "") +
        (cur && cur.id === l.id ? " rv-cur" : "") + '" data-i="' + i + '">' +
        '<span class="rt">' + fmt(l.t) + "</span>" +
        '<span class="rn" contenteditable="plaintext-only" spellcheck="false"' +
        ' data-i="' + i + '">' + (esc(l.s) || "") + "</span>" +
        '<span class="rz">' + (l.e - l.t).toFixed(1) + "s" +
        (l.y ? " ↑" + l.y : "") +
        (l.e > DUR + 1e-6
          ? ' <b class="rz-over" title="结束时间超出片长 ' +
            DUR.toFixed(2) + 's，导出时会被截断">⟨超出片长⟩</b>'
          : "") + "</span>" +
        '<span class="rx" data-del="' + i + '" title="删除本段">×</span></div>';
    }).join("");
    subMark();
    SUB_CUR_ID = "";        /* 强制 subMarkCur 重新扫一遍 */
    subMarkCur();
  }

  /* ---------- 编辑操作 ---------- */
  /* 只切换行 class，**不重绘列表** —— 列表里每条都是 contenteditable，
   * 一旦 innerHTML 换掉，焦点就没了，用户打的字会丢。 */
  function subMark() {
    var rows = document.querySelectorAll("#sb-list .rv-item");
    for (var i = 0; i < rows.length; i++) {
      rows[i].classList.toggle("rv-sel", i === SUB.sel);
    }
  }
  function subSel(i) {
    SUB.sel = i;
    paintSubBar();
    subMark();
  }
  /* "目前段"高亮同样只切 class：paint() 每帧都会调到这里，
   * 一旦重绘 innerHTML，contenteditable 行的焦点会被冲掉。 */
  var SUB_CUR_ID = "";
  function subMarkCur() {
    var c = subAt(S.t), id = c ? c.id : "";
    if (id === SUB_CUR_ID) return;
    SUB_CUR_ID = id;
    var rows = document.querySelectorAll("#sb-list .rv-item"),
        lines = SUB.lines;
    for (var i = 0; i < rows.length; i++) {
      var l = lines[i];
      rows[i].classList.toggle("rv-cur", !!l && l.id === id);
    }
  }

  function subSplit(i, k) {
    var l = SUB.lines[i];
    if (!l) return false;
    k = Math.max(0, Math.min(l.s.length, k));
    if (k <= 0 || k >= l.s.length) return false;
    var a = l.s.slice(0, k), b = l.s.slice(k);
    var span = l.e - l.t, f = k / l.s.length;
    /* 边界空白归一：拆在词中间就什么都不动；拆在词边界就把那个空格留在
     * 前半段末尾（而不是丢给新句开头 —— 新句以空格开头会让字幕视觉偏右）。
     * "并入"是原样拼接，所以这里留一个空格，拆开再并回来就一字不差还原。 */
    /* 头尾的换行/空白要清掉，否则拆出来的句子会带空行 */
    var aTrim = a.replace(/[\s\u00a0]+$/, ""), bTrim = b.replace(/^[\s\u00a0]+/, "");
    var cut = a.slice(aTrim.length) + b.slice(0, b.length - bTrim.length);
    l.s = /\s/.test(cut) ? aTrim + " " : aTrim;
    l.e = l.t + span * f;
    SUB.lines.splice(i + 1, 0, { id: l.id + "b" + Date.now().toString(36),
                                 t: l.e, e: l.e + span * (1 - f), s: bTrim, y: 0 });
    return true;
  }
  /* 并入上一段：文本拼接、上一段吃掉这段时间。
   * ⚠️ 拼接是**原样**的：行首退格的语义是"删掉那个换行符"，换行本身就是
   * 分隔符，再补一个空格就会每并一次多一个空格（这是实际被报出来的 bug）。
   * 配合 subSplit 保留前半段行尾空格的写法，拆开再并回来能一字不差还原。 */
  function subMergePrev(i) {
    if (i <= 0 || !SUB.lines[i - 1]) return false;
    var p = SUB.lines[i - 1], c = SUB.lines[i];
    p.s = p.s + c.s;
    p.e = Math.max(p.e, c.e);
    p.y = p.y || c.y || 0;
    SUB.lines.splice(i, 1);
    return true;
  }
  function subDel(i) {
    if (i < 0 || !SUB.lines[i]) return;
    SUB.lines.splice(i, 1);
    subSel(-1);
  }
  function subSort() { SUB.lines.sort(function (a, b) { return a.t - b.t; }); }

  /* ---------- 字幕轴拖动：移动改时间 / 右边缘改时长 ---------- */
  var subDrag = null;
  function subT(ev) {
    var r = $("rv-subbar").getBoundingClientRect();
    return timeAt(Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)));
  }
  function subDown(ev) {
    var n = ev.target.closest ? ev.target.closest("#rv-subbar i") : null;
    if (!n) return;
    var i = parseInt(n.dataset.i, 10);
    /* ⚠️ 顺序：几何必须在 `subSel()` **之前**取 —— subSel 会重绘字幕轴，
     * 刚拿到的 block 元素就脱离文档了，getBoundingClientRect() 变 0×0，
     * 于是 `(clientX - 0) > (0 - 7)` 恒成立 → 每次拖动都被当成"改时长"。
     * 也不能用 `ev.offsetX`：命中子元素（<b>/<u>）时它是相对子元素的。 */
    var br = n.getBoundingClientRect();
    var x = ev.clientX - br.left;
    /* ③ **只有选中的块**能调两端；未选中的块点了只是选中它。
     *   而且两端都能拖（之前只有右端，左端拖不了）。 */
    var isSel = (i === SUB.sel);
    var edge = null;
    if (SUB.on && isSel && x > br.width - 7) edge = "tail";
    else if (SUB.on && isSel && x < 7) edge = "head";
    if (!isSel) subSel(i);
    if (edge) pushUndo(edge === "head" ? "调开始时间" : "调结束时间");
    subDrag = {
      i: i, edge: edge,
      t0: subT(ev), lt: SUB.lines[i].t, le: SUB.lines[i].e
    };
    ev.preventDefault();
  }
  /* ④ 磁力吸附：把字幕头尾吸到相邻字幕上，省得手动对齐。
   * 阈值用**像素**换算成秒（SNAP_PX），这样放大轨道后手感一样细。 */
  var SNAP_PX = 9;
  function snapT() {
    var r = $("rv-subbar").getBoundingClientRect();
    return Math.max(0.02, SNAP_PX / Math.max(1, r.width) * viewSpan());
  }
  function subNeighbours(i) {
    var a = SUB.lines[i - 1] || null, b = SUB.lines[i + 1] || null;
    return { prev: a, next: b };
  }
  function subMove(ev) {
    if (!subDrag) return;
    var t = subT(ev), d = t - subDrag.t0;
    var i = subDrag.i, l = SUB.lines[i];
    if (!l) return;
    var sn = snapT(), nb = subNeighbours(i), snapped = false;
    var CAP2 = DUR + 3600;                 /* 同上：允许超出片长，只设宽松上限 */
    if (subDrag.edge === "tail") {
      l.e = Math.max(l.t + 0.15, Math.min(CAP2, subDrag.le + d));
      /* 尾端吸到下一句的开头（不留缝） */
      if (nb.next && Math.abs(l.e - nb.next.t) < sn) {
        l.e = nb.next.t; snapped = true;
      }
    } else if (subDrag.edge === "head") {
      l.t = Math.min(l.e - 0.15, Math.max(0, Math.min(CAP2, subDrag.lt + d)));
      /* 头端吸到上一句的结尾 */
      if (nb.prev && Math.abs(l.t - nb.prev.e) < sn) {
        l.t = nb.prev.e; snapped = true;
      }
    } else {
      /* ⚠️ 这里**故意不**用 `Math.min(DUR - 时长, d)` 夹住：用户要求字幕
       * 可以排到 MV 片长之外（编辑期不限），由导出/渲染按实际片长裁剪。
       * 上限给一个宽松的天花板，避免拖出几小时的荒唐值。 */
      var CAP = DUR + 3600;
      var dt = Math.max(-l.t + 0.02, Math.min(CAP - (l.e - l.t), d));
      l.t = subDrag.lt + dt;
      l.e = subDrag.le + dt;
      if (nb.prev && Math.abs(l.t - nb.prev.e) < sn) {
        var sh = nb.prev.e - l.t;
        l.t += sh; l.e += sh; snapped = true;
      } else if (nb.next && Math.abs(l.e - nb.next.t) < sn) {
        var sh2 = nb.next.t - l.e;
        l.t += sh2; l.e += sh2; snapped = true;
      }
    }
    l.t = Math.round(l.t * 1e3) / 1e3;
    l.e = Math.round(l.e * 1e3) / 1e3;
    subDrag.snapped = snapped;
    paintSubBar(); paintSubList(); paintSubs();
  }
  function subUp() {
    if (!subDrag) return;
    subDrag = null;
    subSort(); subSel(SUB.sel >= 0 ? SUB.lines.findIndex(function (x) {
      return x.id === (SUB.lines[SUB.sel] || {}).id; }) : -1);
    markUnsaved();
  }

  /* ---------- 存取 ---------- */
  function subsData() {
    return { film: "world.execute(me);", style: SUB.st, lines: SUB.lines };
  }
  /* ────────────── 字幕的保存语义（2026-10-07 改） ──────────────
   * 之前是"每次改动都自动写 字幕轨.json"，用户看不出"到底存没存"。
   * 现在两条路泾渭分明：
   *   自动保存 = 关（默认）→ 改动只在**预览**里，必须点「保存字幕」才落盘
   *   自动保存 = 开          → 任何改动都实时写入对应的字幕文件
   * 落盘目标是 `review/字幕导出/<轨名>.srt`（与「导出 SRT」同一套逻辑，
   * 顺带按实际片长裁剪）；`字幕轨.json` 只作为页面工作态存档一起更新。 */
  function subTargetName() {
    var f = SUB.files[SUB.cur];
    return ((f ? f.name : "world.execute(me);.en")
      .replace(/\.(ass|ssa|vtt|srt)$/i, "") + ".srt");
  }
  function paintSaveState() {
    var d = $("sb-dirty"), sv = $("sb-save"), au = $("sb-auto");
    var f = SUB.files[SUB.cur];
    var un = !!(f && f.unsaved);
    if (d) {
      d.textContent = un ? "有未保存的改动" : "已保存";
      d.className = "rv-dim " + (un ? "dirty" : "saving");
    }
    if (sv) {
      sv.classList.toggle("need", un);
      sv.title = un ? ("有未保存的改动 —— 点这里写入 " + subTargetName())
                    : ("把当前字幕写入 " + subTargetName());
    }
    if (au) {
      au.textContent = SUB.autoSave ? "自动保存：开" : "自动保存：关";
      au.classList.toggle("rv-on", !!SUB.autoSave);
    }
    var fi = $("sb-fileinfo");
    if (fi && !SUB.saving) {
      fi.textContent = "目标文件：review/字幕导出/" + subTargetName() +
        "（" + SUB.lines.length + " 段）" +
        (SUB.autoSave ? " · 自动保存已开" : " · 自动保存关，修改需手动保存");
    }
  }
  function markUnsaved() {
    var f = SUB.files[SUB.cur];
    if (f) { f.unsaved = true; f.dirty = true; }
    paintSaveState();
    subFileOptions();
    if (SUB.autoSave) saveSubs();
  }
  function saveSubs(quiet) {
    subStash();
    SUB.saving = true;
    var name = subTargetName();
    /* ① 写出真正的字幕文件（按片长裁剪）② 顺带更新页面工作态存档 */
    api("review_server.py?action=srt", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ srt: subsSrt(), dur: DUR, name: name })
    }).then(function (r) {
      SUB.saving = false;
      if (r && r.ok) {
        var f = SUB.files[SUB.cur];
        if (f) { f.unsaved = false; f.dirty = false; }
        if (!quiet) {
          log("✓ 字幕已保存 → " + r.file +
            (r.dur ? "（按片长 " + DUR.toFixed(2) + "s 裁剪：截断 " +
                      (r.clipped || 0) + " / 丢弃 " + (r.dropped || 0) + "）" : ""));
        }
      } else if (r && r.queued) {
        log("⏳ 服务断开，保存已排队（恢复后自动写入）");
      } else {
        log("保存失败：" + ((r && r.error) || "未知"));
      }
      paintSaveState();
      subFileOptions();
    });
    api("../tools/review_server.py?action=subs", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(subsData())
    }).then(function (r) {
      if (!r.ok && !r.queued) { /* 工作态存档失败不打扰用户，字幕文件才是正事 */ }
    });
  }
  function loadSubs() {
    return api("../tools/review_server.py?action=subs").then(function (r) {
      if (r.ok && r.data && r.data.lines && r.data.lines.length) {
        SUB.lines = r.data.lines;
        if (r.data.style) SUB.st = r.data.style;
      } else {
        subsFromFilm();
      }
      /* ⚠️ 状态文字要写 sb-fileinfo：**不能**写 $("sb-file") —— 那是
       * <select>，给它设 textContent 会把它内部所有 <option> 全部清空，
       * 下拉就变成一个只有文字的空壳（切文件当然没反应）。 */
      if ($("sb-fileinfo")) {
        $("sb-fileinfo").textContent = r.ok
          ? (r.file + "（" + SUB.lines.length + " 段）" + (r.data && r.data.lines && r.data.lines.length ? "" : " · 尚无存档，用的是影片歌词"))
          : "读不到存档，用的是影片歌词";
      }
      /* 内置轨的快照要跟着更新，否则列表里一直显示 0 段 */
      if (SUB.cur === "film") {
        SUB.files.film.lines = cloneLines(SUB.lines);
        SUB.files.film.dirty = false;
      }
      subFileOptions(); subFileInfo(); paintSaveState();
      paintSubBar(); paintSubList(); paintSubs(); subSel(-1);
    });
  }
  function srtTime(t) {
    /* ⚠️ 毫秒要**四舍五入**：`1.2 % 1` 在浮点下是 0.19999999999999996，
     * 直接 Math.floor 会写成 199（每次导出都少 1ms）。先归整到毫秒再拆分。 */
    var ms = Math.max(0, Math.round(t * 1000));
    var h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60,
        sec = Math.floor(ms / 1000) % 60, msf = ms % 1000;
    function p2(v) { return (v < 10 ? "0" : "") + v; }
    return p2(h) + ":" + p2(m) + ":" + p2(sec) + "," +
      ("00" + msf).slice(-3);
  }
  function subsSrt() {
    var out = [];
    SUB.lines.forEach(function (l, i) {
      out.push(String(i + 1));
      out.push(srtTime(l.t) + " --> " + srtTime(l.e));
      out.push(l.s);
      out.push("");
    });
    return out.join("\n");
  }

  /* ══════════════ 审片意见：点 / 区间 + 建议 + 元素引用 ══════════════
   * 一条意见 = { id, t0, t1, tag, note, fix, el }
   *   t1 === t0  → 时间点；t1 > t0 → 时间区间（时间轴上画半透明条）
   *   el         → 元素拾取器抓到的那个元素（种类/外观/画布坐标/所属场景）
   * 落盘：POST tools/review_server.py?action=notes → review/审片意见.json
   * 目的很直接：**给 Agent 改片用**。JSON 里有时间、元素坐标、期望，
   * 打开就能照着改，不需要人再口头描述一遍。
   */
  var NOTES = [];
  var NOTE_TAGS = ["画面", "文字", "配色", "节奏", "特效", "转场", "其他"];
  var rangeAnchor = null;          /* 区间标记的起点 */

  function noteId() {
    return "n" + Date.now().toString(36).slice(-5) +
      Math.floor(Math.random() * 1296).toString(36);
  }
  function saveNotes() {
    try { localStorage.setItem("rv-notes", JSON.stringify(NOTES)); } catch (e) {}
    api("../tools/review_server.py?action=notes", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: NOTES })
    }).then(function (r) {
      var f = $("mk-file");
      if (f) f.textContent = saveMsg(r, r.file,
        "（已存 " + (r.n == null ? NOTES.length : r.n) + " 条）");
      if (r.ok) { paintMarks(); buildMarkBars(); }
    });
  }
  function loadNotes() {
    return api("../tools/review_server.py?action=notes").then(function (r) {
      var f = $("mk-file");
      if (r.ok) {
        NOTES = r.notes || [];
        if (f) f.textContent = r.file + "（" + NOTES.length + " 条）";
      } else if (f) {
        f.textContent = "意见文件读不到，改用浏览器本地存档";
      }
      try {
        var ls = JSON.parse(localStorage.getItem("rv-notes") || "[]");
        if (!NOTES.length && ls.length) NOTES = ls;
      } catch (e) {}
      paintMarks();
      buildMarkBars();
    });
  }
  function addNote(t0, t1, note, fix, el, tag) {
    NOTES.push({ id: noteId(), t0: +t0.toFixed(3), t1: +t1.toFixed(3),
                 tag: tag || "画面", note: note || "", fix: fix || "",
                 el: el || null, at: Date.now() });
    /* 乐观重绘：先把条目画出来再去存 —— 否则保存一失败，界面就"丢"了这条 */
    paintMarks();
    buildMarkBars();
    saveNotes();
  }

  /* 时间轴上的标记：三角（点）+ 半透明条（区间） */
  function buildMarkBars() {
    var hb = "", hr = "";
    for (var i = 0; i < NOTES.length; i++) {
      var n = NOTES[i], a = posOf(n.t0), b = posOf(n.t1);
      var col = n.el ? "#5ee7ff" : "#ff4d8d";
      if (a < -2 || a > 102) continue;
      if (n.t1 > n.t0) {
        hr += '<i data-id="' + esc(n.id) + '" style="left:' + a + '%;width:' +
          Math.max(0.25, b - a) + '%;background:' + col + '"></i>';
      } else {
        hb += '<i class="hit" data-id="' + esc(n.id) + '" style="left:' + a + '%;' +
          'border-top-color:' + col + '" title="' +
          esc((n.tag || "") + " " + fmt(n.t0) + " " + (n.note || "")) + '"></i>';
      }
    }
    $("rv-bar-marks").innerHTML = hb;
    $("rv-bar-ranges").innerHTML = hr;
  }

  function paintMarks() {
    var box = $("mk-list");
    if (!box) return;
    if (!NOTES.length) {
      box.innerHTML = '<div class="rv-note" style="padding:10px">' +
        "还没有意见。在「元素」页选中一个元素写建议，或按 M 打时间点标记。</div>";
      return;
    }
    box.innerHTML = NOTES.slice().sort(function (a, b) { return a.t0 - b.t0; })
      .map(function (n) {
        /* 意见文本全部走 esc():意见文件会被 Agent 写回,tag/note/fix/元素名
           都是自由文本,直接拼 innerHTML 就是一条跨进程注入通道。 */
        var dur = n.t1 > n.t0 ? " ▭ " + (n.t1 - n.t0).toFixed(2) + "s" : "";
        var el = n.el ? (' <span class="z">⌖ ' + esc(n.el.label) + "</span>") : "";
        return '<div class="rv-item" data-id="' + esc(n.id) + '">' +
          '<span class="rt">' + fmt(n.t0) + dur + "</span>" +
          '<span class="rn">[' + esc(n.tag || "画面") + "] " +
          esc(n.note || "（无描述）") +
          (n.fix ? '<br><span style="color:#5fe08a">→ ' + esc(n.fix) + "</span>" : "") +
          el + "</span>" +
          '<span class="rz">✕</span></div>';
      }).join("");
  }

  function notesMarkdown() {
    var L = ["# 审片意见 · world.execute(me);", "",
             "由审片台导出。每条：时间（秒）+ 分类 + 现状 + 要改成什么 + 元素坐标。",
             "画面 = `SEEK(t)` 的直接输出，与成片同源（同源校验见 tools/audit_cache.py）。",
             ""];
    NOTES.slice().sort(function (a, b) { return a.t0 - b.t0; }).forEach(function (n, i) {
      L.push("## " + (i + 1) + ". [" + (n.tag || "画面") + "] " +
        fmt(n.t0) + (n.t1 > n.t0 ? " – " + fmt(n.t1) +
          "（" + (n.t1 - n.t0).toFixed(2) + "s）" : ""));
      if (n.el) {
        L.push("- 元素：" + n.el.label + "｜" + n.el.kind +
          "｜颜色 " + (n.el.color || "—") +
          "｜画布坐标 x=" + Math.round(n.el.x) + " y=" + Math.round(n.el.y) +
          " w=" + Math.round(n.el.w) + " h=" + Math.round(n.el.h) +
          "｜场景 " + (n.el.scene || "—"));
      }
      if (n.note) L.push("- 现状：" + n.note);
      if (n.fix) L.push("- **要改成：" + n.fix + "**");
      L.push("");
    });
    return L.join("\n");
  }

  /* ══════════════ 配置：实时落盘（审片台配置.json） ══════════════
   * 之前所有设置只活在本页内存里，刷新一次就要重调一遍（音量、变速、帧率锁、
   * 加速档位、字幕外观…）。现在任何一项变动都会去抖 400ms 后 POST 给
   * tools/review_server.py 写到工程根的 审片台配置.json，下次开浏览器自动套回。
   * 刻意不存：播放位置、轨道缩放窗口、标记、意见、字幕轨内容
   *          （它们各有自己的存档，混在一起会让"清空意见"顺手把设置也清了）。 */
  var CFG_T = 0, CFG_FILE = "—";
  function cfgCollect() {
    var g = function (id) { var e = $(id); return e ? e.value : undefined; };
    var o = {
      vol: parseFloat(g("vol")), audioOn: S.audioOn, loop: S.loop,
      speed: S.speed, fps: S.fps, scale: S.scale,
      pf: { mode: g("pf-mode"), drag: parseInt(g("pf-drag"), 10) },
      sub: {
        on: SUB.on, file: SUB.cur, autoSave: SUB.autoSave, font: SUB.st.font,
        size: SUB.st.size, color: SUB.st.color, stroke: SUB.st.stroke,
        strokeColor: SUB.st.strokeColor, bg: SUB.st.bg, bga: SUB.st.bga,
        pad: SUB.st.pad, bottom: SUB.st.bottom, align: SUB.st.align,
        lh: SUB.st.lh, maxw: SUB.st.maxw
      },
      cmp: { mode: S.diffMode, ref: S.refName || "" }
    };
    if (!isNaN(o.vol)) o.vol = o.vol / 100;      /* 滑杆 0-100，存 0-1 */
    return o;
  }
  function cfgApply(c) {
    if (!c) return;
    try {
      if (c.vol != null) { $("vol").value = Math.round(c.vol * 100); if (au) au.volume = c.vol; }
      if (c.audioOn != null) S.audioOn = !!c.audioOn;
      if (c.loop != null) { S.loop = !!c.loop; $("btn-loop").classList.toggle("rv-on", S.loop); }
      if (c.speed) { S.speed = c.speed; $("sel-speed").value = String(c.speed); }
      if (c.fps) setFps(c.fps);   /* 输出帧率锁（60/30/120/custom）*/
      if (c.scale) { S.scale = c.scale; if ($("sel-scale")) $("sel-scale").value = c.scale; }
      if (c.pf) {
        if (c.pf.mode && $("pf-mode")) $("pf-mode").value = c.pf.mode;
        if (c.pf.drag) PERF.dragAdec = c.pf.drag;
        if ($("pf-drag")) $("pf-drag").value = String(c.pf.drag || 2);
        pfModeFromSel(c.pf.mode);
      }
      if (c.sub) {
        var st = c.sub;
        if (st.on != null) SUB.on = !!st.on;
        if (st.file) SUB.lastFile = st.file;
        if (st.autoSave != null) SUB.autoSave = !!st.autoSave;
        ["font", "size", "color", "stroke", "strokeColor", "bg", "bga",
         "pad", "bottom", "align", "lh", "maxw"].forEach(function (k) {
          if (st[k] == null) return;
          /* 行距存的是比例(1.35),滑块是百分比(100..220) —— 直接写 e.value
             会被 range 钳到 100,用户一动滑块就跳变。 */
          var pct = (k === "lh" && st[k] <= 3) ? st[k] * 100 : st[k];
          SUB.st[k] = (k === "lh") ? pct / 100 : st[k];
          /* id 全小写:配置键是 camelCase(strokeColor),控件 id 是全小写
             (sb-strokecolor)。getElementById 大小写敏感,写成 strokeColor
             会查不到 → 每次开页都报"页面缺控件"。 */
          var e = $("sb-" + k.toLowerCase());
          if (e) e.value = pct;
        });
      }
      if (c.cmp) {
        if (c.cmp.mode) { S.diffMode = c.cmp.mode; }
        if (c.cmp.ref) S.refName = c.cmp.ref;
      }
      log("⚙ 已载入审片台配置" + (CFG_FILE === "—" ? "" : "（" + CFG_FILE + "）"));
      paintAudio(); paintSubBar(); paintSubs();
      $("sb-toggle").textContent = SUB.on ? "关闭字幕" : "开启字幕";
      $("sb-toggle").classList.toggle("rv-on", SUB.on);
    /* ⚠️ 这里曾经挂过一个"只刷新按钮文案"的 sb-toggle 包装器，它会把下面 init() 里真正的开关 handler 覆盖掉 ——
     * 因为 cfgApply() 是在 init() 之后由 cfgLoad() 触发的，
     * 于是页面一加载配置，"关闭字幕"就变成了死按钮（点了不关、
     * 文案也不变）。同一个 onXXX 只能有一处赋值。 */
    } catch (e) {
      /* 这里绝不能静默：曾经因为 setScale() 不存在而抛错，
         结果音量/帧率套上了、字幕外观没套上，现象极难定位。 */
      log("⚠ 配置套用失败：" + e);
    }
  }
  function pfModeFromSel(v) {
    if (!v) return;
    PERF.auto = v === "auto";
    if (v === "l3") { PERF.playAdec = 3; PERF.playReuse = 2; }
    if (v === "l2") { PERF.playAdec = 2; PERF.playReuse = 2; }
    if (v === "reuse") { PERF.playAdec = 1; PERF.playReuse = 2; }
    if (v === "full") { PERF.playAdec = 1; PERF.playReuse = 0; }
  }
  function cfgSave(now) {
    clearTimeout(CFG_T);
    var go = function () {
      api("review_server.py?action=config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfgCollect())
      }).then(function (r) {
        if (r && r.ok) {
          CFG_FILE = (r.file || "").split(/[\\/]/).pop();
          var f = $("cf-file");
          if (f) f.textContent = "配置文件：" + CFG_FILE + "（已保存 " +
            new Date().toLocaleTimeString("zh-CN") + "）";
          flashCfg();
        } else if (r && r.queued) {
          var f2 = $("cf-file");
          if (f2) f2.textContent = "⏳ 配置已排队（" + NET.queue.length +
            " 项，服务恢复后自动写入）";
        }
      });
    };
    if (now) go(); else CFG_T = setTimeout(go, 400);
  }
  function flashCfg() {
    var c = $("chip-cfg");
    if (!c) return;
    c.textContent = "⚙ 已保存";
    c.classList.add("rv-on");
    setTimeout(function () { c.classList.remove("rv-on"); }, 1200);
  }
  function cfgTouch() { cfgSave(false); }
  function cfgLoad() {
    api("review_server.py?action=config").then(function (r) {
      if (r && r.ok) {
        CFG_FILE = (r.file || "").split(/[\\/]/).pop();
        var f = $("cf-file");
        if (f) f.textContent = "配置文件：" + CFG_FILE;
        cfgApply(r.data);
      }
    });
  }

  /* ══════════════ 性能：为什么是"少画"而不是"上 GPU" ══════════════
   * CDP 采样实测（全片最重的一帧 t=193，1920×1080）：
   *   · 这一帧发 18,351 次 fillText，其中 girl 的 bold 11.5px 占 13,734 次
   *   · M11 段 37.6~47.6 ms/帧，67.5% 的时间在 fillText 上
   *   · 字形图集（drawImage 贴预渲染字形）反而慢一倍：17.4ms vs 8.4ms/3000 字
   *   · 把 E.SS 从 1 降到 0.5 只快 18% —— canvas2d 已经是 GPU 光栅，
   *     瓶颈在 **CPU 侧文本整形调用次数**，跟像素量基本无关
   * 所以提速只有三条路，缺一不可：
   *   ① 少画：图层时间复用（E.AREUSE）+ 空间抽稀（E.ADEC），只在播放/拖动时开
   *   ② 少渲染：跟不上就跳帧（时间照走，画面按 2 帧一跳）
   *   ③ 别重复：暂停/导出/成片一律全量 —— 审片看的那一帧永远是完整的
   * 实测（M11，90 帧连播）：全量 47.6ms → 复用2帧 14.5ms → 1/3抽稀+复用 9.2ms。
   */
  var PERF = {
    auto: true,
    playAdec: 3, playReuse: 2, dragAdec: 2,
    tuneAdec: 1, tuneReuse: 0,
    avg: 0, drawn: 0, skip: 0, worst: 0
  };
  /* 帧率锁：逐帧步进 / 帧号 / 跳帧兜底都以它为准（片子是时间的函数，
   * 任意帧率都能画；30fps 步进更大更稳，120fps 逐帧更细但更吃 CPU） */
  function setFps(v) {
    v = Math.max(1, Math.min(240, Math.round(v || 60)));
    S.fps = v;
    ["sel-fps", "pf-fps"].forEach(function (id) {
      var sel = $(id);
      if (sel && sel.value !== "custom" && parseInt(sel.value, 10) !== v) {
        sel.value = String([30, 60, 120].indexOf(v) >= 0 ? v : "custom");
      }
    });
    var inp = $("in-fps");
    if (inp && document.activeElement !== inp) inp.value = v;
    log("帧率锁定 " + v + " fps（±1 帧 = " + (1000 / v).toFixed(2) + " ms）");
    paint();
  }

  function applyLOD(kind) {
    var En = window.ENG;
    if (!En) return;
    var a = 1, r = 0;
    if (kind === "play") {
      a = PERF.auto ? PERF.tuneAdec : PERF.playAdec;
      r = (PERF.auto ? PERF.tuneReuse : PERF.playReuse) / 60;
    } else if (kind === "drag") {
      a = PERF.dragAdec;
    }
    En.ADEC = a; En.AREUSE = r;
    S.lod = a > 1 || r > 0
      ? (a > 1 ? "1/" + a : "") + (r > 0 ? "缓存" + Math.round(r * 60) + "f" : "")
      : "全量";
  }
  function autoTune(cost) {
    PERF.avg = PERF.avg ? PERF.avg * 0.82 + cost * 0.18 : cost;
    if (cost > PERF.worst) PERF.worst = cost;
    if (!PERF.auto) return;
    var budget = 1000 / S.fps, a = PERF.tuneAdec, r = PERF.tuneReuse;
    if (PERF.avg > budget * 1.25) {
      if (r < 4) r += 1; else if (a < 3) { a += 1; r = 2; }
    } else if (PERF.avg < budget * 0.55) {
      if (a > 1) { a -= 1; r = 2; } else if (r > 0) r -= 1;
    }
    PERF.tuneAdec = a; PERF.tuneReuse = r;
  }
  function perfReset() { PERF.avg = 0; PERF.drawn = 0; PERF.skip = 0; PERF.worst = 0; }

  /* ══════════════ 音频：与影片时间轴同步 ══════════════
   * 影片是时间的纯函数，音频是另一条时间轴；这里让 audio.currentTime 一直
   * 咬住 S.t：
   *   · 播放时按变速设 playbackRate，漂移 >0.25s 就重新对齐（浏览器时钟漂、
   *     后台标签页节流都可能造成漂移）
   *   · 暂停/拖动/逐帧时不发声，但**把播放头挪到对应位置** —— 这样"从
   *     174.3s 起播"是从那一秒的声音开始，而不是从上一处
   *   · 循环时音频一起 loop；音频走完（先于画面）就停下画面
   * 浏览器要求用户手势才能出声：所有入口都是点击/按键，天然满足。 */
  var au = $("au");
  var AU_NAME = "";        /* 音源文件名（服务端 meta 探测结果，仅用于日志/报错） */
  var ADRIFT = 0.25;

  function audioFollow(force) {
    if (!au) return;
    if (!S.audioOn) {
      if (!au.paused) au.pause();
      return;
    }
    au.loop = S.loop;
    var want = Math.max(0, Math.min(audur() - 0.05, S.t));
    if (S.playing) {
      if (au.paused) {
        if (Math.abs(au.currentTime - want) > 0.08) au.currentTime = want;
        var pr = au.play();
        if (pr && pr.catch) pr.catch(function () {
          err("音频被浏览器拦下（点一下页面再按播放）");
        });
      } else if (force || Math.abs(au.currentTime - S.t) > ADRIFT) {
        au.currentTime = want;
      }
      if (Math.abs(au.playbackRate - S.speed) > 0.01) au.playbackRate = S.speed;
      S.drift = au.currentTime - S.t;
    } else {
      if (!au.paused) au.pause();
      /* 暂停时也把头挪到位（拖动过程不挪，up() 再统一对齐） */
      if (force && Math.abs(au.currentTime - want) > 0.04) au.currentTime = want;
      S.drift = 0;
    }
  }
  function audur() {
    return isFinite(au.duration) && au.duration > 1 ? au.duration : DUR;
  }
  function paintAudio() {
    var b = $("btn-audio");
    if (!b) return;
    b.classList.toggle("rv-on", S.audioOn);
    b.title = S.audioOn
      ? "原曲同步播放：开（当前偏差 " + (S.drift >= 0 ? "+" : "") + S.drift.toFixed(2) + "s）"
      : "原曲同步播放：关 (A)";
  }

  /* ─────────────── 缩放：把 1920×1080 的舞台装进视口 ─────────────── */
  function fit() {
    var vp = $("rv-viewport"), sc = $("rv-scaler");
    var k = S.scale === "fit"
      ? Math.min(vp.clientWidth / 1920, vp.clientHeight / 1080)
      : parseFloat(S.scale);
    sc.style.transform = "scale(" + k + ")";
  }

  /* ══════════════ 轨道缩放：VIEW 视图窗口 ══════════════
   * 动机：全片 211.9s 挤在一条轨上，每句歌词只有几像素宽，看不出是哪句。
   * Alt+滚轮以鼠标处为锚缩放；两个轨道 + 播放头 + 悬停 + 点击 + 拖动**共享**
   * 同一个 VIEW，所以怎么缩放都不会错位。
   */
  var VIEW = { t0: 0, t1: 211.913 };
  var ZMIN = 0.3;                       /* 最小跨度 0.3 秒 */
  function viewSpan() { return Math.max(0.001, VIEW.t1 - VIEW.t0); }
  function posOf(t) { return (t - VIEW.t0) / viewSpan() * 100; }
  function timeAt(x01) { return VIEW.t0 + x01 * viewSpan(); }
  function viewFit() {
    VIEW.t0 = 0; VIEW.t1 = DUR;
    log("轨道：全片 0 – " + DUR.toFixed(2) + "s");
    viewRepaint();
  }
  /* 以 anchor 秒为锚缩放：k<1 放大、k>1 缩小 */
  function viewZoom(k, anchorT) {
    var sp = viewSpan(), a = anchorT == null ? (VIEW.t0 + VIEW.t1) / 2 : anchorT;
    var nsp = Math.max(ZMIN, Math.min(DUR, sp * k));
    if (Math.abs(nsp - sp) < 1e-6) return;
    var f = (a - VIEW.t0) / sp;          /* 锚点在窗口里的相对位置 */
    VIEW.t0 = a - nsp * f;
    VIEW.t1 = VIEW.t0 + nsp;
    if (VIEW.t0 < 0) { VIEW.t0 = 0; VIEW.t1 = nsp; }
    if (VIEW.t1 > DUR) { VIEW.t1 = DUR; VIEW.t0 = DUR - nsp; }
    viewRepaint();
  }
  /* ────────────── 平移滑条 ──────────────
   * 缩放只解决"看得清"，还要能"走得动"。滑条 = 整部片，滑块 = 当前视图窗口。
   * 拖动时按抓取点平移（不是按速度积分），松手后按整片边界夹紧；
   * 滑块有最小宽度，极限放大时依然抓得住，此时可平移范围自动收窄。 */
  var PAN_MIN = 20;                     /* 滑块最小像素宽 */
  function panBox() {
    var el = $("rv-pan");
    return el ? el.getBoundingClientRect() : null;
  }
  /* ⚠️ 这里**不要**加"拖动中跳过刷新"的守卫：thumb 的唯一写入来源就是
     视图（panToCenter → viewRepaint → paintPan）。一旦在拖动期间跳过刷新，
     就会出现"拖动滑条不动、时间轴却在动、松手才刷新"——
     （上一轮加过 panBusy 守卫，正是这个 bug）。播放中能拖动靠的是
     paint() 里不再每帧调 paintPan，thumb 不会被别处抢。 */
  function paintPan() {
    var bar = $("rv-pan"), th = $("rv-pan-thumb");
    if (!bar || !th) return;
    var r = panBox();
    if (!r || r.width < 10) return;
    var sp = viewSpan(), W = r.width;
    var full = sp >= DUR - 1e-3;
    var w = Math.max(PAN_MIN, sp / DUR * W);
    if (full) w = W;
    var center = (VIEW.t0 + VIEW.t1) / 2;
    var left = Math.max(0, Math.min(W - w, center / DUR * W - w / 2));
    th.style.width = w + "px";
    th.style.left = left + "px";
    bar.classList.toggle("full", full);
    bar.title = full
      ? "全片视图（Alt+滚轮放大后可用它左右移动）"
      : (fmt(VIEW.t0) + " – " + fmt(VIEW.t1) + "（跨度 " + sp.toFixed(2) +
         "s）· 拖动滑块移动视野");
  }
  /* 把视图中心移到 ct（按整片边界夹紧） */
  function panToCenter(ct) {
    var sp = viewSpan();
    var t0 = Math.max(0, Math.min(DUR - sp, ct - sp / 2));
    VIEW.t0 = t0;
    VIEW.t1 = t0 + sp;
    viewRepaint();
  }

  function viewRepaint() {
    buildBar(); buildMarkBars(); paintSubBar(); paintPan();
    var full = viewSpan() >= DUR - 1e-3;
    $("rv-zoom-v").textContent = full ? "全片"
      : (fmt(VIEW.t0) + " – " + fmt(VIEW.t1));
    $("rv-zoom-v").title = full ? "当前：全片"
      : ("当前窗口 " + fmt(VIEW.t0) + " – " + fmt(VIEW.t1) +
         "（" + viewSpan().toFixed(2) + "s，Alt+滚轮缩放，双击复位）");
    paint();
  }
  function viewAt(ev) {
    var r = $("rv-bar").getBoundingClientRect();
    var x = (ev.clientX - r.left) / r.width;
    return timeAt(Math.max(0, Math.min(1, x)));
  }
  /* Alt+滚轮缩放（两个轨道都支持） */
  function bindZoom(el) {
    el.addEventListener("wheel", function (ev) {
      if (!ev.altKey) return;            /* 普通滚轮不劫持 */
      ev.preventDefault();
      var r = el.getBoundingClientRect();
      var x = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width));
      var t = timeAt(x);
      var r2 = $("rv-bar").getBoundingClientRect();
      if (el.id === "rv-subbar") {       /* 字幕轴上：用主时间条的位置换算锚点 */
        var xs = Math.max(0, Math.min(1, (ev.clientX - r2.left) / r2.width));
        t = timeAt(xs);
      }
      viewZoom(ev.deltaY < 0 ? 1 / 1.22 : 1.22, t);
    }, { passive: false });
  }

  /* ─────────────── 渲染一帧 ─────────────── */
  function draw(t) {
    var t0 = performance.now();
    window.SEEK(t);
    S.ms = performance.now() - t0;
    autoTune(S.ms);
    PERF.drawn++;
    S.t = Math.max(0, Math.min(DUR - 1e-4, t));
    paint();
  }

  /* 暂停/导出/成片一律全量 —— 审片看到的那一帧必须是完整的 */
  function drawFull(t) {
    var E = window.ENG, a = E.ADEC, r = E.AREUSE;
    E.ADEC = 1; E.AREUSE = 0;
    draw(t);
    E.ADEC = a; E.AREUSE = r;
  }

  function fmt(t) {
    var m = Math.floor(t / 60), s = t - m * 60;
    return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s.toFixed(2);
  }

  function paint() {
    $("t-cur").textContent = fmt(S.t);
    $("t-frame").textContent = "  f" + Math.round(S.t * S.fps) + " / " +
      Math.round(DUR * S.fps) + "  @" + S.fps + "fps";
    var p = S.t / DUR;
    $("rv-bar-fill").style.left = "0%";
    $("rv-bar-fill").style.width = Math.max(0, Math.min(100, posOf(S.t))) + "%";
    var ph = Math.max(-1, Math.min(101, posOf(S.t)));
    $("rv-bar-head").style.left = ph + "%";
    $("rv-bar-head").style.opacity = (ph < 0 || ph > 100) ? "0" : "1";
    $("chip-perf").textContent = "🔒" + S.fps + " · " + PERF.avg.toFixed(1) +
      "ms · " + S.lod;
    var mv = curMove();
    $("chip-sec").textContent = mv ? (mv.id + " " + mv.name + " · " + mv.note) : "—";
    $("chip-lyric").textContent = curLyric() ? curLyric().s : "（无歌词）";
    paintAudio();
    highlight();
    /* 全屏浮层条（同一份读数，不另起状态） */
    $("fs-time").textContent = fmt(S.t) + " / " + fmt(DUR) +
      "   f" + Math.round(S.t * S.fps) + "  @" + S.fps + "fps";
    $("fs-fill").style.width = Math.max(0, Math.min(100, posOf(S.t))) + "%";
    $("fs-head").style.left = Math.max(0, Math.min(100, posOf(S.t))) + "%";
    $("fs-play").textContent = S.playing ? "⏸" : "▶";
    if ($("tab-perf").classList.contains("rv-on")) paintPerf();
    paintSubs();
    if ($("tab-sub").classList.contains("rv-on")) { subMarkCur(); subFileInfo(); }
  }

  function curMove() {
    var ms = (window.MV && window.MV.moves) || [];
    for (var i = 0; i < ms.length; i++) if (S.t >= ms[i].t0 && S.t < ms[i].t1) return ms[i];
    return ms[ms.length - 1] || null;
  }
  function curLyric() {
    var ls = (window.FILM && window.FILM.lyrics) || [];
    for (var i = ls.length - 1; i >= 0; i--) if (S.t >= ls[i].t) return ls[i];
    return null;
  }

  /* ─────────────── 播放循环 ─────────────── */
  function tick(now) {
    if (!S.playing) return;
    var dt = (now - S.last) / 1000;
    S.last = now;
    var budget = 1000 / S.fps;
    var nt = S.t + dt * S.speed;
    if (nt >= DUR) {
      if (S.loop) nt -= DUR;
      else { nt = DUR - 1e-4; setPlay(false); }
    }
    /* ② 少渲染：上一帧超预算太多就一次跳两帧（时间照走，画面 30fps），
     *    免得"越播越慢"。自适应档位已经把均摊成本压到预算内，这里兜底。 */
    if (S.ms > budget * 1.8 && dt * 1000 < budget * 4) {
      nt = S.t + (2 / S.fps) * S.speed;
      PERF.skip++;
    }
    applyLOD("play");
    draw(nt);
    audioFollow(false);
    S.raf = requestAnimationFrame(tick);
  }
  function setPlay(on) {
    S.playing = on;
    $("btn-play").textContent = on ? "⏸" : "▶";
    if (on) {
      applyLOD("play");              /* 进播放：开图层缓存/抽稀 */
      S.last = performance.now();
      S.raf = requestAnimationFrame(tick);
    } else {
      cancelAnimationFrame(S.raf);
      applyLOD("full");              /* 暂停：立刻回到全量并重画这一帧 */
      draw(S.t);
    }
    audioFollow(true);
  }

  /* ─────────────── 时间条 ─────────────── */
  function barT(ev) {
    var r = $("rv-bar").getBoundingClientRect();
    var x = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    return timeAt(Math.max(0, Math.min(1, x / r.width)));
  }
  function buildBar() {
    var ms = (window.MV && window.MV.moves) || [];
    var h = [], row = 0, lastX = -99;
    for (var i = 0; i < ms.length; i++) {
      var x = posOf(ms[i].t0);
      h.push('<i class="' + (i ? "" : "hot") + '" style="left:' + x + '%"></i>');
      /* 段名只在够宽的时候写，且相邻的交替上下错开一行，否则全是压在一起的字 */
      var wpc = (ms[i].t1 - ms[i].t0) / viewSpan() * 100;
      if (wpc >= 4.2) {
        row = (x - lastX < 7) ? 1 - row : 0;
        lastX = x;
        h.push('<b class="' + (row ? "rv-b2" : "") + '" style="left:' + x + '%;max-width:' +
          (wpc - 0.4) + '%">' + (i + 1) + " " + ms[i].name + "</b>");
      }
    }
    $("rv-bar-sections").innerHTML = h.join("");
    var ls = (window.FILM && window.FILM.lyrics) || [], g = [], row2 = 0;
    for (var k = 0; k < ls.length; k++) {
      var lx = posOf(ls[k].t);
      if (lx < -2 || lx > 102) continue;               /* 视野外不画 */
      var lw = Math.max(0.15, ((ls[k].e || ls[k].t + 1.6) - ls[k].t) / viewSpan() * 100);
      g.push('<i style="left:' + lx + '%;width:' + lw + '%"></i>');
      /* 视野够宽就把歌词原文写出来（之前只有 1px 的刻度线，看不出是哪句） */
      if (lw >= 3.2) {
        g.push('<b class="' + (row2 ? "rv-b2" : "") + '" style="left:' + lx + "%;max-width:" +
          (lw - 0.3) + '%">' + (ls[k].s || "") + "</b>");
      }
      row2 = row2 ? 0 : 1;
    }
    $("rv-bar-lyrics").innerHTML = g.join("");
  }
  /* 进度条：**悬停只出预览，点击才跳转**，拖动要过 4px 阈值才算拖。
   * （之前一按下就 seek，鼠标轻抖也会跳；现在纯点击=精确跳，拖=连续刷） */
    var wasPlaying = false, dragging = false, armed = false, downX = 0, downT = 0;
  function down(ev) {
    armed = true; dragging = false; downX = ev.clientX;
    downT = barT(ev); wasPlaying = S.playing;
    if (S.playing) setPlay(false);
    ev.preventDefault();
  }
  function move(ev) {
    if (!armed) return;
    if (!dragging) {
      if (Math.abs(ev.clientX - downX) < 4) return;   /* 还没过阈值：不算拖 */
      dragging = true;
      applyLOD("drag");                 /* 拖动中：抽稀换手感（不抽时间缓存） */
      hideHover();
    }
    draw(barT(ev));
  }
  function up(ev) {
    if (!armed) return;
    var moved = dragging;
    armed = false; dragging = false;
    if (!moved) {                                     /* 纯点击 → 跳过去 */
      applyLOD("full");
      seek(downT);
      audioFollow(true);
      if (wasPlaying) setPlay(true);
      return;
    }
    applyLOD("full");
    drawFull(S.t);                    /* 松手：立刻出一帧全画质 */
    audioFollow(true);
    if (wasPlaying) setPlay(true);
  }

  /* 时间条上的悬停缩略图：把当前帧缩到 320×180 */
  var hoverT = -1;
  function hover(ev) {
    if (dragging || S.playing) { hideHover(); return; }
    var t = barT(ev);
    if (Math.abs(t - hoverT) < 1 / S.fps) { moveHover(ev); return; }
    hoverT = t;
    /* 只算画面、绝不碰 UI：之前这里走 drawFull()（它会 paint），于是播放头和
     * 时间读数会闪到鼠标位置再跳回来 —— 看着就是"划到哪进度条就跳到哪"。
     * 现在：SEEK(t) → 缩略图 → SEEK 回当前时间，全程不动 paint()。 */
    var E = window.ENG, a = E.ADEC, r = E.AREUSE;
    E.ADEC = 1; E.AREUSE = 0;
    window.SEEK(t);
    composite($("rv-hover-cv"), 320, 180);
    window.SEEK(S.t);
    E.ADEC = a; E.AREUSE = r;
    $("rv-hover-t").textContent = fmt(t) + "  f" + Math.round(t * S.fps);
    moveHover(ev);
  }
  /* 定位：fixed 坐标就是视口坐标，所以直接用 clientX/Y；
   * 默认放在光标**上方**（缩略图底边离光标 12px），上方不够高才放下方，
   * 四周都夹在窗口内 —— 无论鼠标在时间条的哪个位置都不会被裁/被盖。 */
  var HW = 326, HH = 210;
  function moveHover(ev) {
    var box = $("rv-hover");
    var vw = window.innerWidth, vh = window.innerHeight;
    var x = ev.clientX - HW / 2;
    if (x < 8) x = 8;
    if (x + HW > vw - 8) x = vw - 8 - HW;
    var y = ev.clientY - HH - 12;
    if (y < 8) y = ev.clientY + 20;                 /* 上方不够：放下方 */
    if (y + HH > vh - 8) y = vh - 8 - HH;         /* 下方也不够：贴住下沿 */
    if (y < 8) y = 8;
    box.style.left = x + "px"; box.style.top = y + "px"; box.hidden = false;
  }
  function hideHover() { $("rv-hover").hidden = true; hoverT = -1; }

  /* 手动合成：所有可见场景画布 + #fx → 一张 canvas（缩略图/导出用） */
  function composite(dst, w, h) {
    var g = dst.getContext("2d");
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, dst.width, dst.height);
    var list = [].slice.call(document.querySelectorAll("#scenes .scene"));
    list.sort(function (a, b) {
      var za = parseInt(getComputedStyle(a).zIndex || 0, 10) || 0;
      var zb = parseInt(getComputedStyle(b).zIndex || 0, 10) || 0;
      return za - zb;
    });
    g.globalAlpha = 1;
    for (var i = 0; i < list.length; i++) {
      var sc = list[i], st = getComputedStyle(sc);
      if (st.display === "none" || st.visibility === "hidden") continue;
      var op = parseFloat(st.opacity);
      if (!(op > 0.004)) continue;
      var c = sc.querySelector("canvas.cvs");
      if (!c) continue;
      g.globalAlpha = op;
      g.drawImage(c, 0, 0, w, h);
    }
    g.globalAlpha = 1;
    var fx = $("fx");
    if (fx) g.drawImage(fx, 0, 0, w, h);
    return dst;
  }

  /* ══════════════ 元素拾取器：这一帧到底画了什么 ══════════════
   * 办法：临时包装 CanvasRenderingContext2D 的绘图方法，把每次调用记成
   * "一条带包围盒的元素"。开启时重画一帧收集，收集完就恢复原方法 ——
   * 所以**平时播放零开销**。
   * 为什么需要：让用户能指着画面说"就这个"，Agent 也能拿到画布坐标去改代码。
   */
  var PICK = { items: [], sel: null, on: false };

  /* ── DevTools 式"在页面中选择一个元素以进行检查"（Ctrl+Shift+C）──
   * 开启后：鼠标在画面上移动 → 实时高亮光标下的元素 + 蓝色 tooltip 显示
   * 它的名字（与 DevTools 的行为一致）；点击即选中，模式保持开启，
   * 可以连续点多个元素；再按一次或 Esc 退出。 */
  var INSPECT = { on: false };
  function toggleInspect(on) {
    INSPECT.on = on == null ? !INSPECT.on : !!on;
    document.body.classList.toggle("rv-inspect", INSPECT.on);
    $("dk-inspect").classList.toggle("rv-on", INSPECT.on);
    $("pk-inspect").classList.toggle("rv-on", INSPECT.on);
    if (INSPECT.on) {
      if (!PICK.items.length) pickRun();
      log("⌖ 检查模式：点画面上的元素（Esc 退出）");
    } else {
      $("rv-inspect-tip").style.display = "none";
      log("⌖ 检查模式：关");
    }
  }
  function inspectAt(ev) {
    if (!INSPECT.on) return;
    var r = $("rv-scaler").getBoundingClientRect();
    var lx = (ev.clientX - r.left) / (r.width / 1920);
    var ly = (ev.clientY - r.top) / (r.height / 1080);
    var best = null, bestA = 1e9;
    PICK.items.forEach(function (e) {
      if (lx < e.x - 4 || lx > e.x + e.w + 4) return;
      if (ly < e.y - 4 || ly > e.y + e.h + 4) return;
      var a = e.w * e.h;                 /* 取**最小**的命中元素：DevTools 就是这个语义 */
      if (a < bestA) { bestA = a; best = e; }
    });
    drawPickBox(best);
    var tip = $("rv-inspect-tip");
    if (!best) { tip.style.display = "none"; return; }
    tip.style.display = "block";
    tip.style.left = Math.min(innerWidth - 260, ev.clientX + 14) + "px";
    tip.style.top = (ev.clientY + 16) + "px";
    tip.textContent = (best.label || best.kind) + "  ·  " + best.kind + "  ·  " +
      Math.round(best.w) + "×" + Math.round(best.h) + "  @ " + best.x + "," + best.y;
  }

  /* ══════════════ 元素拾取器：这一帧到底画了什么 ══════════════
   * 办法：临时包装 CanvasRenderingContext2D 的绘图方法，把每次调用记成
   * "一条带包围盒的元素"，抓完一帧立刻恢复 —— 平时播放零开销。
   *
   * 三个必须处理的现实问题（都是实测踩出来的）：
   *  ① 背景是整屏渐变，包围盒 16818×2769 —— 必须**裁到画面内**，
   *     裁完还占半个画面以上的判为"背景"，排到最后，否则列表第一条永远是它。
   *  ② `fillText` 也要记（不然一条文字都抓不到），但 18 000 次 measureText
   *     不慢，所以只在 on-demand 抓帧时做。
   *  ③ ASCII 女孩是一格一个字的 13 700 次 fillText —— 逐格入列会把列表冲垮，
   *     所以**单字按 (字符,颜色) 聚合**：≥20 格就并成一条"ASCII 网格"。
   */
  var PICK_CAP = 400;

  function pickCtx() {
    var P = CanvasRenderingContext2D.prototype;
    if (P.__pickOrig) return P.__pickOrig;
    var orig = {};
    ["fillText","strokeText","fillRect","strokeRect","drawImage","arc","ellipse",
     "fill","stroke","moveTo","lineTo","rect","bezierCurveTo","quadraticCurveTo"]
      .forEach(function (k) { orig[k] = P[k]; });
    var cur = null;

    function begin() { cur = { x0: 1e9, y0: 1e9, x1: -1e9, y1: -1e9, n: 0 }; }
    function grow(x, y) {
      if (!cur) begin();
      if (x < cur.x0) cur.x0 = x;
      if (x > cur.x1) cur.x1 = x;
      if (y < cur.y0) cur.y0 = y;
      if (y > cur.y1) cur.y1 = y;
      cur.n++;
    }
    function cssOf(c) {
      var v = c.fillStyle || c.strokeStyle || "";
      var nm = v && v.constructor ? v.constructor.name : "";
      if (nm === "CanvasGradient") return "渐变";
      if (nm === "CanvasPattern") return "图案";
      return String(v).slice(0, 40);
    }
    /* ⚠️ 场景 ctx 的 setTransform(SS,0,0,SS,0,0) 之后，fillText/fillRect 的
     * **参数仍然是 1920×1080 逻辑坐标**（变换只作用在光栅化时），而 #rv-scaler
     * 本身就是 1920×1080 再由 CSS 缩放。所以这里**不能**再除一次屏幕缩放 ——
     * 早期版本除了这一下，坐标全错（y=1502 / x=3596 这种越界值）。 */
    function toLogical(x, y) { return [x, y]; }
    function push(kind, label, style, x, y, w, h, n) {
      if (PICK.items.length >= PICK_CAP * 3) return;
      /* 裁到画面 */
      var x0 = Math.max(0, x), y0 = Math.max(0, y);
      var x1 = Math.min(1920, x + w), y1 = Math.min(1080, y + h);
      if (x1 - x0 < 2 || y1 - y0 < 2) return;               /* 碎屑 */
      var lx = toLogical(x0, y0)[0], ly = toLogical(x0, y0)[1];
      var lw = toLogical(x1, y0)[0] - lx, lh = toLogical(x0, y1)[1] - ly;
      PICK.items.push({
        kind: kind, label: label, color: String(style || ""),
        x: Math.round(lx), y: Math.round(ly),
        w: Math.round(lw), h: Math.round(lh), n: n || 1,
        bg: lw * lh > 1920 * 1080 * 0.45
      });
    }
    function flush(kind, label, style) {
      if (cur && cur.n && cur.x1 > cur.x0) {
        push(kind, label, style, cur.x0, cur.y0, cur.x1 - cur.x0, cur.y1 - cur.y0, cur.n);
      }
      cur = null;
    }
    function textBox(c, t, x, y) {
      var w = 0;
      try { w = c.measureText(String(t)).width; } catch (e) {}
      var fs = parseFloat(c.font) || 12;
      var al = c.textAlign === "center" ? .5 : (c.textAlign === "right" || c.textAlign === "end" ? 1 : 0);
      var bl = c.textBaseline === "middle" ? .5 :
               (c.textBaseline === "bottom" || c.textBaseline === "ideographic" ? 1 : 0);
      return [x - w * al, y - fs * bl, w, fs * 1.05];
    }

    P.fillText = function (t, x, y) {
      var b = textBox(this, t, x, y);
      var one = String(t).replace(/\s+/g, " ").trim();
      PICK.glyphs = PICK.glyphs || {};
      if (one.length === 1) {
        var k = one + "|" + cssOf(this);
        var g = PICK.glyphs[k] || (PICK.glyphs[k] = { n: 0, x0: b[0], y0: b[1],
                                                        x1: b[0] + b[2], y1: b[1] + b[3], c: k });
        g.n++; g.x1 = Math.max(g.x1, b[0] + b[2]); g.y1 = Math.max(g.y1, b[1] + b[3]);
      } else {
        push("text", one.slice(0, 26) || "文字", cssOf(this), b[0], b[1], b[2], b[3], 1);
      }
      return orig.fillText.call(this, t, x, y);
    };
    P.strokeText = function (t, x, y) {
      var b = textBox(this, t, x, y);
      push("text", "描边:" + String(t).slice(0, 22), cssOf(this), b[0], b[1], b[2], b[3], 1);
      return orig.strokeText.call(this, t, x, y);
    };
    P.fillRect = function (x, y, w, h) { push("方块", "实心方块", cssOf(this), x, y, w, h, 1); return orig.fillRect.call(this, x, y, w, h); };
    P.strokeRect = function (x, y, w, h) { push("方框", "描边方框", cssOf(this), x, y, w, h, 1); return orig.strokeRect.call(this, x, y, w, h); };
    P.drawImage = function (im, a, b2, c2, d2) {
      var w = (c2 === undefined ? im.width : c2), h = (d2 === undefined ? im.height : d2);
      push("图像", "贴图 " + w + "×" + h, "—", a, b2, w, h, 1);
      return orig.drawImage.apply(this, arguments);
    };
    P.arc = function (x, y, r) { grow(x - r, y - r); grow(x + r, y + r); return orig.arc.apply(this, arguments); };
    P.ellipse = function (x, y, rx, ry) { grow(x - rx, y - ry); grow(x + rx, y + ry); return orig.ellipse.apply(this, arguments); };
    P.rect = function (x, y, w, h) { grow(x, y); grow(x + w, y + h); return orig.rect.apply(this, arguments); };
    P.moveTo = function (x, y) { grow(x, y); return orig.moveTo.apply(this, arguments); };
    P.lineTo = function (x, y) { grow(x, y); return orig.lineTo.apply(this, arguments); };
    P.bezierCurveTo = function (a, b2, c2, d2, e2, f2) { grow(a, b2); grow(c2, d2); grow(e2, f2); return orig.bezierCurveTo.apply(this, arguments); };
    P.quadraticCurveTo = function (a, b2, c2, d2) { grow(a, b2); grow(c2, d2); return orig.quadraticCurveTo.apply(this, arguments); };
    P.fill = function () { flush("路径", "填充路径", cssOf(this)); return orig.fill.apply(this, arguments); };
    P.stroke = function () { flush("路径", "描边路径", cssOf(this)); return orig.stroke.apply(this, arguments); };
    P.__pickOrig = orig;
    return orig;
  }

  function pickRestore() {
    var P = CanvasRenderingContext2D.prototype;
    if (!P.__pickOrig) return;
    ["fillText","strokeText","fillRect","strokeRect","drawImage","arc","ellipse",
     "fill","stroke","moveTo","lineTo","rect","bezierCurveTo","quadraticCurveTo"]
      .forEach(function (k) { P[k] = P.__pickOrig[k]; });
    P.__pickOrig = null;
  }

  function pickRun() {
    PICK.items = []; PICK.glyphs = {}; PICK.sel = null;
    pickCtx();
    try { window.SEEK(S.t); } catch (e) {}
    pickRestore();
    /* 单字聚合：同一 (字符,颜色) ≥20 格 ⇒ 并成一条 ASCII 网格 */
    var gl = PICK.glyphs;
    for (var k in gl) {
      var g = gl[k];
      if (g.n >= 20) {
        PICK.items.push({ kind: "grid", label: "ASCII 网格 '" + k.slice(0, 1) +
          "' ×" + g.n, color: k.split("|")[1] || "",
          x: Math.round(g.x0), y: Math.round(g.y0),
          w: Math.round(g.x1 - g.x0), h: Math.round(g.y1 - g.y0), n: g.n,
          bg: (g.x1 - g.x0) * (g.y1 - g.y0) > 1920 * 1080 * 0.45 });
      }
    }
    PICK.glyphs = {};
    /* 零散单字已被上面的聚合吸收，丢弃 */
    PICK.items = PICK.items.filter(function (e) { return e.kind !== "grid" || e.n >= 20; });
    /* 再加一条"全部 ASCII 网格"的总项 —— 用户要指的整体（比如"她"）多半是它，
     * 而不是某一笔画的并集框。 */
    var gs = PICK.items.filter(function (e) { return e.kind === "grid"; });
    if (gs.length > 1) {
      var ux0 = 1e9, uy0 = 1e9, ux1 = -1e9, uy1 = -1e9, un = 0;
      gs.forEach(function (e) {
        ux0 = Math.min(ux0, e.x); uy0 = Math.min(uy0, e.y);
        ux1 = Math.max(ux1, e.x + e.w); uy1 = Math.max(uy1, e.y + e.h); un += e.n;
      });
      PICK.items.unshift({ kind: "grid", label: "ASCII 网格 全部（" + un + " 字）",
        color: "多色", x: ux0, y: uy0, w: ux1 - ux0, h: uy1 - uy0, n: un,
        bg: (ux1 - ux0) * (uy1 - uy0) > 1920 * 1080 * 0.45, all: true });
    }
    /* 排序：文字（最常被指）→ 方块/方框/路径 → 网格 → 背景；同类按面积大到小 */
    var RANK = { text: 0, 方块: 1, 方框: 1, 图像: 1, 路径: 2, grid: 3 };
    PICK.items.sort(function (a, b) {
      if (a.bg !== b.bg) return a.bg ? 1 : -1;
      var ra = RANK[a.kind], rb = RANK[b.kind];
      if (ra === undefined) ra = 2;
      if (rb === undefined) rb = 2;
      if (a.all) return -1;
      if (b.all) return 1;
      if (ra !== rb) return ra - rb;
      return (b.w * b.h) - (a.w * a.h);
    });
    var total = PICK.items.length;
    var texts = PICK.items.filter(function (e) { return e.kind === "text"; }).length;
    var grids = PICK.items.filter(function (e) { return e.kind === "grid"; }).length;
    PICK.items = PICK.items.slice(0, PICK_CAP);
    PICK.on = true;
    var info = $("pk-info");
    if (info) {
      info.classList.remove("rv-dim");
      info.textContent = "当前帧 " + fmt(S.t) + "（f" + Math.round(S.t * S.fps) + " @ " +
        S.fps + "fps）：抓到 " + total + " 个元素 —— 文字 " + texts +
        "，ASCII 网格 " + grids + "，方块/路径 " +
        (total - texts - grids) + "（背景已沉底）。" +
        (total > PICK_CAP ? "列表显示前 " + PICK_CAP + " 个。" : "") +
        " 点一项看它框住谁，或直接点画面。";
    }
    paintPickList();
  }

  function paintPickList() {
    var box = $("pk-list");
    if (!box) return;
    box.innerHTML = PICK.items.map(function (e, i) {
      return '<div class="rv-item" data-i="' + i + '">' +
        '<span class="rt">' + Math.round(e.w) + "×" + Math.round(e.h) + "</span>" +
        '<span class="rn">' + (e.label || e.kind) +
        '<br><span class="z">' + e.kind + " " + (e.color || "") +
        " @" + e.x + "," + e.y + (e.n > 1 ? " ×" + e.n : "") + "</span></span></div>";
    }).join("");
  }

  /* 把选中的元素画成方框（元素层，坐标 1920×1080 逻辑） */
  function drawPickBox(e) {
    var lay = $("rv-picklayer");
    if (!lay) return;
    if (!e) { lay.innerHTML = ""; return; }
    lay.innerHTML = '<div class="pk-box" style="left:' + e.x + "px;top:" + e.y +
      "px;width:" + e.w + "px;height:" + e.h + 'px"><span class="pk-tag">' +
      (e.label || e.kind) + "</span></div>";
  }

  function pickInfo(e) {
    return (e.label || e.kind) + " · " + e.kind + " · " + Math.round(e.w) + "×" +
      Math.round(e.h) + " @ " + e.x + "," + e.y;
  }

  /* ─────────────── 成片对照 ─────────────── */
  var refV = $("ref"), refCv = document.createElement("canvas");
  function refReady() { return S.refOn && refV.readyState >= 2; }
  function refDraw() {
    if (!refReady()) return null;
    if (refCv.width !== 1920) { refCv.width = 1920; refCv.height = 1080; }
    var g = refCv.getContext("2d");
    g.drawImage(refV, 0, 0, 1920, 1080);
    return g;
  }
  function refSync() {
    if (!refReady()) return;
    if (Math.abs(refV.currentTime - S.t) > 0.12) refV.currentTime = S.t;
  }

  function drawDiff() {
    var g = refDraw(); if (!g) return;
    var src = document.querySelector("#scenes .scene:last-child canvas.cvs");
    var cv = document.getElementById("rv-diffcv");
    if (!cv) {
      cv = document.createElement("canvas");
      cv.id = "rv-diffcv";
      cv.style.cssText = "position:absolute;inset:0;width:100%;height:100%;z-index:35;pointer-events:none";
      $("rv-scaler").appendChild(cv);
    }
    cv.width = 1920; cv.height = 1080;
    var d = cv.getContext("2d");
    d.clearRect(0, 0, 1920, 1080);
    if (S.diffMode === "side") {
      var half = composite(document.createElement("canvas"), 1920, 1080);
      d.drawImage(half, 0, 0, 960, 1080);
      d.drawImage(refCv, 960, 0, 960, 1080);
      d.fillStyle = "#ffc46b"; d.font = "600 26px monospace"; d.textAlign = "center";
      d.fillText("本页 SEEK(t)", 480, 60); d.fillText("成片 " + fmt(S.t), 1440, 60);
    } else if (S.diffMode === "blend") {
      var cur = composite(document.createElement("canvas"), 1920, 1080);
      d.globalAlpha = 0.5; d.drawImage(refCv, 0, 0); d.globalAlpha = 1;
      d.globalAlpha = 0.5; d.drawImage(cur, 0, 0); d.globalAlpha = 1;
    } else {
      var a = composite(document.createElement("canvas"), 1920, 1080);
      var A = a.getContext("2d").getImageData(0, 0, 1920, 1080);
      var B = g.getImageData(0, 0, 1920, 1080);
      var Aa = A.data, Bb = B.data;
      for (var i = 0; i < Aa.length; i += 4) {
        var dr = Math.abs(Aa[i] - Bb[i]) * 6, dg = Math.abs(Aa[i + 1] - Bb[i + 1]) * 6,
            db = Math.abs(Aa[i + 2] - Bb[i + 2]) * 6;
        Aa[i] = dr > 255 ? 255 : dr; Aa[i + 1] = dg > 255 ? 255 : dg; Aa[i + 2] = db > 255 ? 255 : db;
        Aa[i + 3] = 255;
      }
      d.putImageData(A, 0, 0);
    }
    $("rv-badge-diff").hidden = false;
    $("rv-badge-diff").textContent = S.diffMode === "diff" ? "DIFF ×6" : "对照：" +
      ({ side: "并排", blend: "半透明叠加", diff: "差分 ×6" }[S.diffMode]);
  }
  function clearDiff() {
    var cv = $("rv-diffcv"); if (cv) cv.remove();
    $("rv-badge-diff").hidden = true;
  }

  /* ─────────────── 面板 ─────────────── */
  function buildPanels() {
    var ms = (window.MV && window.MV.moves) || [];
    $("tab-moves").innerHTML = ms.map(function (m, i) {
      return '<div class="rv-item" data-t="' + m.t0 + '"><span class="rt">' +
        fmt(m.t0) + '</span><span class="rn">' + (i + 1) + ". " + m.name +
        '</span><span class="rz">' + m.mode + "</span></div>";
    }).join("") + '<div class="rv-note" style="padding:8px 6px">' +
      (window.MV ? "duration " + window.MV.duration + "s · fps " + window.MV.fps +
        " · hits " + (window.MV.hits || []).length + " · cuts " + (window.MV.cuts || []).length
        : "") + "</div>";

    var ls = (window.FILM && window.FILM.lyrics) || [];
    $("tab-lyrics").innerHTML = ls.map(function (L) {
      return '<div class="rv-item rv-cue" data-t="' + L.t + '"><span class="rt">' +
        fmt(L.t) + '</span><span class="rn">' + L.s.replace(/</g, "&lt;") + "</span></div>";
    }).join("");

    $("sel-ref").innerHTML = '<option value="">无</option>' + (window.__REFS || []).map(function (r) {
      return '<option value="' + r + '">' + r.split("/").pop() + "</option>";
    }).join("");
  }
  function highlight() {
    var mv = curMove(), ls = (window.FILM && window.FILM.lyrics) || [];
    var ci = -1, k;
    for (k = ls.length - 1; k >= 0; k--) if (S.t >= ls[k].t) { ci = k; break; }
    [].forEach.call(document.querySelectorAll("#tab-moves .rv-item"), function (e, i) {
      e.classList.toggle("rv-cur", !!mv && (window.MV.moves[i] || {}).t0 === mv.t0);
    });
    [].forEach.call(document.querySelectorAll("#tab-lyrics .rv-item"), function (e, i) {
      e.classList.toggle("rv-cur", i === ci);
    });
  }
  function log(s) {
    var b = $("log-box");
    b.textContent += s + "\n";
    b.scrollTop = b.scrollHeight;
  }
  function err(s) {
    S.errs.push(s);
    var c = $("chip-err");
    c.hidden = false; c.textContent = S.errs.length + " err";
    log("✗ " + s);
  }

  /* ─────────────── 渲染命令 / 后台任务 ─────────────── */
  function cmdFor(t0, t1) {
    return 'python tools/render.py --t0 ' + t0.toFixed(2) + " --t1 " + t1.toFixed(2) +
      ' --out "review/片段_审片/seg_' + t0.toFixed(0) + "-" + t1.toFixed(0) +
      '.mp4" --ss 1 --fps 30 --crf 16 --preset medium';
  }
  function refreshCmd() { $("cmd-box").textContent = cmdFor(S.t, Math.min(DUR, S.t + 8)); }

  /* 保存结果的统一措辞：离线排队 ≠ 失败。
   * `r.queued` 表示"已排队，服务恢复后自动补写"（不丢数据）；
   * 只有既没成功也没排队（服务器明确报错）才算保存失败。 */
  function saveMsg(r, file, extra) {
    if (r && r.queued) {
      return "⏳ 已排队（服务断开，恢复后自动补写 " + (NET.queue.length) + " 项）";
    }
    if (r && r.ok) return file + (extra || "");
    return "保存失败：" + ((r && r.error) || "未知原因");
  }

  /* ══════════════ 网络层：离线也不丢保存 ══════════════
   * 背景：整轮下来"保存失败：TypeError: Failed to fetch"出现过多次。根因是
   * **服务进程没了**（浏览器还开着），连接被拒 → fetch 连响应都拿不到 → TypeError。
   * 之前每次保存都直接失败，用户的意见/字幕就丢了；现在：
   *   ① POST 失败 → 排队（整份快照，幂等），退避重试，服务回来自动补写
   *   ② 每 2.5s 探活，页面自己"复活"，不需要刷新
   *   ③ 横幅写清楚怎么修：python 04_影片工程/审片台.py
   * GET 类（读字幕/配置/成片清单）失败只提示一次，不刷屏。 */
  var NET = {
    on: true, queue: [], tries: 0, timer: 0, probe: 0, busy: false,
    BACKOFF: [0, 700, 1800, 4500, 9000, 15000]
  };
  function netBanner(msg) {
    var b = $("rv-net");
    if (!b) return;
    if (msg === null) {                    /* null = 恢复正常 */
      b.hidden = true;
      NET.tries = 0;
      $("rv-net-q").textContent = "";      /* 计数也要清，否则横幅收起后还挂着"待写 2 项" */
      return;
    }
    b.hidden = false;
    $("rv-net-msg").textContent = msg ||
      "保存会暂存本页，服务恢复后自动补写"
      + "（重新运行：python 04_影片工程/审片台.py）";
    $("rv-net-q").textContent = NET.queue.length
      ? ("待写 " + NET.queue.length + " 项") : "";
  }
  function netPush(item) {
    /* 同 URL 只保留最后一条（都是整份快照，旧的自动作废） */
    for (var i = NET.queue.length - 1; i >= 0; i--) {
      if (NET.queue[i].path === item.path) NET.queue.splice(i, 1);
    }
    NET.queue.push(item);
    netBanner();
    netSchedule();
  }
  function netSchedule() {
    if (NET.timer) return;
    var d = NET.BACKOFF[Math.min(NET.tries, NET.BACKOFF.length - 1)];
    NET.timer = setTimeout(function () {
      NET.timer = 0;
      netFlush();
    }, d);
  }
  function netFlush() {
    if (NET.busy || !NET.queue.length) return;
    NET.busy = true;
    var item = NET.queue[0], done = false;
    fetch(item.path, item.opt).then(function (r) {
      return r.json().catch(function () { return { ok: false }; });
    }).then(function (j) {
      if (j && j.ok) {                    /* 成功：出队并继续下一条 */
        NET.queue.shift();
        NET.tries = 0;
        if (!NET.queue.length) {
          netBanner(null);
          log("✓ 服务恢复，已补写 " + (item.n || 1) + " 项保存");
        } else {
          netBanner("服务已恢复，正在补写 " + NET.queue.length + " 项…");
        }
      } else {
        NET.tries++;
        err("补写失败：" + ((j && j.error) || "未知原因"));
      }
    }).catch(function () {
      NET.tries++;                        /* 还是连不上，继续等 */
    }).then(function () {
      NET.busy = false;
      done = true;
      if (NET.queue.length) netSchedule();
    });
    return done;
  }
  function netProbe() {
    if (NET.on) return;                    /* 还在线就别探 */
    fetch("review_server.py?action=ping", { cache: "no-store" }).then(function (r) {
      return r.json();
    }).then(function (j) {
      if (j && j.ok) {
        NET.on = true;
        log("✓ 审片台服务已恢复（自动补写中）");
        if (NET.queue.length) {
          /* ⚠️ 探测成功 ≠ 补写完成：队列里还有东西时横幅要留着，
           * 让用户看得见"还在写"，否则会以为已经保存好了。 */
          NET.tries = 0;
          netBanner("服务已恢复，正在补写 " + NET.queue.length + " 项…");
          netFlush();
        } else {
          netBanner(null);
        }
        /* 顺便把配置/字幕读回来，保证界面与磁盘一致 */
        cfgLoad(); loadNotes(); loadSubs();
      }
    }).catch(function () { /* 还不行，下一轮再探 */ });
  }

  function api(path, opt) {
    var isSave = !!(opt && opt.method === "POST");
    /* ⚠️ 字幕/文本类资源必须按文本取：SRT/VTT 不是 JSON，拿 r.json() 解析
     * 必然失败 → 读不到文件 → "切换字幕文件"静默失效（踩过一次）。
     * 判据用扩展名；查询串在扩展名之后的，用正则兼容。 */
    var isText = !opt && /\.(srt|vtt|ass|txt|md)(\?|#|$)/i.test(path);
    var got = isText
      ? fetch(path).then(function (r) {
          if (!r.ok) { return { ok: false, error: "HTTP " + r.status }; }
          return r.text().then(function (t) {
            return { ok: true, text: t, file: path.split("/").pop() };
          });
        })
      : fetch(path, opt).then(function (r) {
          return r.json().catch(function () {
            return { ok: false, error: "响应不是 JSON" };
          });
        });
    return got.catch(function (e) {
      /* ---- 网络层失败（服务没起 / 被 kill / 端口不通）---- */
      NET.on = false;
      if (isSave) {
        netPush({ path: path, opt: opt, n: 1 });
        log("⚠ 服务未响应，保存已排队（" + NET.queue.length + " 项）");
        return { ok: false, offline: true, queued: true };
      }
      netBanner();
      if (!NET.told) {
        NET.told = true;
        err("连不上审片台服务 —— 请重新运行：python 04_影片工程/审片台.py");
        setTimeout(function () { NET.told = 0; }, 8000);
      }
      return { ok: false, offline: true, error: String(e) };
    });
  }

  function startRender(t0, t1) {
    if (S.playing) setPlay(false);
    $("job-box").textContent = "提交中…";
    api("../tools/review_server.py?action=render", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ t0: t0, t1: t1, fps: 30, crf: 16, preset: "medium" })
    }).then(function (r) {
      if (!r.ok) { $("job-box").textContent = "提交失败：" + (r.error || r.msg); return; }
      log("▶ 后台渲染 " + t0.toFixed(2) + "–" + t1.toFixed(2) + "s  job=" + r.id);
      poll(r.id);
    });
  }
  function poll(id) {
    api("../tools/review_server.py?action=job&id=" + id).then(function (r) {
      if (!r.ok) { $("job-box").textContent = "查询失败"; return; }
      $("job-box").textContent = r.state + "  " + Math.round(r.pct || 0) + "%\n" + (r.tail || "");
      if (r.state === "done") { log("✓ 渲染完成：" + r.out); $("job-box").textContent += "\n→ " + r.out; }
      else if (r.state === "error") log("✗ 渲染失败");
      else setTimeout(function () { poll(id); }, 1500);
    });
  }
  function snap() {
    drawFull(S.t);                        /* 导出必须是全画质 */
    var c = document.createElement("canvas");
    c.width = 1920; c.height = 1080;
    composite(c, 1920, 1080);
    c.toBlob(function (b) {
      var a = document.createElement("a");
      a.href = URL.createObjectURL(b);
      a.download = "f" + String(Math.round(S.t * S.fps)).padStart(5, "0") + "_t" +
        S.t.toFixed(2) + ".png";
      a.click();
      log("⤓ 已导出 " + a.download);
    });
  }

  /* ─────────────── 影片全屏（只全屏画面，不是整个界面） ─────────────── */
  var fsIdle = 0;
  function fsOn() { return document.fullscreenElement === $("rv-viewport"); }
  function toggleFull() {
    if (document.fullscreenElement) { document.exitFullscreen(); return; }
    var vp = $("rv-viewport");
    if (vp.requestFullscreen) vp.requestFullscreen();
    else log("这个浏览器不支持 Element.requestFullscreen");
  }
  function wakeFs() {
    var vp = $("rv-viewport");
    if (!vp.classList.contains("rv-fs")) return;
    vp.classList.remove("idle");
    clearTimeout(fsIdle);
    fsIdle = setTimeout(function () { vp.classList.add("idle"); }, 2500);
  }
  function onFsChange() {
    var on = fsOn();
    $("rv-viewport").classList.toggle("rv-fs", on);
    if (!on) $("rv-viewport").classList.remove("idle");
    fit();
    if (on) {
      wakeFs();
      var tip = $("rv-fs-tip");
      tip.style.opacity = "1";
      setTimeout(function () { tip.style.opacity = "0"; }, 3500);
    } else {
      $("rv-fs-tip").style.opacity = "0";
    }
  }
  function fsSeekT(ev) {
    var r = $("fs-bar").getBoundingClientRect();
    var x = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
    return Math.max(0, Math.min(1, x / r.width)) * DUR;
  }

  /* ─────────────── 交互接线 ─────────────── */
  function seek(t) {
    drawFull(Math.max(0, Math.min(DUR - 1e-4, t)));
    audioFollow(true);
  }

  function init() {
    if (window.MV) { DUR = window.MV.duration || DUR; S.fps = window.MV.fps || 60; }
    $("t-dur").textContent = fmt(DUR);
    $("chip-res").textContent = "画布 " + (document.getElementById("fx").width) + "×" +
      (document.getElementById("fx").height) + " · SS=" + (window.ENG ? window.ENG.SS : 1);
    buildBar(); buildPanels();
    fit();
    /* 预热：把 13 个场景各画一帧（扔掉），这样"第一次跳到某段"看到的
       也是暖帧 —— 与 render.py 的预热是同一套道理。 */
    try {
      window.ENG.ADEC = 1; window.ENG.AREUSE = 0;
      window.SEEK(0);
      var ms = (window.MV && window.MV.moves) || [];
      for (var w = 0; w < ms.length; w++) window.SEEK(ms[w].t0 + 1 / 60);
    } catch (e) { /* 预热失败不致命 */ }
    applyLOD("full");
    draw(0); refreshCmd();
    loadNotes();
    loadSubs();
    /* 字幕默认开（用户要求）：按钮文案与状态一开始就对 */
    $("sb-toggle").textContent = SUB.on ? "关闭字幕" : "开启字幕";
    $("sb-toggle").classList.toggle("rv-on", SUB.on);
    /* 字幕文件：先登记内置的影片歌词，再扫工程 review 里的字幕文件 */
    SUB.cur = "film";
    SUB.files["film"] = { key: "film", name: "影片歌词（内置）", kind: "film",
                          url: "", lines: cloneLines(SUB.lines),
                          st: null, dirty: false };
    subFileOptions();
    subScanDisk();
    subFileInfo();
    paintSaveState();
    /* 记住上次打开的字幕文件（配置里存的），磁盘文件读完再切 */
    if (SUB.lastFile && SUB.lastFile !== "film") {
      var tryLast = function (n) {
        if (SUB.files[SUB.lastFile]) {
          var f = SUB.files[SUB.lastFile];
          if (f.kind === "disk" && !f.lines.length) {
            subLoadDisk(f.key).then(function () { subSwitchFile(SUB.lastFile, true); });
          } else {
            subSwitchFile(SUB.lastFile, true);
          }
          return;
        }
        if (n > 0) setTimeout(function () { tryLast(n - 1); }, 300);
      };
      tryLast(6);
    }
    cfgLoad();                 /* ⑦ 载入上次的界面设置 */
    /* 网络层：离线探活（服务回来自动补写，不需要刷新页面） */
    NET.probe = setInterval(netProbe, 2500);
    /* 用 file:// 双击打开时，fetch 会被浏览器直接拒绝 —— 那正是
       "保存失败：TypeError: Failed to fetch" 最常见的另一种原因。
       这里主动说清楚该怎么打开，省得对着报错猜。 */
    if (location.protocol === "file:") {
      NET.on = false;
      netBanner("这是 file:// 直接打开的，浏览器禁止本页访问本地服务 —— "
              + "请改成：运行 python 04_影片工程/审片台.py");
      log("⚠ 检测到 file:// 打开。请运行：python 04_影片工程/审片台.py");
      err("用 file:// 打开时无法保存（浏览器安全限制）");
    }
    $("rv-net-re").onclick = function () {
      log("… 重新连接审片台服务");
      netProbe();
      if (NET.queue.length) { NET.tries = 0; netFlush(); }
    };
    window.addEventListener("online", function () { netProbe(); });
    var miss = Object.keys(MISSING);
    if (miss.length) {
      var bar = $("rv-stale");
      if (bar && bar.id === "rv-stale") {
        bar.hidden = false;
        bar.textContent = "⚠ 页面缺 " + miss.length + " 个控件：" + miss.join(", ") +
          " —— 请按 Ctrl+Shift+R 强制刷新（若仍缺，说明 review.html 与 review.js " +
          "版本不一致，重新安装这两个文件）。";
      }
      console.warn("[review] 缺少控件:", miss);
    }
    log("✓ SEEK 就绪 · " + DUR.toFixed(3) + "s / 原生 " + S.fps + "fps");

    window.addEventListener("resize", fit);
    $("rv-bar").addEventListener("mousedown", down);
    /* 悬停缩略图**只挂在时间条上** —— 之前挂在 window 上，鼠标移到画面里也会
     * 弹出来（还会顺手把画面 SEEK 两次）。 */
    $("rv-bar").addEventListener("mousemove", hover);
    $("rv-bar").addEventListener("click", function (ev) {
      var n = ev.target.closest ? ev.target.closest("#rv-bar-marks i, #rv-bar-ranges i") : null;
      if (!n) return;
      var f = NOTES.filter(function (x) { return x.id === n.dataset.id; })[0];
      if (f) seek(f.t0);
    });
    $("rv-bar").addEventListener("mouseleave", hideHover);
    /* 轨道缩放：Alt+滚轮（两个轨道）+ 按钮 + 双击空白复位 */
    bindZoom($("rv-bar"));
    bindZoom($("rv-subbar"));
    /* 平移滑条：拖滑块 / 点空白 / 滚轮 */
    (function () {
      var bar = $("rv-pan"), th = $("rv-pan-thumb");
      if (!bar || !th) return;
      var drag = null;
      function centerFromX(x) {
        var r = panBox();
        if (!r) return;
        var W = r.width, sp = viewSpan();
        var w = sp >= DUR - 1e-3 ? W : Math.max(PAN_MIN, sp / DUR * W);
        /* 滑块中心 x → 视图中心时刻；再按滑块可达范围夹紧（两端各留半个滑块） */
        var half = w / 2 / W;
        var u = Math.max(half, Math.min(1 - half, x / W));
        panToCenter(u * DUR);
      }
      bar.addEventListener("mousedown", function (ev) {
        var r = panBox();
        if (!r) return;
        var onThumb = ev.target === th;
        if (onThumb) {
          th.classList.add("drag");
          drag = { grab: ev.clientX - th.getBoundingClientRect().left };
          log("平移视图：拖动滑块（当前 " + fmt(VIEW.t0) + " – " + fmt(VIEW.t1) + "）");
        } else {
          centerFromX(ev.clientX - r.left);
          drag = { grab: null };
        }
        ev.preventDefault();
      });
      window.addEventListener("mousemove", function (ev) {
        if (!drag) return;
        var r = panBox();
        if (!r) return;
        if (drag.grab == null) { centerFromX(ev.clientX - r.left); return; }
        centerFromX(ev.clientX - r.left - drag.grab);
      });
      window.addEventListener("mouseup", function () {
        if (!drag) return;
        drag = null;
        th.classList.remove("drag");
        paintPan();                    /* 松手后对齐一次（拖动中已实时跟手）*/
      });
      bar.addEventListener("wheel", function (ev) {
        ev.preventDefault();
        var d = Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
        var sp = viewSpan() * (ev.shiftKey ? 0.4 : 1);
        panToCenter((VIEW.t0 + VIEW.t1) / 2 + (d > 0 ? 1 : -1) * sp);
      }, { passive: false });
      bar.addEventListener("dblclick", viewFit);
    })();

    $("zm-in").onclick = function () { viewZoom(1 / 1.5); };
    $("zm-out").onclick = function () { viewZoom(1.5); };
    $("zm-fit").onclick = viewFit;
    $("rv-bar").addEventListener("dblclick", function (ev) {
      if (ev.target.closest("#rv-bar-sections b, #rv-bar-lyrics b")) return;
      viewFit();
    });
    $("rv-subbar").addEventListener("dblclick", function (ev) {
      if (ev.target.closest("#rv-subbar i")) return;
      viewFit();
    });
    window.addEventListener("mousemove", function (e) { move(e); wakeFs(); inspectAt(e); });
    $("rv-viewport").addEventListener("mouseleave", function () {
      $("rv-inspect-tip").style.display = "none";
    });
    window.addEventListener("mouseup", up);
    $("rv-bar").addEventListener("touchstart", down, { passive: false });
    window.addEventListener("touchmove", function (e) { move(e); }, { passive: false });
    window.addEventListener("touchend", up);
    document.addEventListener("fullscreenchange", onFsChange);
    /* 全屏浮层条 */
    $("fs-play").onclick = function () { setPlay(!S.playing); };
    $("fs-exit").onclick = function () { document.exitFullscreen(); };
    $("fs-bar").addEventListener("mousedown", function (ev) {
      var was = S.playing; if (was) setPlay(false);
      seek(fsSeekT(ev));
      var mv = function (e) { seek(fsSeekT(e)); };
      var up = function () {
        window.removeEventListener("mousemove", mv);
        window.removeEventListener("mouseup", up);
        if (was) setPlay(true);
      };
      window.addEventListener("mousemove", mv);
      window.addEventListener("mouseup", up);
      ev.preventDefault();
    });
    $("rv-fs-tip").addEventListener("click", function () { this.style.opacity = "0"; });

    $("btn-play").onclick = function () { setPlay(!S.playing); };
    $("btn-home").onclick = function () { seek(0); };
    $("btn-end").onclick = function () { seek(DUR - 0.02); };
    $("btn-prev").onclick = function () { seek(S.t - 1 / S.fps); };
    $("btn-next").onclick = function () { seek(S.t + 1 / S.fps); };
    $("btn-loop").onclick = function () {
      S.loop = !S.loop;
      this.classList.toggle("rv-on", S.loop);
      audioFollow(true);
      cfgTouch();
    };
    /* 音频开关：只切"要不要跟"，播放/暂停由传送带统一管 */
    $("btn-audio").onclick = function () {
      S.audioOn = !S.audioOn;
      cfgTouch();
      if (!S.audioOn && au) au.pause();
      audioFollow(true);
      paintAudio();
      log(S.audioOn ? "♪ 原曲同步：开" : "♪ 原曲同步：关");
    };
    $("vol").oninput = function () {
      if (au) au.volume = parseFloat(this.value) / 100;
      cfgTouch();
    };
    $("sel-fps").onchange = function () {
      if (this.value === "custom") {
        $("in-fps").hidden = false;
        $("in-fps").focus();
        $("in-fps").select();
      } else {
        $("in-fps").hidden = true;
        setFps(parseInt(this.value, 10));
      }
    };
    $("in-fps").onchange = function () {
      var v = parseInt(this.value, 10);
      if (!v || v < 1 || v > 240) { log("帧率要在 1~240 之间，已退回 60"); setFps(60); }
      else setFps(v);
      /* 焦点留在输入框里的话，←/→ 逐帧这些快捷键会被输入框吃掉 —— 失焦掉。 */
      this.blur();
    };
    $("sel-speed").onchange = function () {
      S.speed = parseFloat(this.value);
      audioFollow(true);          /* 变速时音频一起变速，保持同步 */
      cfgTouch();
    };
    $("sel-scale").onchange = function () {
      S.scale = this.value; fit(); cfgTouch();
    };
    $("btn-full").onclick = toggleFull;
    $("btn-help").onclick = function () { $("rv-help").hidden = false; };
    $("btn-help-close").onclick = function () { $("rv-help").hidden = true; };
    $("btn-snap").onclick = snap;
    $("btn-clip").onclick = function () { startRender(S.t, Math.min(DUR, S.t + 8)); };
    $("btn-render-all").onclick = function () { startRender(0, DUR); };
    $("btn-copycmd").onclick = function () {
      var t = $("cmd-box").textContent;
      if (navigator.clipboard) navigator.clipboard.writeText(t);
      log("⧉ 已复制：" + t);
    };
    $("btn-mark").onclick = addMark;
    $("btn-mrange").onclick = markRange;
    $("btn-pick").onclick = function () {
      this.classList.toggle("rv-on", !PICK.on);
      PICK.on ? drawPickBox(PICK.sel) : pickRun();
      log(PICK.on ? "⌖ 元素拾取：" + PICK.items.length + " 个元素" : "⌖ 元素框选已关");
    };
    $("btn-diff").onclick = function () {
      S.refOn = !S.refOn;
      this.classList.toggle("rv-on", S.refOn);
      if (S.refOn && refV.src) { refSync(); draw(S.t); } else clearDiff();
    };
    $("sel-diffmode").onchange = function () { S.diffMode = this.value; if (S.refOn) draw(S.t); };
    $("sel-ref").onchange = function () {
      if (!this.value) { S.refOn = false; $("btn-diff").classList.remove("rv-on"); clearDiff(); return; }
      refV.src = this.value; S.refOn = true;
      $("btn-diff").classList.add("rv-on");
      refV.addEventListener("loadeddata", function () { refSync(); draw(S.t); }, { once: true });
    };
    /* 字幕轨选择已移除:字幕来源统一走顶部「字幕」区的 sb-file(由
       subfiles 动态列出)。这里原来挂一个只 log() 的死下拉,它的 option
       还写着 `../06_成片输出/…` —— 移植时漏改的硬编码,点它什么也不会发生。 */

    /* ---- 性能面板 ---- */
    $("pf-mode").onchange = function () {
      var v = this.value; cfgTouch();
      PERF.auto = v === "auto";
      if (v === "l3") { PERF.auto = false; PERF.playAdec = 3; PERF.playReuse = 2; }
      if (v === "l2") { PERF.auto = false; PERF.playAdec = 2; PERF.playReuse = 2; }
      if (v === "reuse") { PERF.auto = false; PERF.playAdec = 1; PERF.playReuse = 2; }
      if (v === "full") { PERF.auto = false; PERF.playAdec = 1; PERF.playReuse = 0; }
      log("加速：" + this.options[this.selectedIndex].text);
    };
    /* 性能页与传送带是**同一个**帧率锁：两个下拉互相同步，自定义共用同一个输入框 */
    $("pf-fps").onchange = function () {
      if (this.value === "custom") {
        $("in-fps").hidden = false; $("in-fps").focus(); $("in-fps").select();
        return;
      }
      $("in-fps").hidden = true;
      setFps(parseInt(this.value, 10));
      cfgTouch();
    };
    $("pf-drag").onchange = function () {
      PERF.dragAdec = parseInt(this.value, 10); cfgTouch();
    };
    $("pf-reset").onclick = function () { perfReset(); paintPerf(); };
    $("cf-save").onclick = function () { cfgSave(true); log("⚙ 配置已立即保存"); };
    $("cf-default").onclick = function () {
      cfgApply({ vol: 0.82, audioOn: true, loop: false, speed: 1, fps: 60,
                 scale: "fit", pf: { mode: "auto", drag: 2 },
                 sub: { on: true, lang: "en", font: "yh", size: 34,
                        color: "#ffffff", stroke: 0, strokeColor: "#000000",
                        bg: "#000000", bga: 0, pad: 6, bottom: 64,
                        align: "center", lh: 1.35, maxw: 1500 },
                 cmp: { mode: "side", ref: "" } });
      cfgSave(true);
      log("⚙ 已恢复默认设置");
    };

    [].forEach.call(document.querySelectorAll(".rv-tab"), function (b) {
      b.onclick = function () {
        [].forEach.call(document.querySelectorAll(".rv-tab"), function (x) { x.classList.remove("rv-on"); });
        [].forEach.call(document.querySelectorAll(".rv-panel"), function (x) { x.classList.remove("rv-on"); });
        b.classList.add("rv-on"); $(b.dataset.tab).classList.add("rv-on");
        if (b.dataset.tab === "tab-perf") paintPerf();
      };
    });
    document.addEventListener("click", function (e) {
      var it = e.target.closest ? e.target.closest(".rv-item") : null;
      if (it && it.dataset.t) { seek(parseFloat(it.dataset.t)); }
    });

    /* ---- 字幕页：逐条直接编辑（无独立输入框）---- */
    var sbBox = $("sb-list");

    /* 行内编辑：所有手势都走这里。
     * ⚠️ 命中判定必须用 closest(".rn")，**不能**用
     * ev.target.classList.contains("rn") —— 光标一旦落在行内浏览器自己插入的
     * 子元素（原生 Enter 产生的 <div>、粘贴带入的 <span>）上，ev.target 就不是
     * .rn，handler 会直接 return，然后**浏览器原生行为接管**：
     * plaintext-only 里 Enter 原生插换行、行首退格原生并到上一块。
     * 外观上就是"Enter 不是拆分而是跳到下一行、行首退格不是并入而是跳到上一句"，
     * 而 Ctrl+Z 走另一条路所以功能看着是好的 —— 典型的"按键没被识别 + 界面没刷新"。 */
    function rnOf(node) {
      return node && node.closest ? node.closest("#sb-list .rn") : null;
    }
    function sbRowOf(node) {
      var n = node && node.closest ? node.closest("#sb-list .rv-item") : null;
      return n ? parseInt(n.dataset.i, 10) : -1;
    }
    /* 把行内容压平成一个纯文本节点：去掉浏览器插进来的换行与子元素。
     * 字幕必须是单行（导出 SRT 才不会出现空行），顺带也让 caretPos 可靠。 */
    function flattenRow(rn) {
      if (!rn) return;
      var hasElem = !!rn.querySelector("div,br");
      /* 有块级子元素时用 innerText —— 它把 <div> 边界还原成换行；
       * textContent 会把"两行双语"压成一行。 */
      var raw = hasElem ? (rn.innerText || "") : (rn.textContent || "");
      var flat = raw.replace(/\r\n?/g, "\n")
                   .replace(/\u2028|\u2029/g, "\n")
                   .replace(/\u00a0/g, " ")
                   .replace(/[ \t]{2,}/g, " ")
                   .replace(/\n{3,}/g, "\n\n")
                   .replace(/^\n+|\n+$/g, "");
      if (!hasElem && flat === raw) return;
      var pos = caretPos(rn);
      rn.textContent = flat;
      setCaret(rn, Math.min(pos, flat.length));
    }
    sbBox.addEventListener("mousedown", function (ev) {
      var i = sbRowOf(ev.target);
      if (i >= 0 && ev.target.classList.contains("rx")) {   /* 行尾 × */
        ev.preventDefault();
        pushUndo("删除本段");
        subDel(i);
        markUnsaved();
        return;
      }
      if (i >= 0 && !rnOf(ev.target)) subSel(i);
    });
    sbBox.addEventListener("focusin", function (ev) {
      var rn = rnOf(ev.target);
      if (!rn) return;
      var i = parseInt(rn.dataset.i, 10);
      if (i === SUB.sel) return;
      pushUndo("选中并编辑");       /* 一次聚焦 = 一步撤销单位 */
      subSel(i);                   /* 只改 class，焦点不动 */
    });
    sbBox.addEventListener("input", function (ev) {
      var rn = rnOf(ev.target);
      if (!rn) return;
      var i = parseInt(rn.dataset.i, 10), l = SUB.lines[i];
      if (!l) return;
      /* 组字中不动 DOM（会把输入法打断），只同步文本 */
      if (ev.isComposing) { l.s = rn.textContent; return; }
      flattenRow(rn);
      l.s = rn.textContent;
      /* ⚠️ 这里绝不能 paintSubList()：会把当前行 innerHTML 换掉，
       * 光标跳到行首，正在打的字就没法连着改了。只更新别处。 */
      paintSubBar(); paintSubs();
      markUnsaved();      /* 打字也是改动：必须标记未保存（自动保存开着时由它落盘）*/
    });
    sbBox.addEventListener("compositionend", function (ev) {
      var rn = rnOf(ev.target);
      if (!rn) return;
      var i = parseInt(rn.dataset.i, 10), l = SUB.lines[i];
      if (!l) return;
      flattenRow(rn);
      l.s = rn.textContent;
      paintSubBar(); paintSubs(); markUnsaved();
    });

    /* ---- 两个手势：拆 / 并（keydown 与 beforeinput 共用） ---- */
    function doSplitAt(i, rn) {
      var l = SUB.lines[i];
      if (!l) return;
      var txt = l.s || "";
      if (!txt) { log("这一行是空的，拆不了"); return; }
      var pos = caretPos(rn);
      /* 光标在句末时"在光标处拆"必然失败（k >= len），而这正是大多数人实际的
       * 按法 —— 自动断在最后一个词之前。 */
      if (pos >= txt.length) {
        var cut = txt.replace(/\s+$/, "").lastIndexOf(" ");
        if (cut > 0) { pos = cut; log("光标在句末 → 已在最后一个词前拆开"); }
        else { log("这一行太短（没有词可断），先把光标放到要拆开的位置"); return; }
      }
      if (pos <= 0) { log("光标在行首，拆不开（要拆成两句请把光标放在中间或句末）"); return; }
      pushUndo("拆分");
      if (!subSplit(i, pos)) { UNDO.pop(); log("拆分失败"); return; }
      subSort();
      subSel(i + 1);
      /* ⚠️ 必须重绘：拆分会改变行数与文本，而 subSel 为了保住输入焦点
       * 已经不重绘列表了（那是"行内打不进字"的修复）。不重绘的话这一行
       * DOM 里还是旧文本 —— 就是"界面没刷新"。 */
      paintSubList();
      markUnsaved();
      var row = sbBox.querySelector('.rn[data-i="' + (i + 1) + '"]');
      if (row) { row.focus(); setCaret(row, 0); }
    }
    function doMergeInto(i, rn) {
      var prev = SUB.lines[i - 1];
      if (!prev) { log("这是第一句，没有上一句可并入"); return; }
      var keep = (prev.s || "").length;
      pushUndo("并入上一句");
      if (!subMergePrev(i)) { UNDO.pop(); log("并入失败"); return; }
      subSort();
      var ni = SUB.lines.findIndex(function (x) { return x.id === prev.id; });
      subSel(ni);
      paintSubList();          /* 同上：并入改了文本与行数，必须重绘 */
      markUnsaved();
      var row = sbBox.querySelector('.rn[data-i="' + ni + '"]');
      if (row) { row.focus(); setCaret(row, keep); }
    }

    /* keydown：拦在原生行为之前 */
    var SB_KEYDONE = 0;
    sbBox.addEventListener("keydown", function (ev) {
      var rn = rnOf(ev.target);
      if (!rn) return;
      var i = parseInt(rn.dataset.i, 10), l = SUB.lines[i];
      if (!l) return;
      if (ev.isComposing) return;            /* 输入法组字中不管 */
      if (ev.key === "Enter" && (ev.altKey || ev.shiftKey)) {
        /* Alt+Enter / Shift+Enter = 在光标处插入换行。
         * 双语字幕要靠它分语言行，所以这里**不能**拆句。 */
        ev.preventDefault();
        ev.stopPropagation();
        SB_KEYDONE = 1;
        insertBreakInRow(rn, i);
        return;
      }
      if (ev.key === "Enter") {
        ev.preventDefault();                 /* 无条件拦：不让原生插换行 */
        ev.stopPropagation();
        SB_KEYDONE = 1;
        doSplitAt(i, rn);
        return;
      }
      if (ev.key === "Backspace") {
        /* 双语字幕：光标紧贴换行时，一次退格就删掉换行（两行合并） */
        if (deleteBreakAtCaret(rn, i, true)) {
          ev.preventDefault();
          ev.stopPropagation();
          return;
        }
        if (!caretIsMerge(rn)) return;       /* 光标不在行首 = 正常删字符 */
        ev.preventDefault();                 /* 行首退格 = 并入上一句 */
        ev.stopPropagation();
        SB_KEYDONE = 1;
        doMergeInto(i, rn);
        return;
      }
      if (ev.key === "Delete") {
        /* 正向删除：光标在第一行末尾（紧贴换行）时一次删掉换行 */
        if (deleteBreakAtCaret(rn, i, false)) {
          ev.preventDefault();
          ev.stopPropagation();
        }
        return;
      }
      if (ev.key === "ArrowUp" || ev.key === "ArrowDown") {
        if (!ev.shiftKey) return;
        ev.preventDefault();
        pushUndo("上下挪位");
        l.y = Math.max(0, Math.min(600, (l.y || 0) +
          (ev.key === "ArrowUp" ? -4 : 4)));
        paintSubList(); paintSubs(); markUnsaved();
        var r3 = sbBox.querySelector('.rn[data-i="' + i + '"]');
        if (r3) { r3.focus(); setCaret(r3, caretPos(rn)); }
        return;
      }
      if (ev.key === "Tab") {
        ev.preventDefault();
        var d = ev.shiftKey ? i - 1 : i + 1;
        var nx = sbBox.querySelector('.rn[data-i="' + d + '"]');
        if (nx) { nx.focus(); placeCaretEnd(nx); }
      }
    });

    /* 显式删除"光标紧贴着的那个换行"。
     * ⚠️ 不能依赖浏览器原生：contenteditable 里换行的删除行为各家不一样
     * （有的删掉换行、有的要按两次、有的把换行当零宽字符跳过去）。
     * 自己改 DOM + 模型 + 光标，一次按键就完成，行为与浏览器无关。 */
    function deleteBreakAtCaret(rn, i, back) {
      var l = SUB.lines[i];
      if (!l) return false;
      var txt = rn.textContent || "";
      var pos = caretPos(rn);
      var at = back ? pos - 1 : pos;             /* 退格看左，Delete 看右 */
      if (at < 0 || at >= txt.length) return false;
      if (txt.charAt(at) !== "\n") return false;
      var next = txt.slice(0, at) + txt.slice(at + 1);
      rn.textContent = next;
      pushUndo(back ? "删换行" : "删换行");
      l.s = next;
      setCaret(rn, at);
      paintSubBar(); paintSubs(); markUnsaved();
      log("已删除换行（两行合并为一句）");
      return true;
    }

    /* 在光标处插入一个真换行（写成文本节点，模型同步） */
    function insertBreakInRow(rn, i) {
      var pos = caretPos(rn);
      var txt = rn.textContent || "";
      var next = txt.slice(0, pos) + "\n" + txt.slice(pos);
      rn.textContent = next;
      var l = SUB.lines[i];
      if (l) {
        pushUndo("插入换行");
        l.s = next;
        paintSubBar(); paintSubs(); markUnsaved();
      }
      setCaret(rn, pos + 1);
    }

    /* beforeinput：权威通路。keydown 被输入法吞掉、或某些浏览器不派发 keydown
     * 时，这里仍然会触发（inputType 已经说明了用户的真实意图）。 */
    sbBox.addEventListener("beforeinput", function (ev) {
      var rn = rnOf(ev.target);
      if (!rn) return;
      if (SB_KEYDONE) { SB_KEYDONE = 0; ev.preventDefault(); return; }
      if (ev.isComposing) return;
      var i = parseInt(rn.dataset.i, 10);
      var type = ev.inputType || "";
      if (type === "insertLineBreak") {
        ev.preventDefault();          /* Shift/Alt+Enter：插换行，不拆句 */
        insertBreakInRow(rn, i);
        return;
      }
      if (type === "insertParagraph") {
        ev.preventDefault();
        doSplitAt(i, rn);
        return;
      }
      if (type === "deleteContentBackward") {
        if (deleteBreakAtCaret(rn, i, true)) { ev.preventDefault(); return; }
        if (caretIsMerge(rn)) {
          ev.preventDefault();
          doMergeInto(i, rn);
        }
        return;
      }
      if (type === "deleteContentForward") {
        if (deleteBreakAtCaret(rn, i, false)) ev.preventDefault();
        return;
      }
      if (type.indexOf("insert") === 0 && ev.data &&
          /[\r\n]/.test(ev.data)) {
        ev.preventDefault();          /* 粘贴进来的换行：压成空格 */
      }
    });

    function caretPos(node) {
      var sel = window.getSelection();
      if (!sel || !sel.rangeCount) return 0;
      var r = sel.getRangeAt(0);
      if (!node.contains(r.startContainer)) return 0;   /* 选区不在本行 */
      var pre = r.cloneRange();
      pre.selectNodeContents(node);
      pre.setEnd(r.startContainer, r.startOffset);
      return pre.toString().length;
    }
    /* 并入上一句的判定：光标在**行首**（选区折叠），或者整行被全选。
     * ⚠️ contenteditable 上 `node.selectionStart` 是 undefined（只有 textarea
     * 才有），所以必须走 Selection API 判定，不能靠 selectionStart。 */
    function caretIsMerge(node) {
      var sel = window.getSelection();
      if (!sel || !sel.rangeCount) return caretPos(node) === 0;
      var r = sel.getRangeAt(0);
      if (!r.collapsed) {
        /* 全选整行 → 也当作"要并入上一句" */
        return r.toString().length >= (node.textContent || "").length;
      }
      return caretPos(node) === 0;
    }
    function setCaret(node, n) {
      var sel = window.getSelection(), r = document.createRange();
      var len = (node.textContent || "").length;
      n = Math.max(0, Math.min(len, n));
      r.setStart(node.firstChild || node, n);
      r.collapse(true);
      sel.removeAllRanges(); sel.addRange(r);
    }
    function placeCaretEnd(node) {
      setCaret(node, (node.textContent || "").length);
    }

    /* ---- 字幕页 ---- */
    /* 字幕外观：任何一项变化都存配置（styleApply 负责回显） */
    ["sb-font", "sb-size", "sb-color", "sb-stroke", "sb-strokecolor", "sb-bg",
     "sb-bga", "sb-pad", "sb-bottom", "sb-align", "sb-lh", "sb-maxw"]
      .forEach(function (id) {
        var e = $(id);
        if (!e) return;
        e.addEventListener("change", cfgTouch);
        e.addEventListener("input", cfgTouch);
      });
    function styleApply() {
      subLastKey = "x";                  /* 强制下一帧重画 */
      paintSubs();
    }
    $("sb-toggle").onclick = function () {
      SUB.on = !SUB.on;
      this.classList.toggle("rv-on", SUB.on);
      this.textContent = SUB.on ? "关闭字幕" : "开启字幕";
      paintSubBar(); paintSubList(); paintSubs();
      cfgTouch();               /* 字幕开关也是设置，要落盘 */
      log("字幕：" + (SUB.on ? "开" : "关") + "（" + SUB.lines.length + " 段）");
    };
    $("sb-import").onclick = function () {
      var f = SUB.files[SUB.cur];
      if (f && f.kind === "disk") { subLoadDisk(f.key); return; }
      subsFromFilm();
      SUB.lines.forEach(function (l, i) { l.id = "L" + i; });
      f.lines = cloneLines(SUB.lines);
      f.dirty = false;
      subSel(-1); markUnsaved(); subFileOptions(); subFileInfo();
      log("已重置为来源数据：" + SUB.lines.length + " 段");
    };
    var FONTMAP = { yh: "yh", src: "src", mono: "mono", serif: "serif" };
    $("sb-font").onchange = function () { SUB.st.font = FONTMAP[this.value]; styleApply(); };
    $("sb-size").oninput = function () {
      SUB.st.size = parseInt(this.value, 10);
      $("sb-size-v").textContent = this.value; styleApply();
    };
    $("sb-color").oninput = function () { SUB.st.color = this.value; styleApply(); };
    $("sb-stroke").oninput = function () { SUB.st.stroke = parseFloat(this.value); styleApply(); };
    $("sb-strokecolor").oninput = function () { SUB.st.strokeColor = this.value; styleApply(); };
    $("sb-bg").oninput = function () { SUB.st.bg = this.value; styleApply(); };
    $("sb-bga").oninput = function () { SUB.st.bga = parseInt(this.value, 10); styleApply(); };
    $("sb-pad").oninput = function () { SUB.st.pad = parseInt(this.value, 10); styleApply(); };
    $("sb-bottom").oninput = function () {
      SUB.st.bottom = parseInt(this.value, 10);
      $("sb-bottom-v").textContent = this.value; styleApply();
    };
    $("sb-align").onchange = function () { SUB.st.align = this.value; styleApply(); };
    $("sb-lh").oninput = function () { SUB.st.lh = parseInt(this.value, 10) / 100; styleApply(); };
    $("sb-maxw").oninput = function () { SUB.st.maxw = parseInt(this.value, 10); styleApply(); };

    /* 选中 / 删除 / 编辑都走上面 #sb-list 的委托；这里只挂工具行。
     * 拆分 / 并入**只在行内用键盘手势**（中间 Enter / 开头 Backspace），
     * 不做独立按钮 —— 两套入口容易让人猜错当前选中的是哪一段。 */
    $("sb-file").onchange = function () { subSwitchFile(this.value); };
    $("sb-add").onclick = function () { $("sb-filein").click(); };
    $("sb-filein").onchange = function () {
      var f = this.files && this.files[0];
      if (f) subImportLocal(f);
      this.value = "";
    };
    $("sb-open").onclick = function () {
      var f = SUB.files[SUB.cur];
      if (f && f.kind === "disk") { subLoadDisk(f.key).then(function (ok) {
        if (ok) { SUB.lines = f.lines; paintSubBar(); paintSubList(); paintSubs(); }
      }); }
      else if (f && f.kind === "film") { subsFromFilm(); SUB.lines.forEach(function (l, i) {
        l.id = "L" + i; }); f.lines = cloneLines(SUB.lines); f.dirty = false;
        paintSubBar(); paintSubList(); paintSubs(); subFileOptions(); subFileInfo();
        log("已回到影片歌词原始数据"); }
      else log("本机导入的文件没有" + "源可重读，要回原文件请重新导入");
    };
    $("sb-undo").onclick = function () { undo(); };
    $("sb-save").onclick = function () { saveSubs(); };
    $("sb-auto").onclick = function () {
      SUB.autoSave = !SUB.autoSave;
      paintSaveState();
      log("自动保存：" + (SUB.autoSave ? "开（改动实时写入文件）" : "关（需手动保存）"));
      if (SUB.autoSave && SUB.files[SUB.cur] && SUB.files[SUB.cur].unsaved) {
        saveSubs();
      }
    };
    $("sb-srt").onclick = function () {
      if (!SUB.lines.length) { log("没有字幕可导出"); return; }
      var f = SUB.files[SUB.cur];
      /* 统一导成 .srt：ASS 轨要是沿用 .ass 名，就会把 SRT 文本写进 .ass 文件 */
      var name = (f ? f.name : "world.execute(me).en")
        .replace(/\.(ass|ssa|vtt|srt)$/i, "") + ".srt";
      api("review_server.py?action=srt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ srt: subsSrt(), dur: DUR, name: name })
      }).then(function (r) {
        if (r && r.ok) {
          log("✓ SRT 已写出 → " + r.file +
            (r.dur ? "（按片长 " + DUR.toFixed(2) + "s 裁剪：截断 " +
                      (r.clipped || 0) + " 条 / 丢弃 " + (r.dropped || 0) + " 条）" : ""));
        } else {
          log(r && r.queued ? "⏳ 服务断开，SRT 已排队"
                            : "导出失败：" + (r.error || "未知"));
        }
      });
    };

    /* 字幕轴拖动 */
    $("rv-subbar").addEventListener("mousedown", subDown);
    window.addEventListener("mousemove", subMove);
    window.addEventListener("mouseup", subUp);
    $("rv-subbar").addEventListener("dblclick", function (ev) {
      var n = ev.target.closest ? ev.target.closest("#rv-subbar i") : null;
      if (n) { var i = parseInt(n.dataset.i, 10); seek(SUB.lines[i].t); }
    });

    /* ---- 元素页 + 意见坞（坞在右栏顶部，冻结，不随列表滚动） ---- */
    function dockShow(e) {
      $("dk-info").textContent = e ? pickInfo(e)
        : (PICK.items.length ? PICK.items.length + " 个元素（点画面或列表选一个）"
                             : "未选中元素 —— 先点「抓取」");
      $("dk-count").textContent = NOTES.length ? NOTES.length + " 条意见" : "";
      $("dk-save").disabled = !e;
    }
    function pickSelect(e, keepText) {
      PICK.sel = e;
      drawPickBox(e);
      dockShow(e);
      if (!keepText) $("dk-text").value = "";
      log(e ? "选中：" + (e.label || e.kind) : "取消选择");
    }
    $("dk-pick").onclick = function () { pickRun(); $("btn-pick").classList.add("rv-on"); };
    $("dk-inspect").onclick = function () { toggleInspect(); };
    $("dk-save").onclick = function () {
      var fix = $("dk-text").value.trim();
      if (!fix) { log("先在坞里写要改成什么"); $("dk-text").focus(); return; }
      if (!PICK.sel) { log("还没选中元素 —— 点画面或列表里的一项"); return; }
      addNote(S.t, S.t, (PICK.sel.label || PICK.sel.kind) + " 附近", fix, PICK.sel, "画面");
      $("dk-text").value = "";
      dockShow(PICK.sel);
      log("✓ 意见已记（含元素坐标）");
    };
    $("dk-cancel").onclick = function () {
      $("dk-text").value = ""; pickSelect(null);
    };
    $("pk-inspect").onclick = function () { toggleInspect(); };
    $("pk-on").onclick = function () {
      pickRun();
      $("btn-pick").classList.add("rv-on");
      dockShow(PICK.sel);
    };
    $("pk-re").onclick = function () { pickRun(); };
    $("pk-clear").onclick = function () { drawPickBox(null); PICK.sel = null; };
    $("pk-list").addEventListener("click", function (ev) {
      var it = ev.target.closest ? ev.target.closest(".rv-item") : null;
      if (!it) return;
      pickSelect(PICK.items[parseInt(it.dataset.i, 10)]);
    });

    /* 画布点选：开启拾取时，点画面选中该处面积最大的元素 */
    $("rv-viewport").addEventListener("click", function (ev) {
      if (!PICK.on || !PICK.items.length) return;
      var r = $("rv-scaler").getBoundingClientRect();
      var lx = (ev.clientX - r.left) / (r.width / 1920);
      var ly = (ev.clientY - r.top) / (r.height / 1080);
      /* 取**面积最小**的命中元素 —— 与 DevTools 一致（点谁就是谁，
       * 而不是被整屏背景吃掉）。 */
      var best = null, bestA = Infinity;
      PICK.items.forEach(function (e) {
        if (lx < e.x - 4 || lx > e.x + e.w + 4) return;
        if (ly < e.y - 4 || ly > e.y + e.h + 4) return;
        var a = e.w * e.h;
        if (a < bestA) { bestA = a; best = e; }
      });
      if (!best) { if (INSPECT.on) pickSelect(null); return; }
      pickSelect(best, true);          /* 保留坞里已写的字，别打断输入 */
    });

    /* ---- 标记页 ---- */
    $("mk-point").onclick = addMark;
    $("mk-range").onclick = markRange;
    $("mk-list").addEventListener("click", function (ev) {
      var it = ev.target.closest ? ev.target.closest(".rv-item") : null;
      if (!it) return;
      var id = it.dataset.id;
      if (ev.target.classList.contains("rz")) {
        NOTES = NOTES.filter(function (x) { return x.id !== id; });
        saveNotes();
        return;
      }
      var f = NOTES.filter(function (x) { return x.id === id; })[0];
      if (f) seek(f.t0);
    });
    $("mk-export").onclick = function () {
      var md = notesMarkdown();
      if (navigator.clipboard) navigator.clipboard.writeText(md);
      log("⧉ 已复制 " + NOTES.length + " 条意见（Markdown）");
    };
    $("mk-open").onclick = function () {
      window.open("../review/审片意见.json", "_blank");
    };

    document.addEventListener("keydown", onKey);
    /* ---- 音频:音量、播完、加载失败;音源由服务端 meta 探测(不硬编码文件名) ---- */
    if (au) {
      au.volume = parseFloat($("vol").value) / 100;
      au.preload = "auto";
      au.addEventListener("loadedmetadata", function () {
        log("♪ 原曲 " + au.duration.toFixed(2) + "s（影片 " + DUR.toFixed(2) + "s）");
        audioFollow(true);
      });
      au.addEventListener("ended", function () {
        if (!S.loop) { log("♪ 原曲播完"); if (S.playing) setPlay(false); }
      });
      au.addEventListener("error", function () {
        err("音频加载失败:" + (AU_NAME || au.getAttribute("src") || "未探测到音频"));
      });
      /* 音源:--audio > <root>/src · assets · audio · 根 下的音频文件(服务端探测)。
       * 没有音频不影响逐帧审片,所以只提示不阻断。 */
      api("review_server.py?action=meta").then(function (m) {
        if (m && m.ok && m.audio) {
          AU_NAME = m.audio_name || "";
          au.src = m.audio;
          log("♪ 音源:" + (AU_NAME || m.audio));
        } else if (m && m.ok) {
          log("♪ 未探测到音频(" + (m.hint || "") + "),逐帧审片不受影响");
        }
      });
    }
    refV.addEventListener("timeupdate", function () {
      if (S.refOn && !dragging) { refSync(); if (Math.abs(refV.currentTime - S.t) < 0.2) drawDiff(); }
    });
  }

  /* 时间点标记：M 直接记（默认分类"画面"）。区间：R 两次。 */
  function addMark() {
    addNote(S.t, S.t, "这里需要改", "", null, "画面");
    log("✚ 时间点意见 @" + fmt(S.t) + "（去「标记」页写具体建议）");
  }
  function markRange() {
    if (rangeAnchor === null) {
      rangeAnchor = S.t;
      log("▭ 区间起点 " + fmt(S.t) + "，再按一次定终点（或直接用播放头）");
      return;
    }
    var a = rangeAnchor, b = S.t;
    rangeAnchor = null;
    if (b < a) { var t = a; a = b; b = t; }
    if (b - a < 1 / S.fps) b = a + 0.2;                 /* 至少 0.2s，别是零宽 */
    addNote(a, b, "这一段需要改", "", null, "画面");
    log("▭ 区间意见 " + fmt(a) + " – " + fmt(b));
  }

  function onKey(e) {
    /* ⚠️ Ctrl+Z 必须在这里拦：撤销时焦点在字幕文本框里，
     * 下一行的"表单控件不劫持按键"会直接 return，撤销就永远不触发。 */
    if ((e.key || "").toLowerCase() === "z" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault(); undo(); return;
    }
    /* ⚠️ 白名单必须包含 **TEXTAREA** 和 **contenteditable**（字幕行就是
     * contenteditable）。之前只挡了 INPUT/SELECT，结果在字幕行里打 s/b/f/r
     * 会触发"导出 PNG / 全屏 / 渲片段"，打字就乱套。
     * 另外 Ctrl+Z 已经在这里单独处理（撤销要在白名单之前拦）。 */
    var tg = e.target;
    var typing = tg && (tg.tagName === "INPUT" || tg.tagName === "SELECT" ||
                        tg.tagName === "TEXTAREA" || tg.isContentEditable);
    if (typing && !((e.key || "").toLowerCase() === "z" && (e.ctrlKey || e.metaKey))) {
      return;
    }
    var k = e.key, ls = (window.FILM && window.FILM.lyrics) || [], ms = (window.MV && window.MV.moves) || [];
    var step = e.shiftKey ? 10 : 1;
    if (k === " ") { e.preventDefault(); setPlay(!S.playing); }
    else if (k === "ArrowLeft" || k === "ArrowRight") {
      /* 逐帧必须是 **Ctrl + 方向键**：裸 ←/→ 留给文本框移动光标。
       * Shift+Ctrl = 十帧。文本框外按裸 ←/→ 不做事，只提示一次。 */
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        if (S.playing) setPlay(false);
        seek(S.t + (k === "ArrowRight" ? 1 : -1) * step / S.fps);
      } else if (!S.arrowTold) {
        S.arrowTold = 1;
        log("← / → 在文本框里用于移动光标；逐帧请用 Ctrl+← / Ctrl+→");
        setTimeout(function () { S.arrowTold = 0; }, 6000);
      }
    }
    else if (k === "Home") seek(0);
    else if (k === "End") seek(DUR - 0.02);
    else if (k === "[") { for (var i = ls.length - 1; i >= 0; i--) if (ls[i].t < S.t - 0.05) { seek(ls[i].t); break; } }
    else if (k === "]") { for (var j = 0; j < ls.length; j++) if (ls[j].t > S.t + 0.05) { seek(ls[j].t); break; } }
    else if (k === ",") { var p = S.marks.filter(function (m) { return m.t < S.t - 0.05; }).pop(); if (p) seek(p.t); }
    else if (k === ".") { var n = S.marks.filter(function (m) { return m.t > S.t + 0.05; })[0]; if (n) seek(n.t); }
    else if (k >= "1" && k <= "9") { var mi = parseInt(k, 10) - 1; if (ms[mi]) seek(ms[mi].t0); }
    else if (k === "0") seek(0);
    else if (k === "l" || k === "L") $("btn-loop").click();
    else if (k === "a" || k === "A") $("btn-audio").click();
    else if (k === "m") addMark();
    /* Shift+M 才是区间标记 —— 之前写成独立的 else if(k === "M")，结果被上一条
       k === "M" 分支先匹配，区间永远触发不了。 */
    else if (k === "M" || k === "k") { if (e.shiftKey) markRange(); else addMark(); }
    else if (k === "p" || k === "P") $("btn-pick").click();
    else if (e.key === "C" && e.shiftKey && e.ctrlKey) { e.preventDefault(); toggleInspect(); }
    else if (k === "Escape" && INSPECT.on) toggleInspect(false);
    else if (k === "b" || k === "B") $("sb-toggle").click();
    else if (k === "s" || k === "S") snap();
    else if (k === "r" || k === "R") $("btn-clip").click();
    else if (k === "d" || k === "D") $("btn-diff").click();
    else if (k === "f" || k === "F") $("btn-full").click();
    else if (k === "?" || k === "/") $("rv-help").hidden = !$("rv-help").hidden;
    else if (k === "Escape") $("rv-help").hidden = true;
    else return;
    refreshCmd();
  }

  window.addEventListener("error", function (e) { err(e.message); });
  window.addEventListener("unhandledrejection", function (e) { err(String(e.reason)); });

  /* 版本自检：页面结构缺控件 ⇒ 标签页是旧的，直接红条提示，
   * 否则用户会以为"选项不存在"（帧率档位就是这么被漏掉的）。 */
  function staleCheck() {
    var need = ["sel-fps", "in-fps", "sel-speed", "sel-scale", "btn-mark", "btn-snap",
                "btn-clip", "btn-diff", "btn-full", "btn-help", "rv-bar", "rv-hover",
                "fs-bar", "pf-mode", "tab-perf", "vol", "btn-audio"];
    var miss = need.filter(function (id) { return !document.getElementById(id); });
    var box = document.getElementById("rv-stale");
    if (!miss.length) return;
    if (box) {
      box.hidden = false;
      box.textContent = "⚠ 这个标签页是旧版本（缺 " + miss.length + " 个控件：" +
        miss.slice(0, 6).join(", ") + "）—— 请按 Ctrl+Shift+R 强制刷新后重试。";
    }
  }

  function boot() {
    staleCheck();
    try { S.marks = JSON.parse(localStorage.getItem("rv-marks") || "[]"); } catch (e) { S.marks = []; }
    if (window.__READY) init();
    else { var n = 0; var iv = setInterval(function () {
      if (window.__READY) { clearInterval(iv); init(); }
      else if (++n > 200) { clearInterval(iv); err("__READY 超时（脚本没加载完？）"); }
    }, 50); }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  /* 供 tools/review_server.py 注入成片清单 */
  window.__setRefs = function (list) { window.__REFS = list; };
  /* 供无头测试 / 脚本化审片（tools 里的自检就是靠它驱动） */
  window.__rv = {
    seek: function (t) { seek(t); },
    play: setPlay,
    state: S,
    perf: PERF,
    lod: applyLOD,
    perfReset: perfReset,
    perfText: function () { return perfLine(); },
    composite: composite,
    mark: addMark,
    notes: notesMarkdown,
    pick: pickRun,
    pickItems: function () { return PICK.items; },
    subs: SUB, subSplit: subSplit, subMergePrev: subMergePrev,
    /* 保存动作也暴露出去：自检脚本可以离线触发，不用去点 UI */
    subSort: subSort, subDel: subDel, subData: subsData,
    /* 解析器与文件管理：脚本化自检要靠它们逐个验证格式 */
    parseSub: parseSub, parseAss: parseAss, parseCue: parseCue,
    subFormat: subFormat,
    subSwitchFile: subSwitchFile, subLoadDisk: subLoadDisk,
    subFileOptions: subFileOptions, subFileInfo: subFileInfo,
    saveSubs: saveSubs, saveNotes: saveNotes, cfgSave: cfgSave,
    markUnsaved: markUnsaved, paintSaveState: paintSaveState,
    subTargetName: subTargetName,
    net: NET, netFlush: netFlush,
    subSel: subSel, subAt: subAt, srt: subsSrt, subStyle: subCss,
    subDrag: function () { return subDrag; },
    subReload: function () { SUB.lines = []; loadSubs(); },
    subFill: function (n) { while (SUB.lines.length < n) SUB.lines.push(      { id: 'x' + SUB.lines.length, t: 0, e: 1, s: 'x', y: 0 }); },
    addNote: addNote,
  };
})();
