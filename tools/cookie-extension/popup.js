// 站点 → config.json 键名映射(与 artboard/scripts/_config.py、fetch_asset.py 保持一致)
const SITES = [
  { match: /(^|\.)huaban\.com$/i,      label: "花瓣 Huaban",       key: "huaban_cookie" },
  { match: /(^|\.)iconfont\.cn$/i,     label: "阿里巴巴图标库",     key: "iconfont_cookie" },
  { match: /(^|\.)pinterest\.[a-z.]+$/i, label: "Pinterest",       key: "pinterest_cookie" }
];

const $site = document.getElementById("site");
const $btn = document.getElementById("grab");
const $out = document.getElementById("out");
const $tip = document.getElementById("tip");

let current = null; // { label, key, url }

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

(async () => {
  const tab = await activeTab();
  let host = "";
  try { host = new URL(tab.url).hostname; } catch { /* chrome:// 页等 */ }
  const site = SITES.find(s => s.match.test(host));

  if (!site) {
    $site.innerHTML = `当前站点:<span class="bad">${host || "不支持的页面"}</span>`;
    $tip.innerHTML = "请先打开并登录 花瓣 / iconfont / Pinterest,再打开本插件。" + $tip.innerHTML;
    return;
  }
  current = { ...site, url: tab.url };
  $site.innerHTML = `当前站点:<b>${site.label}</b>(${host})`;

  // 预检是否已登录(有 cookie)
  const cookies = await chrome.cookies.getAll({ url: tab.url });
  if (!cookies.length) {
    $site.innerHTML += ` — <span class="bad">未检测到 Cookie,请先登录</span>`;
  }
  $btn.disabled = false;
})();

$btn.addEventListener("click", async () => {
  if (!current) return;
  const cookies = await chrome.cookies.getAll({ url: current.url });
  if (!cookies.length) {
    $site.innerHTML = `当前站点:<b>${current.label}</b> — <span class="bad">未检测到 Cookie,请先登录</span>`;
    return;
  }
  const cookieStr = cookies.map(c => `${c.name}=${c.value}`).join("; ");
  // 转义双引号与反斜杠,保证片段可直接粘进 config.json
  const safe = cookieStr.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  const snippet = `"${current.key}": "${safe}"`;

  $out.style.display = "block";
  $out.value = snippet;
  try {
    await navigator.clipboard.writeText(snippet);
    $btn.textContent = "✓ 已复制,粘贴进 artboard config.json";
  } catch {
    $btn.textContent = "已生成,请手动全选复制 ↓";
  }
  $tip.innerHTML =
    `<span class="ok">下一步:</span>打开 artboard/config.json,把片段合并进 JSON` +
    `(替换或新增 "${current.key}" 一行),保存即生效,无需重启。`;
});
