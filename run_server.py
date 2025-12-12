#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动文件共享服务器
"""

import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    # 加载环境变量
    load_dotenv()
    
    # 获取配置
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8800"))
    
    print("=" * 50)
    print("文件共享服务器")
    print("=" * 50)
    print(f"共享目录: {os.getenv('SHARE_DIR', 'shared')}")
    print(f"服务器地址: {host}:{port}")
    print(f"访问地址: http://localhost:{port}")
    print(f"局域网访问: http://[你的IP地址]:{port}")
    print("-" * 50)
    print("功能特性:")
    print("✓ 文件上传下载")
    print("✓ 文件夹浏览")
    print("✓ 文件排序（名称/大小/日期）")
    print("✓ 路径导航")
    print("✓ 中文界面")
    print("-" * 50)
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    uvicorn.run(
        "filesvc_api:app",
        host=host,
        port=port,
        reload=True
    )