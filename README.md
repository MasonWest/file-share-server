# 局域网和公网分离文件共享服务

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.124.2-green)
![Vue.js](https://img.shields.io/badge/Vue.js-3-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

这是一个最小改造的文件共享服务，将管理权限与公共下载彻底分离：

- **管理端 (默认 8800)**：提供完整的管理功能，受 Token 保护，建议仅限内网/本机访问。
- **公共下载端 (默认 9900)**：**极简暴露**，仅提供 `/s/{token}` 下载接口，无任何管理权限，适合直接映射到公网。

## 功能特性

- **双重隔离**：物理端口隔离管理流与下载流。
- **文件管理**：浏览目录、子目录、文件上传、下载、删除（需权限）。
- **实时搜索**：当前目录内快速过滤。
- **临时分享**：一键生成带 Token 的临时下载链接。
- **🔥 增强统计**：
  - **实时日志**：控制台实时打印下载动作（包含 IP、文件、Token）。
  - **次数统计**：记录每个分享链接的累计下载次数。
  - **下载轨迹**：内存保留最近 10 次下载的详细 IP 和时间戳。
- **路径安全**：严格校验 `..` 穿越和绝对路径，禁止越界访问。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 环境配置

复制 `.env.example` 为 `.env`，并按需修改：

```env
# 基础配置
SHARE_DIR=D:\SharedFiles
ADMIN_TOKEN=your_secure_password_here

# 网络配置
PUBLIC_BASE_URL=http://example.com:9900  # 必须包含协议头和端口，例如：http://your-domain.com:9900
ALLOW_OVERWRITE=false

# 链接配置
TOKEN_EXPIRE_HOURS=24  # 分享链接默认有效期（小时）
```

### 3. 启动服务

Windows 环境：
```bat
start_server.bat
```

通用方式：
```bash
python run_server.py
```

## 访问说明

### 管理界面 (Admin)
- **地址**：默认 `http://127.0.0.1:8800`
- **认证**：首次进入需输入 `.env` 中配置的 `ADMIN_TOKEN`。
- **统计查看**：后端提供 `/api/shares` 接口供管理员查看当前所有活跃链接及其下载统计。

### 下载服务 (Public)
- **地址**：默认 `http://0.0.0.0:9900`
- **权限**：仅允许 `/s/{token}`。任何试图访问根目录、管理 API 或非法路径的行为均返回 `403 Forbidden`。

## 分享链接机制

- **生成**：管理端点击“分享链接”生成。
- **地址格式**：`{PUBLIC_BASE_URL}/s/{token}`
- **有效期**：由 `TOKEN_EXPIRE_HOURS` 控制，默认 24 小时。
- **持久性**：Token 存储在内存中，**服务重启后会失效**。

## 安全与约束

1. **零越界**：所有操作限制在 `SHARE_DIR` 及其子目录下。
2. **防爆破**：管理 Token 错误多次后会触发 IP 临时锁定（24小时）。
3. **公网友好**：9900 端口即使映射到公网，攻击者也无法通过该端口探测文件列表或上传文件。

## 项目结构

```text
fastAPI/
├── filesvc_api.py   # 核心逻辑（Admin/Public 应用定义）
├── index.html       # 单页管理端 UI
├── run_server.py    # 双端口启动入口
├── start_server.bat # Windows 快捷启动
├── requirements.txt # 依赖列表
└── .env             # 敏感配置
```

## 许可证

MIT License
