# 局域网文件共享服务

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.124.2-green)
![Vue.js](https://img.shields.io/badge/Vue.js-3-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

一个简单直接的局域网文件共享工具，支持目录浏览、文件上传下载、当前目录搜索，以及临时分享链接。

## 功能

- 浏览共享目录及子目录
- 上传和下载文件
- 按名称、大小、修改时间排序
- 当前目录内搜索文件和文件夹
- 一键生成临时分享链接并复制到剪贴板
- 路径安全校验，限制访问范围在 `SHARE_DIR` 内

## 运行要求

- Python 3.7+
- Windows 推荐直接使用 `start_server.bat`

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置共享目录

复制 `.env.example` 为 `.env`，然后修改：

```env
SHARE_DIR=D:\SharedFiles
PORT=8800
HOST=0.0.0.0
ALLOW_OVERWRITE=false
```

### 3. 启动服务

Windows：

```bat
start_server.bat
```

或直接：

```bash
python run_server.py
```

### 4. 访问

- 本机访问：`http://localhost:8800`
- 局域网访问：`http://你的IP:8800`

## 配置项

`.env` 支持以下参数：

```env
SHARE_DIR=shared
PORT=8800
HOST=0.0.0.0
ALLOW_OVERWRITE=false
```

说明：

- `SHARE_DIR`：共享目录根路径
- `PORT`：监听端口，默认 `8800`
- `HOST`：监听地址，默认 `0.0.0.0`
- `ALLOW_OVERWRITE`：是否允许上传覆盖同名文件，默认 `false`

## 临时分享链接

文件列表中的“分享链接”按钮会调用后端生成一个临时下载地址。

当前实现：

- token 为 32 位随机字符串
- 默认有效期 1 小时
- token 映射保存在内存中
- 服务重启后，已生成的分享链接会失效
- 链接访问路径为 `/s/{token}`

## 安全限制

为了避免越权访问，后端做了这些限制：

- 所有文件操作都必须落在 `SHARE_DIR` 下
- 禁止绝对路径
- 禁止使用 `..` 做路径穿越
- 目标文件不存在时返回 `404`
- 分享 token 不存在或已过期时返回 `404`

## 搜索说明

当前搜索只过滤“当前目录已经列出来的内容”，不会递归搜索子目录。

这样做的原因是：

- 当前实现更快
- 前端开销小
- 共享目录文件很多时不会明显拖慢页面响应

如果后续确实要做递归搜索，建议放到后端实现，并增加结果数量限制。

## 项目结构

```text
fastAPI/
├── filesvc_api.py       # FastAPI 后端
├── index.html           # 前端页面
├── run_server.py        # Python 启动入口
├── start_server.bat     # Windows 启动脚本
├── requirements.txt     # 依赖列表
├── .env.example         # 配置示例
├── README.md            # 项目说明
├── github发布指南.md    # GitHub 发布说明
└── 发布检查清单.txt      # 发布前检查清单
```

## 常见问题

### 1. 无法访问页面

- 检查端口是否被占用
- 检查防火墙是否放行对应端口
- 检查 `.env` 中的 `HOST` 和 `PORT`

### 2. 上传失败

- 检查 `SHARE_DIR` 是否可写
- 检查磁盘空间是否足够
- 检查 `ALLOW_OVERWRITE` 是否允许覆盖

### 3. 分享链接失效

- token 已过期
- 服务已重启
- 原文件已被删除或移动

## GitHub

如果你准备把这个项目发到 GitHub，参考 [github发布指南.md](github发布指南.md)。

## 许可证

MIT License，见 [LICENSE](LICENSE)。
