# file-share-server

个人文件分享服务：把本机目录里的文件生成带 Token 的临时下载链接，同时把链接推送进 [`Vclip`](https://github.com/MasonWest/Vclip) 剪贴板，让手机、VR 头显等设备可以立刻拿到。

管理面和下载面跑在**两个不同端口**上，从物理层面隔离权限。

| 端口 | 默认值 | 暴露范围 | 能力 |
|---|---|---|---|
| 管理端 | `8800` | 仅内网/本机 | 文件浏览、上传、下载、生成分享链接、查看下载统计 |
| 公共端 | `9900` | 可映射公网 | 只有 `/s/{token}` 可以下载，其余一律 `403` |

公网只会看到一个「给链接就能下载，不给链接什么都不知道」的端口。文件列表、上传能力全部留在内网端口。

前端是单文件 `index.html`，用 Vue 3 的 CDN 全局构建，无打包步骤。

## 功能

- **双端口隔离**：管理流与下载流分离，9900 端口无任何管理接口
- **文件管理**：浏览目录、进入子目录、上传（1MB 分块写入并显示进度）、下载
- **临时分享**：生成一次性 Token 链接，可限制有效期和下载次数
- **下载统计**：累计下载次数 + 最近 10 次下载的 IP 与时间戳
- **实时日志**：控制台打印每次下载的 IP、Token、文件名
- **Vclip 联动**：分享链接生成后自动写入剪贴板（见下文）
- **路径安全**：绝对路径和 `..` 穿越一律拒绝，所有操作限制在 `SHARE_DIR` 内
- **防爆破**：管理 Token 连续错误 3 次，该 IP 锁定 24 小时

## 环境要求

- **Python 3.10 或以上**。代码用到了 `int | None` 联合类型语法，3.9 及以下会直接语法报错。
- 无需数据库。分享 Token 和登录状态都存在内存里。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
# 编辑 .env：至少改 SHARE_DIR、ADMIN_TOKEN、PUBLIC_BASE_URL、VCLIP_ACCESS_PASSWORD

# 3. 启动
python run_server.py
```

Windows 也可以直接双击 `start_server.bat`（会先检查 `python` 是否在 PATH 中）。

启动后会打印两个端口的访问地址。管理端首次访问需要输入 `.env` 里的 `ADMIN_TOKEN`。

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `SHARE_DIR` | 是 | `shared` | 被分享的根目录，所有文件操作限制在此目录内 |
| `ADMIN_TOKEN` | 是 | 无 | 管理端登录口令。缺失会直接启动失败 |
| `PUBLIC_BASE_URL` | 是 | `http://221.11.22.70:9900` | 生成分享链接的域名前缀，**必须带协议和端口** |
| `ADMIN_HOST` / `ADMIN_PORT` | 否 | `0.0.0.0` / `8800` | 管理端监听地址与端口 |
| `PUBLIC_HOST` / `PUBLIC_PORT` | 否 | `0.0.0.0` / `9900` | 公共端监听地址与端口 |
| `TOKEN_EXPIRE_HOURS` | 否 | `24` | 分享链接默认有效期（小时） |
| `MAX_DOWNLOADS` | 否 | `100` | 单个链接的默认最大下载次数 |
| `ALLOW_OVERWRITE` | 否 | `false` | 上传时是否允许覆盖同名文件 |
| `VCLIP_API_URL` | 否 | `http://127.0.0.1:4173/api/clips` | Vclip 的写入接口 |
| `VCLIP_ACCESS_PASSWORD` | 否 | 空 | Vclip 的 `ACCESS_PASSWORD`，不一致会被 401 拒绝 |
| `VCLIP_TIMEOUT_SECONDS` | 否 | `5` | 推送 Vclip 的超时时间 |

兼容说明：`ADMIN_TOKEN` 与 `admin_token` 都能识别（历史遗留），推荐用大写形式。

## 接口

### 管理端（8800）

除 `/` 和 `/api/auth/login` 外，所有 `/api/*` 都需要携带 Token：请求头 `X-Admin-Token: <token>`，或查询参数 `?token=<token>`（浏览器原生下载无法带自定义请求头，故支持后者）。

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/auth/login` | 校验 Token，成功返回 `{"ok": true}` |
| `GET` | `/api/list` | 列出根目录 |
| `GET` | `/api/list/{path}` | 列出子目录 |
| `POST` | `/api/upload?path=` | 上传文件（multipart） |
| `GET` | `/api/download/{filepath}` | 下载文件（需鉴权） |
| `POST` | `/api/share-link` | 生成分享链接 |
| `GET` | `/api/shares` | 查看所有活跃链接及下载统计 |

生成分享链接：

```bash
curl -X POST http://127.0.0.1:8800/api/share-link \
  -H "X-Admin-Token: 你的管理口令" \
  -H "Content-Type: application/json" \
  -d '{"filepath":"照片/1.jpg","expire_seconds":86400,"max_downloads":5}'
```

```json
{
  "token": "a1b2c3...",
  "expires_at": "2026-10-29T08:38:33+00:00",
  "download_url": "http://your-domain:9900/s/a1b2c3..."
}
```

`expire_seconds` 上限 7 天（`604800`），超出会被 Pydantic 校验拒绝。

### 公共端（9900）

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/s/{token}` | 按 Token 下载文件 |

其他任何路径返回 `403`。下载时会依次检查：链接是否存在、下载次数是否超限、是否已过期。超限或过期会**立即销毁 Token**。

## Vclip 联动

### 行为

调用 `POST /api/share-link` 生成链接时，服务会通过 FastAPI 的 `BackgroundTasks` 把链接异步推送到 Vclip，**不阻塞接口响应**。

- 推送的是 `download_url`，也就是收件人最终访问的那个地址
- 有效期跟着分享链接走（最多 7 天），而不是 Vclip 默认的 24 小时
- 推送失败只在控制台打印 `[WARN]`，**不影响分享链接本身的生成**

触发时机是「生成链接那一刻」，与「点击复制按钮」无关。

### 实现方式

走 HTTP 接口，用 Python 标准库 `urllib`，**不引入额外依赖**：

```
POST {VCLIP_API_URL}
Authorization: Basic base64("vclip:<VCLIP_ACCESS_PASSWORD>")
Content-Type: application/json

{"content": "http://.../s/<token>", "expires_at": "2026-11-04T08:38:33.930Z"}
```

### 为什么不再直连数据库

历史上有三个版本：

| 时间 | 方案 |
|---|---|
| 最初 | 直连 Supabase（anon key + `clips` 表） |
| 2026-06 | `pymysql` 直连 MySQL 的 `clips` 表 |
| 2026-10 | Vclip 迁移到本地 SQLite，改为调用 HTTP API（当前） |

SQLite 是进程内嵌入式数据库，`.db` 文件由 Vclip 的 `server.mjs` 独占持有。让 Python 再开一个连接写同一个文件，在 WAL 模式下勉强可行，但会把两个项目死死绑在同一个存储实现上——Vclip 以后再换存储，这里还得跟着改。

HTTP 接口才是稳定契约：Vclip 内部怎么存，这里不需要知道，也永远不会去碰它的数据文件。

### 部署前提

- **两个服务跑在同一台机器上**时，`127.0.0.1` 直接可用，无需额外配置。
- 如果分处两台机器，`VCLIP_API_URL` 要改成 Vclip 所在机器的内网地址（如 `http://192.168.1.10:4173/api/clips`），并放行对应端口。
- **Vclip 必须先启动**，否则推送只会打印 WARN。分享功能本身不受影响。
- `VCLIP_ACCESS_PASSWORD` 必须与 Vclip 的 `ACCESS_PASSWORD` 完全一致，否则返回 `401`，日志会明确提示检查这一项。

## 安全模型

| 层面 | 措施 |
|---|---|
| 管理端认证 | Token 校验用 `hmac.compare_digest` 做常量时间比较，避免时序侧信道 |
| 防爆破 | 连续 3 次错误锁定该 IP 24 小时，成功登录后清零 |
| 公网暴露面 | 9900 端口只认 `/s/{token}`，无文件列表、无上传、无管理接口 |
| 路径穿越 | `resolve()` 后再校验是否仍在 `BASE_DIR` 内，绝对路径直接拒绝 |
| 下载限制 | Token 可设有效期与最大下载次数，超限即销毁 |

需要注意：

- **分享 Token 存在内存里，服务重启后全部失效**，这是设计取舍而非缺陷——换来的是零持久化依赖。如果重启后需要链接继续可用，得改造为写文件或数据库。
- **对外暴露 9900 请套 HTTPS**。Token 在 URL 路径里，明文 HTTP 会进各种中间日志。
- 管理端 `8800` 建议只绑内网，或至少不要直接映射到公网。

## 项目结构

```
file-share-server/
├── filesvc_api.py       # 核心逻辑：两个 FastAPI 应用、鉴权、分享、Vclip 推送
├── index.html           # 单页管理端 UI
├── run_server.py        # 双端口启动入口（asyncio.gather 同时跑两个 uvicorn）
├── start_server.bat     # Windows 快捷启动
├── requirements.txt
├── MIGRATION_SUMMARY.md # Vclip 联动方式变更记录
└── .env                 # 本地配置，已 gitignore
```

`run_server.py` 启动前会检查两个端口是否被占用，冲突时直接退出并提示。

## 已知限制

- 分享 Token、下载统计、登录锁定状态全部在内存中，**多进程部署不共享**（`workers=1`，不要改）。
- 上传大小没设硬上限，超大文件会长时间占用连接；需要限制请在反向代理层做。
- 服务端没有删除路由，管理端 UI 也没有删除入口。清理文件请直接操作 `SHARE_DIR` 目录。
- 下载响应统一为 `application/octet-stream`，浏览器一律走下载而非内联预览。

## 许可证

MIT License
