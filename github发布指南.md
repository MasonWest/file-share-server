# GitHub 发布指南

这份指南按当前项目状态整理，适合把这个仓库发布到 GitHub。

## 发布前先确认

- `start_server.bat` 可以正常启动
- `.env.example` 内容可读且可直接复制修改
- `README.md` 已说明启动方式、配置项、临时分享链接和安全限制
- 仓库中不要提交你本机私有的 `.env`

## 1. 初始化或检查 Git 仓库

如果当前目录还没有提交：

```bash
git status
git add .
git commit -m "feat: improve startup and add temporary share links"
```

如果远程仓库还没配置：

```bash
git remote add origin https://github.com/YOUR_USERNAME/file-share-server.git
```

## 2. 推送到 GitHub

```bash
git branch -M main
git push -u origin main
```

## 3. 建议填写的仓库信息

仓库名建议：

```text
file-share-server
```

描述建议：

```text
局域网文件共享服务，支持目录浏览、上传下载、临时分享链接和基础路径安全校验
```

建议 Topics：

```text
fastapi
python
file-share
lan
internal-tools
```

## 4. README 建议保留的信息

仓库首页至少要能让别人马上看懂这几件事：

- 这是个什么工具
- 怎么配置 `SHARE_DIR`
- 怎么启动
- 临时分享链接怎么用
- 安全边界是什么

## 5. 建议打一个版本标签

如果你准备做一个相对正式的版本，可以打 tag：

```bash
git tag -a v1.1.0 -m "startup fix and temporary share links"
git push origin v1.1.0
```

然后去 GitHub 的 `Releases` 页面创建 release。

## 6. 当前版本变更点

这次适合写进 release note 的内容：

- 重写 `start_server.bat`
- 删除不可用的 `start_server.ps1`
- 修复启动输出兼容性问题
- 增加临时文件分享链接功能
- 增加路径校验，限制访问必须在 `SHARE_DIR` 内
- 更新 README、发布指南和配置示例

## 7. 不建议提交的内容

- `.env`
- 真实共享目录中的文件
- 测试用的临时目录
- 本地运行日志

## 8. 可选的后续增强

- 后端递归搜索
- 分享链接管理页
- 自定义分享过期时间 UI
- 持久化 token 存储
