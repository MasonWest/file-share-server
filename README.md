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
- **设备免密登录**：首次输一次口令，之后本设备凭设备令牌直接进入；设备丢失可单独撤销，不影响其他设备
- **渐进式防爆破**：连续错 5 次锁定 5 分钟，再犯翻倍（上限 1 小时），可从已登录设备解锁

## 环境要求

- **Python 3.10 或以上**。代码用到了 `int | None` 联合类型语法，3.9 及以下会直接语法报错。
- 无需数据库。设备令牌和分享链接各存一个 JSON 文件（`devices.json` / `shares.json`），写入走「临时文件 + 原子替换」，崩溃不会读到半截内容。

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

关掉服务：双击 `stop_server.bat`。它会按端口找到监听进程，确认是 python 之后结束；如果端口被别的程序占着，它不会动手，只提示你加 `/force`。

```bat
stop_server.bat            :: 关闭 8800/9900（端口从 .env 读）
stop_server.bat 8801       :: 关闭指定管理端口
stop_server.bat /force     :: 端口被非 python 进程占用时强制结束
```

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
| `MAX_UPLOAD_MB` | 否 | `4096` | 单文件上传上限（MB），`0` 表示不限制。超限返回 413，不落盘 |
| `LIST_PAGE_SIZE` | 否 | `200` | 目录列表每页文件数。目录数量本身不分页，始终全量返回 |
| `DEVICE_TOKEN_TTL_DAYS` | 否 | `365` | 设备令牌有效期（天），到期需重新输口令 |
| `DEVICES_FILE` | 否 | `devices.json` | 受信设备记录文件，只存令牌的 sha256 哈希 |
| `SHARES_FILE` | 否 | `shares.json` | 分享链接记录文件，存相对 `SHARE_DIR` 的路径 |
| `LOGIN_MAX_ATTEMPTS` | 否 | `5` | 连续失败多少次触发锁定 |
| `LOGIN_LOCKOUT_SECONDS` | 否 | `300` | 首次锁定时长（秒），再犯翻倍 |
| `LOGIN_LOCKOUT_MAX_SECONDS` | 否 | `3600` | 锁定时间上限（秒） |
| `TRUST_PROXY` | 否 | `false` | 仅在反向代理后开启，否则 `X-Forwarded-For` 可被伪造 |
| `VCLIP_API_URL` | 否 | `http://127.0.0.1:4173/api/clips` | Vclip 的写入接口 |
| `VCLIP_ACCESS_PASSWORD` | 否 | 空 | Vclip 的 `ACCESS_PASSWORD`，不一致会被 401 拒绝 |
| `VCLIP_TIMEOUT_SECONDS` | 否 | `5` | 推送 Vclip 的超时时间 |

兼容说明：`ADMIN_TOKEN` 与 `admin_token` 都能识别（历史遗留），推荐用大写形式。

## 接口

### 管理端（8800）

鉴权有两条路，任一条有效即可：

1. **设备令牌（推荐）**：首次用口令登录时勾选「在这台设备上记住我」，服务端签发一个长期令牌，前端存 `localStorage`，之后自动携带 `X-Device-Token: <device_token>`。管理员口令不再留在浏览器里。
2. **管理员口令**：请求头 `X-Admin-Token: <token>`，或查询参数 `?token=<token>`。仅用于登录和临时调试。

浏览器原生下载无法带自定义请求头，因此下载接口额外支持设备令牌查询参数 `?dt=<device_token>`。

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/auth/login` | 校验口令；`remember=true` 时额外返回 `device_token` |
| `POST` | `/api/auth/unlock` | 解除某个 IP 的登录锁定（需已通过鉴权） |
| `GET` | `/api/devices` | 列出所有受信设备 |
| `DELETE` | `/api/devices/{id}` | 撤销某台设备 |
| `GET` | `/api/list?offset=0&limit=200` | 列出根目录（`limit=0` 返回全量，默认取 `LIST_PAGE_SIZE`） |
| `GET` | `/api/list/{path}` | 列出子目录，支持同样的分页参数 |
| `POST` | `/api/upload?path=` | 上传文件（multipart），超过 `MAX_UPLOAD_MB` 返回 413 |
| `GET` | `/api/download/{filepath}` | 下载文件（需鉴权） |
| `POST` | `/api/share-link` | 生成分享链接 |
| `GET` | `/api/shares` | 查看所有活跃链接及下载统计 |
| `DELETE` | `/api/shares/{token}` | 手动作废一条链接 |
| `GET` | `/health` | 健康检查（无需鉴权，不含敏感信息） |

列表响应里 `folders` 始终是完整列表，`files` 按页返回；`total_files` / `has_more` / `next_offset` 用于「加载更多」。

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
| 管理端认证 | 设备令牌（存 sha256 哈希）优先，管理员口令兜底；口令比较用 `hmac.compare_digest` 做常量时间比较 |
| 凭据留存 | 口令只在登录请求中出现一次，浏览器只保存设备令牌，不保存口令 |
| 设备撤销 | 每台设备独立令牌，丢失可单独撤销，不影响其他设备 |
| 防爆破 | 连续 5 次错误锁定 5 分钟，再犯翻倍（上限 1 小时）；可从已登录设备调用 `/api/auth/unlock` 解除 |
| 公网暴露面 | 9900 端口只认 `/s/{token}` 与 `/health`，无文件列表、无上传、无管理接口 |
| 接口清单 | 管理端的 `/docs`、`/openapi.json`、`/redoc` 全部关闭 |
| 路径穿越 | `resolve()` 后再校验是否仍在 `BASE_DIR` 内，绝对路径直接拒绝 |
| 下载限制 | Token 可设有效期与最大下载次数，超限即销毁；文件已删除时不消耗额度 |

需要注意：

- **路由器只需映射公网端端口**（默认 9900 或你的外网映射端口）。管理端 8800 监听所有网卡是为了让手机 / 平板 / VR 从内网登录，**不要把它映射到公网**。
- **分享链接会持久化到 `shares.json`**（默认项目根目录，已 gitignore），服务重启后已发出去的链接继续有效。存的是相对 `SHARE_DIR` 的路径，换盘或换机器也能指向对的文件。
- **受信设备记录会持久化**到 `devices.json`（默认在项目根目录，已 gitignore），服务重启不影响设备免密登录。
- **对外暴露公网端口请套 HTTPS**。Token 在 URL 路径里，明文 HTTP 会进各种中间日志。
- 管理口令建议用「好记但够长」的短语（如 `mason-travel-2026`），不必背随机串——强度由设备令牌、限流和端口隔离共同承担。

## 项目结构

```
file-share-server/
├── filesvc_api.py       # 两个 FastAPI 应用、鉴权、分享、Vclip 推送
├── device_store.py      # 设备令牌签发 / 校验 / 撤销（只存哈希）
├── share_store.py       # 分享链接持久化（只存相对路径）
├── index.html           # 单页管理端 UI
├── run_server.py        # 双端口启动入口（asyncio.gather 同时跑两个 uvicorn）
├── test_filesvc.py      # 回归测试（python test_filesvc.py，无需 pytest）
├── start_server.bat     # Windows 快捷启动
├── stop_server.bat      # Windows 一键关闭（按端口找进程，不误杀别的程序）
├── requirements.txt
├── MIGRATION_SUMMARY.md # Vclip 联动方式变更记录
└── .env                 # 本地配置，已 gitignore
```

`run_server.py` 启动前会检查两个端口是否被占用，冲突时直接退出并提示；启动后会打印本机的内网地址，手机 / 平板直接照着输即可。

## 已知限制

- 分享链接、设备令牌已持久化；**登录锁定状态仍在内存中**，进程重启后自动解锁（这对单人服务反而是好事）。多进程部署仍不共享状态，`workers=1` 不要改。
- 上传上限默认 4096 MB，可在 .env 用 `MAX_UPLOAD_MB` 调整；超限在上传过程中即中止并删除半截文件，不会写满磁盘。
- 目录列表按文件分页（默认每页 200 条），子目录始终全量返回。
- 服务端没有删除文件的接口，管理端 UI 也没有删除入口。清理文件请直接操作 `SHARE_DIR` 目录；分享链接可以在「活跃分享」里作废。
- 下载响应统一为 `application/octet-stream`，浏览器一律走下载而非内联预览。
- 登录锁定按来源 IP 计。多台设备共用一个 NAT 出口时会一起被锁，用 `/api/auth/unlock` 或等 5 分钟即可。

## 测试

```bash
python test_filesvc.py
```

全程使用临时目录，不会碰真实 `SHARE_DIR`。覆盖：鉴权与设备令牌、设备撤销、路径穿越、上传异常、分享生命周期、下载计数、渐进式锁定与解锁。

## 许可证

MIT License
