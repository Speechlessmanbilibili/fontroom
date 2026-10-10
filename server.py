#!/usr/bin/env python3
"""局域网字体服务器：提供 iOS 描述文件与安装说明页。

- 静态页 + 已生成描述文件（profiles/）
- GET /fonts.json：可用字体列表（供页面勾选）
- POST /api/profile：按勾选的字体动态生成描述文件（二进制 plist）
- .mobileconfig 用 application/x-apple-aspen-config 内容类型（Safari 识别）
- 不做 gzip 压缩：Safari 下载描述文件交给 iOS 安装器时可能不解压，
  压缩传输会导致安装器拿到二进制乱码而报「包含无效字体」
"""
import http.server
import json
import os
import socketserver
import urllib.parse
from datetime import datetime
from pathlib import Path

from generate_profile import (
    DEFAULT_FONT_DIRS,
    discover_fonts,
    display_name,
    make_profile,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("FONT_SERVER_PORT", "8765"))
# 默认端口绑不上时依次尝试的候选。避开 Windows 常见的保留区间
# （8000-8199、8201-8300、8561-9461 等在 Hyper-V/WSL 开启后常被占）。
DEFAULT_PORT_CANDIDATES = [8765, 8788, 9000, 9700, 12345]


def get_server_font_dirs() -> list[Path]:
    """汇总服务器可供动态打包与勾选的字体来源目录。"""
    return list(DEFAULT_FONT_DIRS)


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mobileconfig": "application/x-apple-aspen-config",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/fonts.json":
            self._send_json(self._font_list())
            return
        if parsed.path == "/profiles.json":
            self._send_json(self._profile_list())
            return
        if parsed.path == "/status.json":
            self._send_json(self._status())
            return
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/profile":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            req = json.loads(body.decode("utf-8", errors="replace") or "{}")
        except json.JSONDecodeError:
            self.send_error(400, "bad json")
            return
        selected = req.get("fonts") or []
        by_name = {p.name: p for p in discover_fonts(get_server_font_dirs())}
        missing = [n for n in selected if n not in by_name]
        if missing:
            self.send_error(400, f"未知字体: {missing}")
            return
        fonts = [by_name[n] for n in selected if n in by_name]
        if not fonts:
            self.send_error(400, "未选择字体")
            return
        desc = req.get("name") or f"{len(fonts)} 个字体"
        data = make_profile("custom", fonts, desc)
        self.send_response(200)
        self.send_header("Content-Type", "application/x-apple-aspen-config")
        self.send_header("Content-Disposition", 'attachment; filename="fonts.mobileconfig"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _font_list(self):
        return [
            {"name": p.name, "display": display_name(p), "size": p.stat().st_size}
            for p in discover_fonts(get_server_font_dirs())
        ]

    def _profile_list(self):
        """列出预生成的描述文件（profiles/ 下的 .mobileconfig）。"""
        profiles_dir = os.path.join(ROOT, "profiles")
        out = []
        if os.path.isdir(profiles_dir):
            for name in sorted(os.listdir(profiles_dir)):
                if not name.endswith(".mobileconfig"):
                    continue
                path = os.path.join(profiles_dir, name)
                out.append({"name": name, "size": os.path.getsize(path)})
        return out

    def _status(self):
        """返回页面与预生成描述文件中最新的实际修改时间。"""
        paths = [os.path.join(ROOT, "index.html")]
        profiles_dir = os.path.join(ROOT, "profiles")
        if os.path.isdir(profiles_dir):
            paths.extend(
                os.path.join(profiles_dir, name)
                for name in os.listdir(profiles_dir)
                if name.endswith(".mobileconfig")
            )
        modified = max(os.path.getmtime(path) for path in paths if os.path.isfile(path))
        return {
            "modified": datetime.fromtimestamp(modified).astimezone().isoformat(
                timespec="seconds"
            )
        }

    def _send_json(self, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}", flush=True)


class ThreadingServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def local_ips() -> list:
    import socket
    ips = set()
    try:
        hostname = socket.gethostname()
        ips.update(socket.gethostbyname_ex(hostname)[2])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(ips)


if __name__ == "__main__":
    # PORT 优先用环境变量；没配就按 DEFAULT_PORT_CANDIDATES 顺序试。
    # 这样用户在 Windows 上直接 `python server.py` 也能起来：
    # 系统的 Hyper-V/WSL 预留区间会占掉 8000-8199、8761-8860 等大段端口，
    # 绑定时会抛 WinError 10013（访问权限不允许），不能只试一个端口。
    candidates = [PORT] if os.environ.get("FONT_SERVER_PORT") else DEFAULT_PORT_CANDIDATES
    httpd = None
    port = None
    for cand in candidates:
        try:
            httpd = ThreadingServer(("0.0.0.0", cand), Handler)
            port = cand
            if cand != candidates[0]:
                print(f"端口 {candidates[0]} 不可用（可能被系统保留或占用），已改用 {cand}")
            break
        except OSError as exc:
            print(f"端口 {cand} 绑定失败：{exc}")

    if httpd is None:
        raise SystemExit(
            "所有候选端口都无法绑定。可用 FONT_SERVER_PORT=<端口> 指定一个未被占用的端口。"
        )

    with httpd:
        print(f"字体服务器已启动（局域网可访问）: http://0.0.0.0:{port}")
        for ip in local_ips():
            print(f"  ->  http://{ip}:{port}/")
        print("在 iPhone Safari 中打开上面的地址，点按「下载并安装」。", flush=True)
        httpd.serve_forever()
