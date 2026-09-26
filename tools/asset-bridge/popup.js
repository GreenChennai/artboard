// artboard 素材 Bridge · popup(Cookie 抓取/导出 = cookie-extension 向后兼容;+ Bridge 授权连接)

// 站点 → config.json 键名映射(与 scripts/_config.py、fetch_asset.py 一致)
const SITES = [
  { match: /(^|\.)huaban\.com$/i,        label: "花瓣 Huaban",     key: "huaban_cookie" },
  { match: /(^|\.)iconfont\.cn$/i,       label: "阿里巴巴图标库",   key: "iconfont_cookie" },
  { match: /(^|\.)pinterest\.[a-z.]+$/i, label: "Pinterest",      key: "pinterest_cookie" }
];
// 站点 → 页面图片 CDN 特征(「导出本页素材」用)
const IMG_HOSTS = {
  huaban_cookie: /gd-hbimg\.huaban\.com/,
  pinterest_cookie: /i\.pinimg\.com/,
  iconfont_cookie: /(?:iconfont\.cn|aliyunic\.com)/
};

const $site = document.getElementById("site");
const $out = document.getElementById("out");
const $tip = document.querySelector(".tip");
const $state = document.getElementById("state");

let current = null;

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

(async () => {
  try {  // 回填上次端口/token(SW 自愈重连无需重填)
    const d = await chrome.storage.local.get("cred");
    if (d.cred) {
      document.getElementById("port").value = d.cred.port || "";
      document.getElementById("token").value = d.cred.token || "";
    }
  } catch { /* 忽略 */ }
  const tab = await activeTab();
  let host = "";
  try { host = new URL(tab.url).hostname; } catch { /* chrome:// 页等 */ }
  const site = SITES.find((s) => s.match.test(host));
  if (site) {
    current = { ...site, url: tab.url };
    $site.innerHTML = `当前站点:<b>${site.label}</b>(${host})`;
    document.getElementById("grab").disabled = false;
    document.getElementById("export").disabled = false;
    const cookies = await chrome.cookies.getAll({ url: tab.url });
    if (!cookies.length) $site.innerHTML += ` — <span class="bad">未检测到 Cookie,请先登录</span>`;
  } else {
    $site.innerHTML = `当前站点:<span class="bad">${host || "不支持的页面"}</span>`;
    $site.innerHTML += "<br>Cookie/导出功能需在 花瓣 / iconfont / Pinterest 页面使用;" +
      "Bridge 连接功能与此页无关,可直接使用。";
  }
  renderState();
})();

document.getElementById("grab").addEventListener("click", async () => {
  if (!current) return;
  const cookies = await chrome.cookies.getAll({ url: current.url });
  if (!cookies.length) {
    $site.innerHTML = `当前站点:<b>${current.label}</b> — <span class="bad">未检测到 Cookie,请先登录</span>`;
    return;
  }
  const cookieStr = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
  const safe = cookieStr.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const snippet = `"${current.key}": "${safe}"`;
  $out.style.display = "block";
  $out.value = snippet;
  try {
    await navigator.clipboard.writeText(snippet);
    document.getElementById("grab").textContent = "✓ 已复制,粘贴进 artboard config.json";
  } catch {
    document.getElementById("grab").textContent = "已生成,请手动全选复制 ↓";
  }
});

// 旧通道:整页素材 JSON → 剪贴板 → fetch_asset.py --source clipboard 入库
document.getElementById("export").addEventListener("click", async () => {
  if (!current) return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const imgHost = IMG_HOSTS[current.key];
  try {
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (hostReSrc) => {
        const hostRe = new RegExp(hostReSrc);
        const seen = new Set();
        const items = [];
        for (const img of document.images) {
          const src = img.currentSrc || img.src || "";
          if (!src.startsWith("http") || !hostRe.test(src) || seen.has(src)) continue;
          seen.add(src);
          items.push({ src, alt: (img.alt || "").slice(0, 60),
                       link: (img.closest("a") && img.closest("a").href) || "" });
        }
        let query = "";
        try { query = new URL(location.href).searchParams.get("q") ||
                         new URL(location.href).searchParams.get("query") || ""; } catch {}
        return { site: location.hostname, page_url: location.href, query, items };
      },
      args: [imgHost.source]
    });
    if (!result || !result.items.length) {
      $site.innerHTML = `当前站点:<b>${current.label}</b> — <span class="bad">本页没收集到素材图,先滚动加载再试</span>`;
      return;
    }
    const payload = JSON.stringify(result);
    $out.style.display = "block";
    $out.value = payload;
    try { await navigator.clipboard.writeText(payload); } catch { /* 手动复制 */ }
    $tip.innerHTML = `<span class="ok">下一步:</span>python fetch_asset.py --theme 主题名 --source clipboard --download`;
  } catch (e) {
    $site.innerHTML = `当前站点:<b>${current.label}</b> — <span class="bad">导出失败: ${e.message}</span>`;
  }
});

// ---- Bridge 授权连接 ----
const $port = document.getElementById("port");
const $token = document.getElementById("token");

document.getElementById("connect").addEventListener("click", () => {
  const port = parseInt($port.value, 10);
  const token = $token.value.trim();
  if (!port || !token) {
    $state.className = "state err";
    $state.textContent = "端口与 token 都要填(bridge.py --json 输出);token 只授权本会话。";
    return;
  }
  chrome.runtime.sendMessage({ type: "bridge-connect", port, token });
  $state.className = "state";
  $state.textContent = "连接中…";
});

document.getElementById("disconnect").addEventListener("click", () => {
  chrome.runtime.sendMessage({ type: "bridge-disconnect" });
});

async function renderState() {
  const st = await chrome.runtime.sendMessage({ type: "bridge-state" });
  if (!st) return;
  $state.className = "state " + (st.state === "ready" ? "ok" : (st.state === "error" ? "err" : ""));
  $state.textContent = { ready: `✓ ${st.detail || "会话已授权"}`,
                         connecting: st.detail || "连接中…",
                         error: st.detail || "连接失败",
                         closed: st.detail || "已断开",
                         idle: "未连接" }[st.state] || "未连接";
}
