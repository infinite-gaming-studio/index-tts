# IndexTTS2 部署工具

简洁的部署方案，解决"先有鸡还是先有蛋"的导入悖论，支持mamba加速安装。

## 核心特性

1. **导入悖论解决**: Cell 1 独立克隆代码，Cell 2+ 才能导入 deploy 模块
2. **mamba加速**: 自动检测Colab/Kaggle环境，使用mamba加速依赖安装
3. **环境适配**: 自动检测并适配Google Colab和Kaggle环境

## 目录结构

```
deploy/
├── IndexTTS2_Deploy.ipynb  # Notebook部署文件（4个Cell）
├── service.py              # 核心服务（FastAPI + WebUI）
├── launcher.py             # 服务启动器
├── utils.py                # 工具函数（含mamba支持）
└── README.md               # 本文件
```

## 使用方式

### 方式1: Notebook 部署（Colab/Kaggle）

**必须按顺序执行4个Cell**：

#### Cell 1: 环境准备（独立运行）
```python
import os, sys, json, subprocess

# 环境检测
IN_COLAB = 'google.colab' in sys.modules
IN_KAGGLE = os.path.exists('/kaggle/input')
WORK_DIR = '/content' if IN_COLAB else '/kaggle/working' if IN_KAGGLE else '/tmp'
REPO_DIR = f"{WORK_DIR}/index-tts"

# 基础依赖 + 克隆代码
subprocess.run(["pip", "install", "-q", "torch==2.8.0", "torchaudio==2.8.0", 
    "--index-url", "https://download.pytorch.org/whl/cu121"], check=True)

subprocess.run(["git", "clone", "-b", "dev", 
    "https://github.com/infinite-gaming-studio/index-tts.git", REPO_DIR], check=True)

# 保存配置
json.dump({"work_dir": WORK_DIR, "repo_dir": REPO_DIR, 
    "in_colab": IN_COLAB, "in_kaggle": IN_KAGGLE}, 
    open("/tmp/notebook_config.json", "w"))

sys.path.insert(0, REPO_DIR)
```

#### Cell 2: 使用mamba安装依赖
```python
# 读取环境配置
config = json.load(open("/tmp/notebook_config.json"))
IN_COLAB = config.get("in_colab", False)
IN_KAGGLE = config.get("in_kaggle", False)

# 现在可以安全导入deploy模块
from deploy.utils import DependencyInstaller, ModelDownloader, check_model_exists

# 使用mamba加速安装（自动适配Colab/Kaggle）
DependencyInstaller.install_deps(
    use_mamba=True,
    in_colab=IN_COLAB,
    in_kaggle=IN_KAGGLE
)

# 安装项目
subprocess.run(["pip", "install", "-q", "-e", REPO_DIR], check=True)

# 下载模型
CHECKPOINT_DIR = f"{REPO_DIR}/checkpoints"
if not check_model_exists(CHECKPOINT_DIR):
    ModelDownloader.download(CHECKPOINT_DIR)
```

#### Cell 3-4: 启动和管理服务
```python
# Cell 3: 启动服务
from deploy.launcher import quick_start
launcher = quick_start(port=8000, mode="both", ngrok_token=None)

# Cell 4: 管理（可选）
launcher.logs(30)   # 查看日志
launcher.stop()     # 停止服务
```

### 方式2: 命令行部署（无导入悖论）

```bash
# 1. 克隆代码
git clone -b dev https://github.com/infinite-gaming-studio/index-tts.git
cd index-tts

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python deploy/launcher.py start --port 8000 --mode both

# 4. 其他命令
python deploy/launcher.py status
python deploy/launcher.py logs
python deploy/launcher.py stop
```

### 方式3: 直接运行服务脚本

```bash
python deploy/service.py --port 8000 --mode both --repo-dir /path/to/index-tts
```

## 环境支持

| 环境 | 检测方法 | 工作目录 |
|------|---------|---------|
| Google Colab | `'google.colab' in sys.modules` | `/content` |
| Kaggle | `os.path.exists('/kaggle/input')` | `/kaggle/working` |
| 其他 | 默认 | `/tmp` |

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
