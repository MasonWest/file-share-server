# Vclip 联动方式变更记录

## 当前方案：通过 Vclip HTTP API 写入

Vclip 已从 MySQL 迁移到本地 SQLite，两个项目不再共享数据库，改为通过 HTTP 接口通信。

**变更内容：**

1.  **依赖库**：`requirements.txt` 移除 `pymysql`，改用 Python 标准库 `urllib`，无新增依赖。
2.  **配置**：`.env` 中移除 `MYSQL_*`，新增：
    *   `VCLIP_API_URL`：Vclip 的写入接口，默认 `http://127.0.0.1:4173/api/clips`
    *   `VCLIP_ACCESS_PASSWORD`：必须与 Vclip 的 `.env` 里 `ACCESS_PASSWORD` 一致
    *   `VCLIP_TIMEOUT_SECONDS`：请求超时，默认 5 秒
3.  **逻辑（`filesvc_api.py`）**：
    *   删除 `load_dotenv("mysql.env")` 与全部 `MYSQL_*` 常量。
    *   `sync_share_link_to_mysql` → `sync_share_link_to_vclip`，改为 `POST {VCLIP_API_URL}`，body 为 `{"content": 分享链接, "expires_at": ISO8601}`，带 HTTP Basic Auth。
    *   `/api/share-link` 的后台任务指向新函数。
4.  **前提**：Vclip 的 `npm run serve`（或 `启动vclip.bat`）必须先启动，否则推送会失败——但只会在日志里打印 `[WARN]`，不影响分享链接本身的生成。

## 为什么不再直连数据库

SQLite 是进程内嵌入式数据库，`.db` 文件由 Vclip 的 `server.mjs` 进程持有。让 Python 再开一个连接去写同一个文件，WAL 模式下勉强可行，但会把两个项目死死耦合在同一个存储实现上——Vclip 以后再换存储，这里还得跟着改一次。

走 HTTP API 则是稳定契约：Vclip 内部怎么存，这边不需要知道。

## 历史沿革

| 时间 | 方案 |
|---|---|
| 最初 | 直连 Supabase（HTTP + anon key + `clips` 表） |
| 2026-06 | 改为 `pymysql` 直连 MySQL 的 `clips` 表 |
| 2026-10 | Vclip 迁移到 SQLite，改为调用 Vclip 的 HTTP API（当前） |

## 如果要改回直连数据库

不建议。若确有需要，参考 git 历史中 `sync_share_link_to_mysql` 的实现即可恢复，但需要同步处理 Vclip 侧的存储格式。
