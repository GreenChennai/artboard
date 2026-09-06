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

// 站点 → 页面图片 CDN 特征(「导出本页素材」用)
const IMG_HOSTS = {
  "huaban_cookie": /gd-hbimg\.huaban\.com/,
  "pinterest_cookie": /i\.pinimg\.com/,
  "iconfont_cookie": /(?:iconfont\.cn|aliyunic\.com)/
};

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
  document.getElementById("export").disabled = false;

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

// 「导出本页素材」:在真实浏览器页面里收集图片(绕开花瓣等站点的程序化访问 WAF),
// JSON 直接进剪贴板 → artboard 里 `fetch_asset.py --source clipboard --download` 入库
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
          items.push({
            src,
            alt: (img.alt || "").slice(0, 60),
            link: (img.closest("a") && img.closest("a").href) || ""
          });
        }
        let query = "";
        try { query = new URL(location.href).searchParams.get("q") ||
                         new URL(location.href).searchParams.get("query") || ""; } catch {}
        return { site: location.hostname, page_url: location.href, query, items };
      },
      args: [imgHost.source]
    });
    if (!result || !result.items.length) {
      $site.innerHTML = `当前站点:<b>${current.label}</b> — <span class="bad">本页没收集到素材图,先滚动加载/翻页再试</span>`;
      return;
    }
    const payload = JSON.stringify(result);
    $out.style.display = "block";
    $out.value = payload;
    try {
      await navigator.clipboard.writeText(payload);
      $btn.textContent = `✓ 已复制 ${result.items.length} 条素材 JSON`;
    } catch {
      $btn.textContent = `已生成 ${result.items.length} 条,请手动全选复制 ↓`;
    }
    $tip.innerHTML =
      `<span class="ok">下一步:</span>运行 <b>python fetch_asset.py --theme 主题名 ` +
      `--source clipboard --download</b>,素材自动入库(CREDITS 自动登记)。`;
  } catch (e) {
    $site.innerHTML = `当前站点:<b>${current.label}</b> — <span class="bad">导出失败: ${e.message}</span>`;
  }
});
