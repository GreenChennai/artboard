#!/usr/bin/env python3
"""Build a self-contained WeChat article preview-and-copy page.

The page is a lightweight bridge to the official 135 editor, not an editor clone:
it previews one or more HTML fragments in a sandboxed iframe and copies the
selected fragment as text/html + text/plain for pasting into 135/WeChat.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import tempfile
from pathlib import Path
from string import Template

MAX_DOCS = 100
MAX_TOTAL_BYTES = 64 * 1024 * 1024
EDITOR_URL = "https://www.135editor.com/"

PAGE_TEMPLATE = Template(r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>$page_title</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#edf2f6;color:#263445;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
.top{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid #dce4eb;padding:16px 22px;box-shadow:0 3px 12px rgba(18,45,68,.08)}
.wrap{max-width:980px;margin:0 auto}
.title{font-size:22px;font-weight:800;line-height:1.4}
.sub{margin-top:5px;color:#667787;font-size:14px;line-height:1.7}
.controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:12px}
.select{min-width:280px;max-width:100%;height:42px;padding:0 12px;border:1px solid #cbd7e1;border-radius:8px;background:#fff;color:#263445;font-size:14px}
.button{min-height:42px;padding:0 18px;border:0;border-radius:8px;background:#166ec8;color:#fff;font-size:14px;font-weight:700;cursor:pointer}
.button.secondary{background:#eef4f8;color:#2d5877;border:1px solid #d6e1e9}
.button:focus-visible,.select:focus-visible{outline:3px solid #78baff;outline-offset:2px}
.status{max-width:980px;margin:10px auto 0;padding:0 22px;color:#24704a;font-size:14px;line-height:1.6}
.hint{max-width:980px;margin:12px auto 0;padding:12px 15px;border:1px solid #ead9b7;border-radius:8px;background:#fff9e9;color:#6b5638;font-size:13px;line-height:1.7}
.preview-shell{max-width:780px;margin:22px auto 48px;padding:10px;background:#dce5ed;border-radius:10px;box-shadow:0 10px 30px rgba(18,45,68,.12)}
iframe{display:block;width:100%;height:calc(100vh - 250px);min-height:700px;border:0;background:#fff;border-radius:4px}
@media(max-width:700px){.top{position:static;padding:14px}.select{width:100%;min-width:0}.button{flex:1}.status,.hint{margin-left:12px;margin-right:12px;padding-left:12px;padding-right:12px}.preview-shell{margin:14px 8px 30px;padding:5px}iframe{height:78vh;min-height:620px}}
</style></head><body>
<header class="top"><div class="wrap">
  <div class="title">公众号文章预览 · 复制到 135</div>
  <div class="sub">选择篇目/品牌版本，在手机宽度预览；点击复制后粘贴到 135 编辑区，再使用 135 的“复制使用”粘到公众号。</div>
  <div class="controls">
    <label class="select-label" for="pick">当前版本</label>
    <select id="pick" class="select" aria-label="选择文章版本"></select>
    <button class="button" id="copy" type="button">复制当前篇目</button>
    <button class="button secondary" id="open135" type="button">打开 135 编辑器</button>
  </div>
</div></header>
<div id="status" class="status" role="status" aria-live="polite">请选择文章版本。</div>
<div class="hint"><b>复制流程：</b>选择版本 → 复制当前篇目 → 粘贴到 135 编辑区（不要粘在源码模式）→ 检查排版后点 135“复制使用” → 粘到公众号编辑器。<br><b>发布前检查：</b>预览页不会替你上传图片；外链/本地图片在 135 和公众号中能否显示，需实际检查。复制未成功时会显示明确提示。</div>
<main class="preview-shell"><iframe id="preview" title="公众号文章预览" sandbox="allow-same-origin" referrerpolicy="no-referrer"></iframe></main>
<script>
'use strict';
const docs = $docs_json;
const editorUrl = $editor_url;
const select = document.getElementById('pick');
const frame = document.getElementById('preview');
const status = document.getElementById('status');
const copyButton = document.getElementById('copy');

docs.forEach((doc, index) => {
  const option = document.createElement('option');
  option.value = String(index);
  option.textContent = doc.title;
  select.appendChild(option);
});

function escapeAttribute(value) {
  return String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
function safeUrlAttribute(name, rawValue) {
  if (/[\u0000-\u001f\u007f]/.test(rawValue) || name === 'action' ||
      name === 'formaction' || name === 'ping') return false;
  const value = rawValue.trim();
  if (!value) return true;
  if (value.includes('\\')) return false;
  const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(value);
  if (!scheme) return true; // 相对路径、片段与协议相对URL
  const protocol = scheme[1].toLowerCase();
  if (name === 'href' && ['http', 'https', 'mailto', 'tel'].includes(protocol)) return true;
  if ((name === 'src' || name === 'xlink:href') && ['http', 'https'].includes(protocol)) return true;
  // 富文本会离开 sandbox；只允许惰性的栅格 data:image，禁止 data:text/html/SVG。
  if (name === 'src' && protocol === 'data' &&
      /^data:image\/(?:png|jpe?g|gif|webp|avif|bmp);base64,/i.test(value)) return true;
  return false;
}
function safeStyleAttribute(rawValue) {
  const value = String(rawValue);
  // Reject CSS escapes/comments and active/resource-loading constructs before
  // any style is copied; these can disguise tokens from a textual URL check.
  if (/[\\@]/.test(value) || /\/\*|\*\//.test(value) ||
      /url\s*\(|expression\s*\(|\bprogid\s*:/i.test(value) ||
      /\b(?:-webkit-)?(?:image-set|image|cross-fade|element|paint)\s*\(/i.test(value) ||
       /(?:^|;)\s*(?:behavior|-moz-binding)\s*:/i.test(value) ||
      /(?:^|;)\s*position\s*:\s*fixed\b/i.test(value)) return false;
  return true;
}
function sanitizeMarkup(markup) {
  const parsed = new DOMParser().parseFromString(String(markup), 'text/html');
  // Remove across the parsed document: HTMLParser may relocate these nodes to head.
  parsed.querySelectorAll('script,iframe,object,embed,applet,form,style,link,base,meta,template,video,audio,source,track')
    .forEach((node) => node.remove());
  parsed.querySelectorAll('*').forEach((node) => {
    // Clipboard HTML leaves the sandbox; remove every non-HTML namespace so SVG
    // SMIL href animation and MathML cannot revive a javascript: URL on paste.
    if (node.namespaceURI !== 'http://www.w3.org/1999/xhtml') {
      node.remove();
      return;
    }
    Array.from(node.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase();
      const urlAttribute = ['href', 'src', 'srcset', 'xlink:href', 'action', 'formaction', 'ping'].includes(name);
      if (name.startsWith('on') || name === 'srcdoc' ||
          (name === 'style' && !safeStyleAttribute(attr.value)) ||
          (urlAttribute && (name === 'srcset' || !safeUrlAttribute(name, attr.value)))) {
        node.removeAttribute(attr.name);
      }
    });
  });
  return parsed.body.innerHTML;
}
function previewDocument(doc) {
  const base = doc.base ? '<base href="' + escapeAttribute(doc.base) + '">' : '';
  return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' + base +
    '<style>html,body{margin:0;background:#fff}body{overflow-x:hidden}</style>' +
    '</head><body>' + sanitizeMarkup(doc.html) + '</body></html>';
}
function show() {
  const doc = docs[Number(select.value) || 0];
  if (!doc) return;
  frame.srcdoc = previewDocument(doc);
  status.textContent = '预览中：' + doc.title;
}
function plainText(markup) {
  const parsed = new DOMParser().parseFromString(markup, 'text/html');
  return parsed.body.innerText || parsed.body.textContent || '';
}
function fallbackCopy(markup) {
  const box = document.createElement('div');
  box.contentEditable = 'true';
  box.setAttribute('aria-hidden', 'true');
  box.style.cssText = 'position:fixed;left:-10000px;top:0;width:677px;max-height:1px;overflow:hidden;';
  box.innerHTML = markup;
  document.body.appendChild(box);
  const range = document.createRange();
  range.selectNodeContents(box);
  const selection = window.getSelection();
  const previous = [];
  if (selection) {
    for (let i = 0; i < selection.rangeCount; i += 1) previous.push(selection.getRangeAt(i).cloneRange());
    selection.removeAllRanges();
    selection.addRange(range);
  }
  let copied = false;
  try { copied = document.execCommand('copy'); } finally {
    if (selection) {
      selection.removeAllRanges();
      previous.forEach((saved) => selection.addRange(saved));
    }
    box.remove();
  }
  if (!copied) throw new Error('浏览器拒绝剪贴板访问；请刷新页面或在浏览器中打开本地文件。');
}
async function copyCurrent() {
  const doc = docs[Number(select.value) || 0];
  if (!doc) return;
  const safeHtml = sanitizeMarkup(doc.html);
  const text = plainText(safeHtml);
  try {
    if (!navigator.clipboard || !window.ClipboardItem || !window.isSecureContext) {
      throw new Error('Rich Clipboard API unavailable');
    }
    await navigator.clipboard.write([new ClipboardItem({
      'text/html': new Blob([safeHtml], {type: 'text/html'}),
      'text/plain': new Blob([text], {type: 'text/plain'})
    })]);
    status.textContent = '已复制 HTML 与纯文本：' + doc.title + '。现在可粘贴到 135 编辑区。';
  } catch (_) {
    try {
      fallbackCopy(safeHtml);
      status.textContent = '已用兼容方式复制：' + doc.title + '。现在可粘贴到 135 编辑区。';
    } catch (error) {
      status.textContent = '复制失败：' + String(error && error.message || error);
    }
  }
}
select.addEventListener('change', show);
copyButton.addEventListener('click', copyCurrent);
document.getElementById('open135').addEventListener('click', () => window.open(editorUrl, '_blank', 'noopener,noreferrer'));
show();
</script></body></html>
''')


def _script_json(value: object) -> str:
    """Serialize data safely into an inline script element."""
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", "\\u0026")
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def render_page(documents: list[dict], page_title: str = "公众号文章预览与复制") -> str:
    if not documents:
        raise ValueError("至少需要一篇 HTML 文章")
    if len(documents) > MAX_DOCS:
        raise ValueError(f"最多支持 {MAX_DOCS} 个文章版本")
    clean_docs: list[dict[str, str]] = []
    total = 0
    for item in documents:
        title = str(item.get("title", "")).strip()
        markup = item.get("html", "")
        base = str(item.get("base", ""))
        if not title or not isinstance(markup, str) or not markup.strip():
            raise ValueError("每个版本都需要非空 title 和 html")
        total += len(markup.encode("utf-8"))
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f"文章总大小超过 {MAX_TOTAL_BYTES // (1024 * 1024)} MiB 限制")
        clean_docs.append({"title": title, "html": markup, "base": base})
    return PAGE_TEMPLATE.substitute(
        page_title=html.escape(page_title, quote=False),
        docs_json=_script_json(clean_docs),
        editor_url=json.dumps(EDITOR_URL))


def write_preview_copy_page(documents: list[dict], output_path: str | Path,
                           page_title: str = "公众号文章预览与复制") -> dict:
    output = Path(os.path.abspath(os.fspath(Path(output_path).expanduser())))
    output.parent.mkdir(parents=True, exist_ok=True)
    page = render_page(documents, page_title)
    fd, temp_name = tempfile.mkstemp(prefix=".artboard-preview-", suffix=".tmp",
                                     dir=str(output.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            fd = -1  # fdopen now owns the descriptor
            stream.write(page)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, output)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
    return {"ok": True, "output": str(output), "documents": len(documents),
            "bytes": output.stat().st_size}


def _read_doc_spec(spec: str) -> dict[str, str]:
    if "=" not in spec:
        raise ValueError(f"--doc 格式为 标题=HTML路径：{spec}")
    title, raw_path = spec.split("=", 1)
    path = Path(raw_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"文章 HTML 不存在：{path}")
    markup = path.read_text(encoding="utf-8")
    return {"title": title.strip() or path.stem, "html": markup,
            "base": path.parent.as_uri() + "/"}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成公众号正文预览与富文本复制页（非编辑器克隆）")
    parser.add_argument("html", nargs="?", help="单篇文章 HTML 片段")
    parser.add_argument("--doc", action="append", default=[], metavar="标题=路径",
                        help="添加一个文章/品牌版本；可重复，用于切换预览")
    parser.add_argument("--label", default="", help="单篇文章的下拉名称(默认文件名)")
    parser.add_argument("--out", type=Path, default=None, help="输出独立预览复制页")
    parser.add_argument("--page-title", default="公众号文章预览与复制", help="页面标题")
    args = parser.parse_args()
    try:
        documents = [_read_doc_spec(spec) for spec in args.doc]
        if args.html:
            path = Path(args.html).expanduser().resolve()
            if not path.is_file():
                raise FileNotFoundError(f"文章 HTML 不存在：{path}")
            documents.insert(0, {"title": args.label or path.stem,
                                 "html": path.read_text(encoding="utf-8"),
                                 "base": path.parent.as_uri() + "/"})
        if not documents:
            raise ValueError("提供 <html> 或至少一个 --doc 标题=路径")
        output = args.out
        if output is None:
            if not args.html:
                raise ValueError("多篇文章时必须指定 --out")
            output = Path(args.html).expanduser().with_suffix(".preview-copy.html")
        print(json.dumps(write_preview_copy_page(documents, output, args.page_title),
                         ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
