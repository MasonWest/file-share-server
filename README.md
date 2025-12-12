# 局域网文件共享服务器

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.68+-green)
![Vue.js](https://img.shields.io/badge/Vue.js-3.0+-brightgreen)
![License](https://img.shields.io/badge/License-MIT-yellow)

一个简单易用的局域网文件共享工具，支持文件夹浏览、文件上传下载和排序功能。

## 功能特性

- 📁 **文件夹浏览**：支持多级目录浏览
- 📄 **文件管理**：上传、下载文件
- 🔍 **排序功能**：按名称、大小、修改日期排序
- 🗺️ **路径导航**：面包屑导航，方便返回上级
- 🌐 **中文界面**：友好的中文用户界面
- 🔒 **安全可控**：可配置共享目录

## 快速开始

### 1. 安装Python
确保已安装Python 3.7+，可从 [python.org](https://www.python.org/downloads/) 下载

### 2. 配置共享目录
1. 复制 `.env.example` 为 `.env`
2. 编辑 `.env` 文件，设置 `SHARE_DIR` 为你的共享目录路径

```env
# 示例：共享D盘的"共享文件"文件夹
SHARE_DIR=D:\共享文件
```

### 3. 启动服务器

#### Windows用户：
- 双击 `start_server.bat`（推荐）
- 或右键 `start_server.ps1` → "使用PowerShell运行"

#### 其他系统：
```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务器
python run_server.py
```

### 4. 访问使用
- 打开浏览器访问：`http://localhost:8800`
- 局域网其他设备访问：`http://[服务器IP地址]:8800`

## 详细配置

### 环境变量配置 (.env文件)

```env
# 共享目录路径（必填）
SHARE_DIR=D:\共享文件夹

# 服务器端口（可选，默认8800）
PORT=8800

# 服务器绑定地址（可选，默认0.0.0.0）
HOST=0.0.0.0

# 允许文件覆盖（可选，默认false）
ALLOW_OVERWRITE=false
```

### 端口说明
- `8800`：默认端口，可在 `.env` 中修改
- `0.0.0.0`：监听所有网络接口，允许局域网访问

## 使用指南

### 文件操作
1. **上传文件**：点击"选择文件" → 选择文件 → 点击"上传"
2. **下载文件**：点击文件右侧的"下载"按钮
3. **浏览文件夹**：点击文件夹进入子目录

### 排序功能
- **文件夹**：自动按名称排序
- **文件**：可点击"名称"、"大小"、"修改日期"按钮排序
- **切换顺序**：点击相同排序按钮切换升序/降序

### 路径导航
- 顶部显示当前路径
- 点击任意路径部分可快速跳转
- "根目录"链接返回最上层

## 常见问题

### 1. 无法访问服务器
- 检查防火墙是否允许端口8800
- 确认服务器IP地址正确
- 检查 `.env` 中的 `HOST` 配置

### 2. 上传文件失败
- 检查共享目录是否有写入权限
- 确认磁盘空间充足
- 检查 `ALLOW_OVERWRITE` 设置

### 3. 依赖安装失败
```bash
# 使用国内镜像源
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 修改默认端口
编辑 `.env` 文件：
```env
PORT=8888
```

## 文件结构

```
文件共享服务器/
├── filesvc_api.py      # 后端API主程序
├── index.html          # 前端界面
├── run_server.py       # 服务器启动脚本
├── requirements.txt    # Python依赖
├── .env.example        # 配置文件模板
├── start_server.bat    # Windows启动脚本
├── start_server.ps1    # PowerShell启动脚本
└── README.md          # 说明文档
```

## 技术栈

- **后端**：Python + FastAPI
- **前端**：Vue.js 3 + Tailwind CSS
- **文件处理**：python-multipart
- **配置管理**：python-dotenv

## 安全提示

1. 仅在内网安全环境使用
2. 不要共享敏感目录
3. 定期检查共享内容
4. 使用后及时关闭服务器

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## GitHub仓库

本项目已开源，欢迎Star和贡献！

```bash
# 克隆项目
git clone https://github.com/YOUR_USERNAME/file-share-server.git
cd file-share-server
```

### 贡献指南
1. Fork本仓库
2. 创建功能分支 (`git checkout -b feature/新功能`)
3. 提交更改 (`git commit -m '添加新功能'`)
4. 推送到分支 (`git push origin feature/新功能`)
5. 创建Pull Request

### 问题反馈
如有问题或建议，请在GitHub Issues中提出。

---

**开始分享你的文件吧！** 🚀

*如果觉得这个项目有用，请给个Star支持一下！* ⭐