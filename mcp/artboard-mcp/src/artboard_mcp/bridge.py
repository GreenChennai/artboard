"""浏览器素材 Bridge · 本地服务端(MV3 扩展的对端)。

架构(ADR-AB-E04):扩展 --WS--> 本服务(仅 127.0.0.1) <--WS-- MCP(server.py)。
安全纪律(逐条对应 mcp-assets.md §安全):
  只听 127.0.0.1 / 一次性会话 token(过期作废)/ 域名白名单在扩展侧执行 /
  不落 cookie 明文 / 不上传外部 / 默认不启动(mcp_enabled=false)。

协议(一帧一条 JSON):
  双方 → {type:"hello", token, role:"extension"|"client"}   握手(必须第一条)→ {type:"ready"}
  client → {type:"collect", url?, scroll, limit, pages}     服务转发给扩展
  extension → {type:"items", items:[{url,thumb,w,h,link}]}  服务转发给发起方
  client → {type:"download", urls:[...]}                    服务转发给扩展
  extension → {type:"downloaded", results:[...]}            服务转发给发起方

WebSocket 为纯标准库实现(RFC6455 最小集:握手 + 文本帧 + close/ping;
服务端出帧不掩码,客户端出帧必须掩码)。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
import struct
import sys
import threading
import time

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def _accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()


# ---------------- 帧编解码(收发两端共用) ----------------

def _recv_exact(sock: socket.socket, n: int, timeout: float) -> bytes | None:
    sock.settimeout(timeout)
    out = b""
    while len(out) < n:
        try:
            chunk = sock.recv(n - len(out))
        except (socket.timeout, OSError):
            return None
        if not chunk:
            return None
        out += chunk
    return out


def _recv_text(sock: socket.socket, timeout: float, masked: bool) -> str | None:
    """收一条文本帧。masked:对端是否必须掩码(True=我方是服务端)。"""
    hdr = _recv_exact(sock, 2, timeout)
    if hdr is None:
        return None
    opcode, mask_flag, ln = hdr[0] & 0x0F, hdr[1] & 0x80, hdr[1] & 0x7F
    if ln == 126:
        ext = _recv_exact(sock, 2, timeout)
        if ext is None:
            return None
        ln = struct.unpack(">H", ext)[0]
    elif ln == 127:
        ext = _recv_exact(sock, 8, timeout)
        if ext is None:
            return None
        ln = struct.unpack(">Q", ext)[0]
    mask = _recv_exact(sock, 4, timeout) if mask_flag else None
    payload = _recv_exact(sock, ln, timeout) if ln else b""
    if payload is None:
        return None
    if mask:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    if opcode == 8:  # close
        return None
    if opcode == 9:  # ping → pong(不掩码回)
        _send_frame(sock, 0x0A, payload)
        return None
    if opcode == 1 and bool(mask_flag) == bool(mask):
        return payload.decode("utf-8", "replace")
    return None


def _send_frame(sock: socket.socket, opcode: int, payload: bytes, mask: bool = False) -> None:
    head = bytes([0x80 | opcode])
    ln = len(payload)
    if ln < 126:
        head += bytes([(0x80 if mask else 0) | ln])
    elif ln < 65536:
        head += bytes([(0x80 if mask else 0) | 126]) + struct.pack(">H", ln)
    else:
        head += bytes([(0x80 if mask else 0) | 127]) + struct.pack(">Q", ln)
    if mask:
        mk = secrets.token_bytes(4)
        sock.sendall(head + mk + bytes(b ^ mk[i % 4] for i, b in enumerate(payload)))
    else:
        sock.sendall(head + payload)


class BridgeHub:
    """本地服务:127.0.0.1 监听;hello 按 role 分流;collect/download 双向转发。"""

    def __init__(self, port: int = 0, token_ttl: int = 900, token: str | None = None):
        # token 可固定(狩猎 hub 绑定常态化:专用浏览器凭据永久有效,ADR D9);
        # 固定 token 时 ttl 视为无限(过期检查跳过)
        self.token = token or secrets.token_urlsafe(24)
        self.token_ttl = token_ttl
        self.expires = time.time() + (10 ** 12 if token else token_ttl)  # 固定 token = 长效
        self.ext: socket.socket | None = None        # 扩展连接
        self.pending: list[socket.socket] = []       # 等 items 的 client 连接(FIFO)
        self._lock = threading.Lock()
        self._srv = self._serve(port)
        threading.Thread(target=self._keepalive, daemon=True).start()

    def _keepalive(self) -> None:
        """对扩展连接 25s 一 ping:探测死链并产生 WS 活动辅证(MV3 SW 闲置会被杀)。"""
        while True:
            time.sleep(25)
            with self._lock:
                ext = self.ext
            if ext is None:
                continue
            try:
                _send_frame(ext, 0x09, b"ka")  # WS ping(浏览器协议层自动 pong)
            except OSError:
                with self._lock:
                    self.ext = None

    def _serve(self, port: int) -> socket.socket:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(4)
        threading.Thread(target=self._accept_loop, args=(srv,), daemon=True).start()
        return srv

    @property
    def port(self) -> int:
        return self._srv.getsockname()[1]

    def _accept_loop(self, srv: socket.socket) -> None:
        while True:
            try:
                sock, _ = srv.accept()
                if not self._handshake(sock):
                    sock.close()
                    continue
                first = _recv_text(sock, 15, masked=True)
                try:
                    hello = json.loads(first or "{}")
                except ValueError:
                    hello = {}
                ok = (hello.get("type") == "hello"
                      and secrets.compare_digest(hello.get("token", ""), self.token)
                      and time.time() <= self.expires)
                if not ok:
                    _send_frame(sock, 0x01, json.dumps({"type": "bye", "error": "AUTH"}).encode())
                    sock.close()
                    continue
                _send_frame(sock, 0x01, json.dumps({"type": "ready"}).encode())
                # 每连接一线程:accept 循环不能被单个连接的泵阻塞
                threading.Thread(target=self._pump,
                                 args=(sock, hello.get("role") == "extension"),
                                 daemon=True).start()
            except Exception:  # noqa: BLE001 — 监听线程常驻
                time.sleep(0.2)

    def _handshake(self, sock: socket.socket) -> bool:
        data = b""
        sock.settimeout(10)
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                return False
            data += chunk
            if len(data) > 65536:
                return False
        key = ""
        for line in data.decode("latin1", "replace").split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()
        if not key:
            return False
        sock.sendall(("HTTP/1.1 101 Switching Protocols\r\n"
                      "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                      f"Sec-WebSocket-Accept: {_accept_key(key)}\r\n\r\n").encode())
        return True

    def _pump(self, sock: socket.socket, is_ext: bool) -> None:
        """常驻收帧:扩展的 items/downloaded 转给最早等待的 client;
        client 的 collect/download 转给扩展。断开清理会话/队列。"""
        if is_ext:
            with self._lock:
                self.ext = sock  # 一次性会话:新扩展连接顶替旧连接
        while True:
            raw = _recv_text(sock, 3600, masked=True)  # 对端(扩展/MCP)都是 RFC 客户端,必掩码
            if raw is None:
                break
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            with self._lock:
                if is_ext:
                    target = self.pending.pop(0) if self.pending else None
                else:
                    mtype = msg.get("type")
                    if mtype in ("collect", "download", "open", "close_tab", "cookie"):
                        if self.ext is not None:
                            self.pending.append(sock)  # 挂起等扩展回执(FIFO)
                            try:
                                _send_frame(self.ext, 0x01, raw.encode("utf-8"))
                            except OSError:
                                self.ext = None
                                if sock in self.pending:
                                    self.pending.remove(sock)
                        else:
                            _send_frame(sock, 0x01, json.dumps(
                                {"type": "items", "items": [],
                                 "error": "BRIDGE_NOT_CONNECTED"}).encode())
                        continue
                    target = None
                if target is not None:
                    try:
                        _send_frame(target, 0x01, raw.encode("utf-8"))
                    except OSError:
                        pass
        with self._lock:
            if self.ext is sock:
                self.ext = None
            if sock in self.pending:
                self.pending.remove(sock)

    def connected(self) -> bool:
        with self._lock:
            return self.ext is not None and time.time() <= self.expires


# ---------------- 会话文件(常驻服务 ↔ MCP 客户端的握手凭据) ----------------

_HUB: BridgeHub | None = None
_HUB_LOCK = threading.Lock()
SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), ".bridge-session.json")


def write_session() -> dict:
    """当前会话写 .bridge-session.json(MCP 据此连接;仅本机;token 一次性、随 TTL 过期)。"""
    if _HUB is None:
        return {}
    info = {"port": _HUB.port, "token": _HUB.token, "ttl": _HUB.token_ttl,
            "started": time.time(), "pid": os.getpid()}
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f)
    return info


def read_session() -> dict:
    """读会话文件;过期返回 {}。"""
    try:
        with open(SESSION_FILE, encoding="utf-8") as f:
            info = json.load(f)
    except Exception:  # noqa: BLE001
        return {}
    if time.time() - info.get("started", 0) > info.get("ttl", 900) + 5:
        return {}
    return info


# ---------------- WS 客户端(MCP → 常驻服务;出帧必须掩码) ----------------

class BridgeClient:
    def __init__(self, port: int, token: str):
        self.token = token
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=10)

    def handshake(self, role: str = "client") -> dict:
        key = base64.b64encode(secrets.token_bytes(16)).decode()
        self.sock.sendall((f"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                           f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)
            if not chunk:
                return {"type": "bye"}
            data += chunk
        head = data.split(b"\r\n\r\n", 1)[0].decode("latin1")
        if "101" not in head.split("\r\n", 1)[0]:
            return {"type": "bye"}
        _send_frame(self.sock, 0x01,
                    json.dumps({"type": "hello", "token": self.token, "role": role}).encode(),
                    mask=True)
        raw = _recv_text(self.sock, 10, masked=False)
        return json.loads(raw) if raw else {"type": "bye"}

    def call(self, payload: dict, timeout: float = 60) -> dict:
        _send_frame(self.sock, 0x01, json.dumps(payload).encode("utf-8"), mask=True)
        raw = _recv_text(self.sock, timeout, masked=False)
        return json.loads(raw) if raw else {"ok": False, "error": "BRIDGE_TIMEOUT"}

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def fetch_page(url: str = "", scroll: bool = True, limit: int = 50,
               pages: int = 1) -> dict:
    """MCP 入口:连常驻服务 → 转发 collect → 回传 items。服务未起给出可执行提示。"""
    info = read_session()
    if not info:
        return {"ok": False, "error": "BRIDGE_NOT_STARTED",
                "hint": "常驻服务未启动:python mcp/artboard-mcp/src/artboard_mcp/bridge.py"
                        " --serve,把输出的端口/token 填进 asset-bridge 扩展并连接"}
    try:
        cli = BridgeClient(info["port"], info["token"])
        ready = cli.handshake(role="client")
        if ready.get("type") != "ready":
            return {"ok": False, "error": "BRIDGE_AUTH",
                    "hint": "token 校验失败:服务可能已重启,重跑 bridge.py --serve 刷新会话"}
        out = cli.call({"type": "collect", "url": url, "scroll": scroll,
                        "limit": limit, "pages": min(pages, 5)})
        cli.close()
        out["port"] = info["port"]
        return out
    except OSError as exc:
        return {"ok": False, "error": "BRIDGE_UNREACHABLE",
                "hint": f"连不上常驻服务({exc});重跑 bridge.py --serve"}


SITE_URLS = {"huaban": "https://huaban.com/", "iconfont": "https://www.iconfont.cn/",
             "pinterest": "https://www.pinterest.com/"}


def fetch_cookie(site: str) -> dict:
    """Cookie 自动抓取(0927 迭代 D7):扩展 chrome.cookies → localhost 回传 → 调用方写 config。
    白名单在扩展侧强制;Cookie 只落本机,从不上传。"""
    url = SITE_URLS.get(site)
    if not url:
        return {"ok": False, "error": "UNKNOWN_SITE",
                "hint": f"可用站点:{sorted(SITE_URLS)}"}
    info = read_session()
    if not info:
        return {"ok": False, "error": "BRIDGE_NOT_STARTED", "hint": "先启动 bridge.py --serve"}
    try:
        cli = BridgeClient(info["port"], info["token"])
        ready = cli.handshake(role="client")
        if ready.get("type") != "ready":
            return {"ok": False, "error": "BRIDGE_AUTH", "hint": "token 校验失败"}
        out = cli.call({"type": "cookie", "url": url}, timeout=20)
        cli.close()
    except OSError as exc:
        return {"ok": False, "error": "BRIDGE_UNREACHABLE", "hint": str(exc)[:120]}
    if out.get("type") != "cookies":
        return {"ok": False, "error": out.get("error") or "NO_RESPONSE"}
    if not out.get("cookie"):
        return {"ok": False, "error": "NO_COOKIES",
                "hint": f"{url} 没采到 Cookie(先在该站登录并保持标签页)"}
    return {"ok": True, "site": site, "url": url, "count": out.get("count", 0),
            "cookie": out["cookie"]}


def get_hub(port: int = 0, token_ttl: int = 900, token: str | None = None) -> BridgeHub:
    """进程内单例(--serve 常驻模式用)。"""
    global _HUB
    with _HUB_LOCK:
        if _HUB is None:
            _HUB = BridgeHub(port=port, token_ttl=token_ttl, token=token)
        return _HUB


def main(argv=None) -> int:  # --serve 常驻:扩展与 MCP 都连这里
    import argparse
    ap = argparse.ArgumentParser(description="artboard 素材 Bridge 本地服务(仅 127.0.0.1)")
    ap.add_argument("--port", type=int, default=0, help="默认 0=随机端口")
    ap.add_argument("--token-ttl", type=int, default=900, dest="token_ttl")
    ap.add_argument("--token", default="", help="固定 token(绑定常态化;缺省随机)")
    ap.add_argument("--json", action="store_true", help="首行输出会话信息 JSON(供上层解析)")
    ap.add_argument("--serve", action="store_true", help="与默认行为相同(常驻服务;文档口径参数)")
    args = ap.parse_args(argv)
    hub = get_hub(args.port, args.token_ttl, args.token or None)
    info = write_session()
    print(json.dumps({"ok": True, "cmd": "bridge", "port": info["port"],
                      "token": info["token"], "ttl": info["ttl"],
                      "session_file": SESSION_FILE,
                      "hint": "把端口与 token 填进 asset-bridge 扩展 popup 点「连接本机会话」;"
                              "会话已写入 .bridge-session.json 供 MCP 连接;Ctrl+C 结束"},
                     ensure_ascii=False), flush=True)
    if not args.json:
        print("等待扩展连接…(Ctrl+C 结束)", file=sys.stderr)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
