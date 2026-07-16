# 迁移总结：从 Supabase 切换到 MySQL

## 已完成的变更

1.  **依赖库**: 在 `requirements.txt` 中添加了 `pymysql`，用于支持 MySQL 的数据库连接。
2.  **配置更新**:
    *   在 `.env.example` 中，将 `SUPABASE_*` 相关的环境变量替换为了 `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE` 和 `MYSQL_CLIPS_TABLE`。
3.  **逻辑实现 (`filesvc_api.py`)**:
    *   将环境变量的读取逻辑从 Supabase 改为 MySQL。
    *   用 `sync_share_link_to_mysql` 函数替换了原有的 `sync_share_link_to_supabase` 函数。新函数使用 `pymysql` 直接通过数据库驱动进行连接，而不是通过 HTTP 请求。
    *   更新了 `/api/share-link` 接口中的后台任务调用，使其指向新的 MySQL 同步函数。

## 如果日后需要切换回 Supabase，该如何操作？

如果您以后想换回 Supabase，请按照以下步骤操作：

1.  **依赖库**: 您可以从 `requirements.txt` 中移除 `pymysql`（当然留着也不会有影响）。
2.  **配置更新**:
    *   在您的 `.env` 文件中，恢复 `SUPABASE_URL`, `SUPABASE_ANON_KEY` 和 `SUPABASE_CLIPS_TABLE` 变量。
    *   移除所有的 `MYSQL_*` 变量。
3.  **代码逻辑**:
    *   在 `filesvc_api.py` 中，恢复对 `SUPABASE_*` 环境变量的加载逻辑。
    *   恢复原有的 `sync_share_link_to_supabase` 函数。
    *   在 `create_share_link` 函数中，将后台任务的调用改回 `sync_share_link_to_supabase`。
