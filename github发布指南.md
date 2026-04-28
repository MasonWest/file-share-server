# GitHub 发布指南

这份说明按当前“双端口分离”版本整理。

## 发布前确认

- `start_server.bat` 能启动
- `8800` 只提供本机管理功能
- `9900` 只提供 `/s/*` 下载功能
- `.env.example` 已包含 `PUBLIC_BASE_URL`
- `.env` 没有被提交到仓库

## 1. 配置仓库

建议仓库名：

```text
file-share-server
```

建议描述：

```text
局域网管理端 + 公网下载端分离的文件共享服务
```

建议 Topics：

```text
fastapi
python
file-sharing
lan
security
```

## 2. 提交代码

```bash
git status
git add .
git commit -m "feat: split internal admin and public download ports"
```

## 3. 配置远程仓库

```bash
git remote add origin https://github.com/YOUR_USERNAME/file-share-server.git
git branch -M main
git push -u origin main
```

## 4. 发布说明建议

这次 release note 可以写：

- 管理端和公网下载端分离
- 8800 仅限本机访问
- 9900 仅开放 `/s/*`
- 临时分享链接继续使用内存 token
- 路径安全校验保留

## 5. 建议打 tag

```bash
git tag -a v1.2.0 -m "split admin and public download ports"
git push origin v1.2.0
```

## 6. 发布后检查

- 仓库首页 README 是否显示新端口说明
- `PUBLIC_BASE_URL` 是否和你的公网地址一致
- 分享链接是否能在外网访问
- 8800 是否只能本机访问

