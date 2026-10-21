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
import shutil
import socket
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
    """汇总预设家族和自备字体的来源目录。"""
    dirs = list(DEFAULT_FONT_DIRS)
    sources = [
        ("CRIMSON_PRO_FONT_DIR", "CrimsonPro"),
        ("SOURCE_SERIF_FONT_DIR", "SourceSerif4"),
        ("SOURCE_HAN_SERIF_FONT_DIR", "SourceHanSerif"),
        ("SOURCE_SANS_FONT_DIR", "SourceSans3"),
        ("SOURCE_HAN_SANS_FONT_DIR", "SourceHanSans"),
        ("CHARIS_FONT_DIR", "Charis"),
    ]
    for variable, folder in sources:
        path = Path(os.environ.get(variable, os.path.join(ROOT, "fonts", folder)))
        if path.is_dir():
            dirs.append(path)
    custom = os.environ.get("FONT_DIR")
    if custom:
        dirs.append(Path(custom))
    path = Path(os.environ.get("FOUNDER_FONT_DIR", os.path.join(ROOT, "fonts", "founder")))
    if path.is_dir():
        dirs.append(path / "Font" if (path / "Font").is_dir() else path)
    return dirs


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".mobileconfig": "application/x-apple-aspen-config",
    }

    # 发送缓冲区。默认值在局域网上偏小，大文件传输时容易喂不满带宽。
    SEND_BUFFER = 1 << 20          # 1 MB
    COPY_CHUNK = 1 << 18           # 256 KB

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def setup(self):
        super().setup()
        try:
            # 关掉 Nagle，避免小包攒批导致 iOS 端等数据
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF,
                                       self.SEND_BUFFER)
        except OSError:
            pass

    def copyfile(self, source, outputfile):
        """用更大的块搬运文件，减少 sendall 调用次数。"""
        try:
            shutil.copyfileobj(source, outputfile, self.COPY_CHUNK)
        except OSError:
            # 客户端中途断开时会走到这里。Windows 上是 ConnectionAborted
            # (10053)、Linux 上是 ConnectionReset (10054) 或 BrokenPipe，
            # 三者都是 OSError 子类。这不是服务端故障，静默收场即可。
            pass

    def end_headers(self):
        # 告诉客户端可以续传。iOS 下载大文件时会先看这个头再决定要不要用 Range。
        if not any(header.lower().startswith(b"accept-ranges:") for header in getattr(self, "_headers_buffer", [])):
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def parse_range(self, size):
        """解析 Range 头，返回 (start, end) 或 None。

        Python 3.13 的 SimpleHTTPRequestHandler 不支持 Range，
        而 iOS 下载大文件时会用续传来从中断处接着下。
        """
        hdr = self.headers.get("Range")
        if not hdr or not hdr.startswith("bytes="):
            return None
        spec = hdr[len("bytes="):].split(",")[0].strip()
        if "-" not in spec:
            return None
        a, b = spec.split("-", 1)
        try:
            if a == "":
                # bytes=-N 表示最后 N 字节
                n = int(b)
                if n <= 0:
                    return None
                start = max(0, size - n)
                end = size - 1
            else:
                start = int(a)
                end = int(b) if b else size - 1
        except ValueError:
            return None
        end = min(end, size - 1)
        if start < 0 or start > end or start >= size:
            return None
        return start, end

    def send_range(self, path):
        """按 Range 只发一段，返回 True 表示已处理。"""
        try:
            size = path.stat().st_size
        except OSError:
            return False
        rng = self.parse_range(size)
        if rng is None:
            return False
        start, end = rng
        length = end - start + 1
        ctype = self.extensions_map.get(path.suffix.lower(),
                                        "application/octet-stream")
        try:
            with open(path, "rb") as f:
                f.seek(start)
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
                self.send_header("Content-Length", str(length))
                self.end_headers()
                remain = length
                while remain > 0:
                    chunk = f.read(min(self.COPY_CHUNK, remain))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remain -= len(chunk)
        except OSError:
            pass
        return True

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
        # 文件请求：带 Range 头时自己处理，支持断点续传
        if self.headers.get("Range"):
            target = Path(self.translate_path(parsed.path))
            if target.is_file() and self.send_range(target):
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
        print(f"字房 / Fontroom 已启动（局域网可访问）: http://0.0.0.0:{port}")
        for ip in local_ips():
            print(f"  ->  http://{ip}:{port}/")
        print("在 iPhone Safari 中打开上面的地址，选择字体家族或自选字体。", flush=True)
        httpd.serve_forever()
