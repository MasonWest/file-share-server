#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import socket
import sys

import uvicorn
from dotenv import load_dotenv

from filesvc_api import ADMIN_HOST
from filesvc_api import ADMIN_PORT
from filesvc_api import PUBLIC_HOST
from filesvc_api import PUBLIC_PORT
from filesvc_api import SHARE_DIR


def build_server(app_path: str, host: str, port: int) -> uvicorn.Server:
    config = uvicorn.Config(
        app_path,
        host=host,
        port=port,
        reload=False,
        log_level="info",
        workers=1,
    )
    return uvicorn.Server(config)


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def local_addresses() -> list[str]:
    """列出本机能被内网其他设备访问到的 IPv4 地址。

    管理端绑 0.0.0.0 时，用户需要知道手机该输哪个 IP——让他去 ipconfig 里
    找一堆虚拟网卡地址是没必要的折磨。
    """
    addresses: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            addr = info[4][0]
            if addr not in addresses and not addr.startswith("127."):
                addresses.append(addr)
    except OSError:
        pass

    # 兜底：用一个不会真正发包的 UDP connect 拿到默认出口网卡地址
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            primary = sock.getsockname()[0]
            if primary not in addresses and not primary.startswith("127."):
                addresses.insert(0, primary)
    except OSError:
        pass

    return addresses


async def run_servers():
    admin_server = build_server("filesvc_api:app_internal", ADMIN_HOST, ADMIN_PORT)
    public_server = build_server("filesvc_api:app_public", PUBLIC_HOST, PUBLIC_PORT)

    admin_server.install_signal_handlers = lambda: None
    public_server.install_signal_handlers = lambda: None

    print("=" * 50)
    print("File Share Server")
    print("=" * 50)
    print(f"Share directory: {SHARE_DIR}")
    print(f"Internal admin: http://{ADMIN_HOST}:{ADMIN_PORT}")
    print(f"Public download: http://{PUBLIC_HOST}:{PUBLIC_PORT}")
    print("-" * 50)
    print("Ports:")
    print(f"[{ADMIN_PORT}] admin interface with token auth")
    print(f"[{PUBLIC_PORT}] public download only")
    print("-" * 50)

    lan = local_addresses()
    if lan:
        print("内网可用地址（手机 / 平板 / VR 用这些）:")
        for addr in lan:
            print(f"  http://{addr}:{ADMIN_PORT}")
    else:
        print(f"未探测到内网地址，请手动访问 http://<本机内网IP>:{ADMIN_PORT}")

    print("-" * 50)
    print("安全提醒:")
    print(f"  路由器只映射 {PUBLIC_PORT}/公网映射端口，不要映射 {ADMIN_PORT}")
    print("  管理端首次登录后会自动记住该设备，之后无需再输口令")
    print("  关闭服务：双击 stop_server.bat（或 Ctrl+C）")
    print("=" * 50)

    await asyncio.gather(
        admin_server.serve(),
        public_server.serve(),
    )


if __name__ == "__main__":
    load_dotenv()

    if not is_port_available(ADMIN_HOST, ADMIN_PORT):
        print(f"[ERROR] Port {ADMIN_HOST}:{ADMIN_PORT} is already in use.")
        sys.exit(1)

    if not is_port_available(PUBLIC_HOST, PUBLIC_PORT):
        print(f"[ERROR] Port {PUBLIC_HOST}:{PUBLIC_PORT} is already in use.")
        sys.exit(1)

    asyncio.run(run_servers())
