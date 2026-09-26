// artboard 素材 Bridge · service worker(MV3)
// 职责:维护到本地服务(127.0.0.1)的 WS 连接,执行 collect/download 指令。
// 安全:只连 ws://127.0.0.1;一次性 token 由 popup 显式输入并点「连接」(= 本次会话授权);
//      采集仅对白名单域名执行(chrome.scripting 的 host_permissions 也只在白名单域生效);
//      不读写 cookie 明文到任何存储;不上传数据到外部。

// 白名单:与 manifest host_permissions 一致,双保险
const ALLOWED = /(^|\.)((huaban\.com)|(iconfont\.cn)|(pinterest\.[a-z.]+)|(svgrepo\.com)|(iconify\.design))$/i;

let ws = null;
let cred = null; // {port, token}(chrome.storage.local 持久;SW 重启自动重连)

function setStatus(state, detail) {
  chrome.storage.session?.set({ bridgeState: { state, detail, ts: Date.now() } });
}

function collectInTab(tabId, opts) {
  return chrome.scripting.executeScript({
    target: { tabId },
    func: (o) => new Promise(async (resolve) => {
      const seen = new Set();
      const items = [];
      const grab = () => {
        for (const img of document.images) {
          const src = img.currentSrc || img.src || "";
          if (!src.startsWith("http") || seen.has(src)) continue;
          seen.add(src);
          items.push({
            url: src,
            thumb: src,
            w: img.naturalWidth || 0,
            h: img.naturalHeight || 0,
            link: (img.closest("a") && img.closest("a").href) || location.href
          });
        }
      };
      const scrollTimes = o.scroll ? Math.min(o.pages || 1, 5) * 3 : 0;
      for (let i = 0; i < scrollTimes; i++) {
        window.scrollTo(0, document.body.scrollHeight);
        await new Promise(r => setTimeout(r, 700));
        if (o.limit && items.length >= o.limit) break;
      }
      grab();
      resolve(items.slice(0, o.limit || 50));
    }),
    args: [opts]
  });
}

async function handleCollect(msg) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  let host = "";
  try { host = new URL(tab.url).hostname; } catch { /* 忽略 */ }
  if (!ALLOWED.test(host)) {
    return { type: "items", items: [], error: `域名不在白名单: ${host || "无法解析"}` };
  }
  const [{ result }] = await collectInTab(tab.id, {
    scroll: !!msg.scroll, pages: msg.pages || 1, limit: msg.limit || 50
  });
  return { type: "items", items: result || [] };
}

function waitForTabComplete(tabId, timeoutMs) {
  return new Promise((resolve) => {
    const t0 = Date.now();
    const timer = setInterval(async () => {
      try {
        const tab = await chrome.tabs.get(tabId);
        if (tab.status === "complete") { clearInterval(timer); resolve(true); }
      } catch (e) { clearInterval(timer); resolve(false); }
      if (Date.now() - t0 > (timeoutMs || 20000)) { clearInterval(timer); resolve(true); }
    }, 250);
  });
}

// 采集自动化:如花瓣「素材范围=不看素材」(ant-dropdown-trigger);失败如实报告不重试轰炸
async function runAutomations(tabId, automations) {
  if (!automations || !automations.length) return { applied: [], failed: [] };
  const out = { applied: [], failed: [] };
  for (const a of automations) {
    try {
      const [{ result }] = await chrome.scripting.executeScript({
        target: { tabId },
        func: (triggerText, optionText) => {
          const triggers = [...document.querySelectorAll(".ant-dropdown-trigger, [class*='dropdown-trigger']")];
          const trig = triggers.find(el => (el.textContent || "").includes(triggerText));
          if (!trig) return "trigger_not_found";
          trig.click();
          return new Promise((resolve) => {
            setTimeout(() => {
              const opts = [...document.querySelectorAll(".ant-dropdown li, .ant-dropdown-menu-item, [class*='dropdown'] li, li, span, div")]
                .filter(el => el.children.length === 0 && (el.textContent || "").trim() === optionText);
              if (!opts.length) return resolve("option_not_found");
              opts[opts.length - 1].click();
              resolve("clicked");
            }, 600);
          });
        },
        args: [a.trigger || "素材范围", a.option || "不看素材"]
      });
      (result === "clicked" ? out.applied : out.failed).push(a.trigger + "=" + a.option + ":" + result);
    } catch (e) {
      out.failed.push(a.trigger + "=" + a.option + ":" + e.message);
    }
  }
  return out;
}

// 打开新后台标签 → 等加载 → (可选自动化)→ 采集 → 回带 tabId
async function handleOpen(msg) {
  let host = "";
  try { host = new URL(msg.url).hostname; } catch { return { type: "items", items: [], error: "URL 无法解析" }; }
  if (!ALLOWED.test(host)) {
    return { type: "items", items: [], error: `域名不在白名单: ${host}` };
  }
  const tab = await chrome.tabs.create({ url: msg.url, active: false });
  await waitForTabComplete(tab.id, 25000);
  if (msg.automations) { var autos = await runAutomations(tab.id, msg.automations); }
  await new Promise(r => setTimeout(r, 800)); // 自动化/懒加载缓冲
  const [{ result }] = await collectInTab(tab.id, {
    scroll: !!msg.scroll, pages: msg.pages || 1, limit: msg.limit || 50
  }).catch(() => [{ result: [] }]);
  return { type: "items", items: result || [], tabId: tab.id, url: msg.url,
           automations: autos || { applied: [], failed: [] } };
}

async function handleCloseTab(msg) {
  const ids = (msg.tabIds || []).filter(Number.isFinite);
  try { await chrome.tabs.remove(ids); } catch (e) { /* 已关的忽略 */ }
  return { type: "closed", closed: ids };
}

// Cookie 自动抓取(白名单站;仅经 localhost 回传,由 MCP 写进本机 config.json)
async function handleCookie(msg) {
  let host = "";
  try { host = new URL(msg.url).hostname; } catch { return { type: "cookies", error: "URL 无法解析" }; }
  if (!ALLOWED.test(host)) {
    return { type: "cookies", error: `域名不在白名单: ${host}` };
  }
  const cookies = await chrome.cookies.getAll({ url: msg.url });
  return { type: "cookies", url: msg.url, count: cookies.length,
           cookie: cookies.map(c => `${c.name}=${c.value}`).join("; ") };
}

async function handleDownload(msg) {
  const results = [];
  for (const url of (msg.urls || []).slice(0, 20)) {
    try {
      await chrome.downloads.download({ url, conflictAction: "uniquify" });
      results.push({ url, ok: true });
    } catch (e) {
      results.push({ url, ok: false, error: e.message });
    }
  }
  return { type: "downloaded", results };
}

function connect(port, token) {
  cred = { port: Number(port), token };
  try { chrome.storage.local.set({ cred }); } catch { /* 忽略 */ }
  try { chrome.alarms.create("bridge-keepalive", { periodInMinutes: 0.5 }); } catch { /* 旧版最低 1 */ }
  if (ws) { try { ws.close(); } catch { /* 忽略 */ } }
  ws = new WebSocket(`ws://127.0.0.1:${port}`);
  setStatus("connecting", `连接 127.0.0.1:${port} …`);

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "hello", token, role: "extension" }));
  };
  ws.onmessage = async (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type === "ready") {
      setStatus("ready", `已授权会话(127.0.0.1:${port});关闭本页或点断开即撤销`);
      return;
    }
    if (msg.type === "bye") {
      setStatus("closed", `服务端拒绝: ${msg.error || "未知"}`);
      try { ws.close(); } catch { /* 忽略 */ }
      ws = null;
      return;
    }
    if (msg.type === "collect") {
      const out = await handleCollect(msg);
      ws.send(JSON.stringify(out));
    } else if (msg.type === "open") {
      const out = await handleOpen(msg);
      ws.send(JSON.stringify(out));
    } else if (msg.type === "close_tab") {
      const out = await handleCloseTab(msg);
      ws.send(JSON.stringify(out));
    } else if (msg.type === "cookie") {
      const out = await handleCookie(msg);
      ws.send(JSON.stringify(out));
    } else if (msg.type === "download") {
      const out = await handleDownload(msg);
      ws.send(JSON.stringify(out));
    }
  };
  ws.onclose = () => {
    setStatus("closed", "会话已断开(关闭 popup 不断开;点「断开」或重启服务重新授权)");
    ws = null;
  };
  ws.onerror = () => setStatus("error", "连接失败:服务未启动或端口不对");
}

// ---- 自愈:SW 被杀后,alarm/唤醒事件触发时用保存的凭据静默重连 ----
function selfHeal() {
  if (cred) return connect(cred.port, cred.token);
  chrome.storage.local.get("cred", (d) => {
    if (d.cred && d.cred.port && d.cred.token) connect(d.cred.port, d.cred.token);
  });
}
try {
  chrome.alarms.onAlarm.addListener((a) => {
    if (a.name === "bridge-keepalive" && (!ws || ws.readyState > 1)) selfHeal();
  });
} catch { /* alarms 不可用时退化为「开 popup 即重连」 */ }
selfHeal(); // SW 每次冷启动都尝试恢复会话

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type === "bridge-connect") {
    connect(Number(msg.port), msg.token);
    reply({ ok: true });
  } else if (msg.type === "bridge-disconnect") {
    if (ws) { try { ws.close(); } catch { /* 忽略 */ } }
    ws = null;
    cred = null;  // 显式断开 = 撤销绑定记忆(否则 alarms 自愈 1 分钟内会复活,语义矛盾)
    try {
      chrome.storage.local.remove("cred");
      chrome.alarms.clear("bridge-keepalive");
    } catch { /* 忽略 */ }
    setStatus("closed", "已手动断开(自愈已停;重连请再点「连接本机会话」)");
    reply({ ok: true });
  } else if (msg.type === "bridge-state") {
    chrome.storage.session?.get("bridgeState", (d) => reply(d.bridgeState || { state: "idle" }));
  }
  return true; // 异步 reply
});
