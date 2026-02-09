# IndexTTS2 部署工具

简洁的部署方案，将复杂逻辑移至Python脚本，Notebook保持简洁。

## 目录结构

```
deploy/
├── service.py    # 核心服务（FastAPI + WebUI）
├── launcher.py   # 服务启动器（支持Notebook和CLI）
├── utils.py      # 工具函数（环境检测、模型下载等）
└── README.md     # 本文件
```

## 使用方式

### 方式1: Notebook 部署（推荐）

```python
# Cell 1: 环境设置（仅安装）
from deploy.utils import (
    EnvDetector, DependencyInstaller, 
    ModelDownloader, clone_repo, save_config
)

work_dir = EnvDetector.get_work_dir()
repo_dir = f"{work_dir}/index-tts"

# 安装依赖
DependencyInstaller.install_pytorch()
DependencyInstaller.install_deps()

# 克隆代码
clone_repo(repo_dir)

# 下载模型
ModelDownloader.download(f"{repo_dir}/checkpoints")

# 保存配置
save_config(repo_dir)
```

```python
# Cell 2: 启动服务
from deploy.launcher import quick_start

# 启动（设置ngrok_token以获得公网访问）
launcher = quick_start(port=8000, mode="both", ngrok_token=None)

# 查看日志
# launcher.logs(20)

# 检查状态
# launcher.status()

# 停止服务
# launcher.stop()
```

### 方式2: 命令行部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python deploy/launcher.py start --port 8000 --mode both

# 3. 其他命令
python deploy/launcher.py status
python deploy/launcher.py logs
python deploy/launcher.py stop
```

### 方式3: 直接运行服务脚本

```bash
python deploy/service.py --port 8000 --mode both --repo-dir /path/to/index-tts
```

## 配置说明

- **mode**: `api` | `webui` | `both`
  - `api`: 仅启动API服务
  - `webui`: 仅启动WebUI
  - `both`: 同时启动（默认）

- **port**: 服务端口（默认8000）

- **ngrok_token**: 用于公网访问，从 https://dashboard.ngrok.com 获取

## API 接口

- `POST /api/tts` - 文本转语音
- `GET /api/health` - 健康检查
- `GET /docs` - API文档
- `/ui` - WebUI界面

## 示例

```bash
# API调用
curl -X POST http://localhost:8000/api/tts \
  -F "text=你好世界" \
  -F "spk_audio=@voice.wav" \
  --output out.wav
```
