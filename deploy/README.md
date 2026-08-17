# IndexTTS-2.5 部署指南（Colab / Kaggle / 本地）

本仓库基于 **IndexTTS-2.5**（已同步 upstream 最新 + 关键 bug 修复），提供
**服务化一键部署**：两条脚本，3 步之内完成「装环境 → 下权重 → 起服务（公网隧道）」，
免注册即可拿到可分享的 WebUI 链接。

> 仓库地址：<https://github.com/infinite-gaming-studio/index-tts>

## 目录结构

```
deploy/
├── scripts/
│   ├── setup.sh   # 一键部署: 克隆仓库 → 装依赖 → 下载 IndexTTS-2.5 权重
│   ├── serve.sh   # 启动服务 + 公网隧道 + 心跳保活 (Cloudflare 优先, ngrok 回退)
│   └── logs.sh    # 查看实时日志 (webui.log / api.log)
├── service.py     # IndexTTS-2.5 API 服务 (FastAPI, 底层 2.5 引擎, 见 API.md)
├── API.md         # API 接口文档 (4 种情感模式 + 多语言 + 语速控制)
├── colab/
│   └── IndexTTS-2.5_Colab.ipynb    # Colab 3 步部署 (后台启动 + 日志 + 防断连)
├── kaggle/
│   └── IndexTTS-2.5_Kaggle.ipynb   # Kaggle 3 步部署 (后台启动 + 日志)
└── README.md      # 本文件
```

## 快速开始（3 步）

### 第 1 步：一键部署

```bash
git clone --depth 1 https://github.com/infinite-gaming-studio/index-tts.git && cd index-tts
bash deploy/scripts/setup.sh
```

`setup.sh` 自动完成：克隆仓库 → `uv sync --all-extras` 安装全部依赖 →
下载 IndexTTS-2.5 权重到 `checkpoints/`（约 3~4 GB）。

可选环境变量：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `REPO_URL` | 项目仓库地址 | 本仓库 |
| `MODEL_SOURCE` | `huggingface` / `modelscope` | huggingface |
| `HF_ENDPOINT` | HF 镜像（如 `https://hf-mirror.com`） | 无 |

```bash
# 国内网络：HF 镜像 + ModelScope
export HF_ENDPOINT=https://hf-mirror.com
MODEL_SOURCE=modelscope bash deploy/scripts/setup.sh
```

### 第 2 步：启动服务 + 公网隧道

```bash
bash deploy/scripts/serve.sh                    # 默认启动 WebUI
SERVICE=api bash deploy/scripts/serve.sh        # 启动 API 服务 (FastAPI, /docs)
SERVICE=both bash deploy/scripts/serve.sh       # API + WebUI 一起
```

- 默认 **Cloudflare 快速隧道**（免注册、免 token），就绪后打印
  `https://xxx.trycloudflare.com` 公网链接，浏览器打开即用。
- 备选 **ngrok**：`TUNNEL=ngrok NGROK_TOKEN=xxx bash deploy/scripts/serve.sh`
- 仅本机：`TUNNEL=none bash deploy/scripts/serve.sh`

API 服务说明见 **[API.md](API.md)**：`POST /api/tts`（4 种情感模式 + 多语言
ZH/EN/JA/ES/AR + 语速控制 duration_factor + base64 JSON 响应）、`GET /api/health`、
Swagger `/docs`。API 鉴权默认开启：固定 Key `indextts-fixed-key-2026`（打印在启动日志），
`INDEXTTS_API_TOKEN` 可自定义 Key 或置空 `""` 关闭。

可选环境变量：

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `SERVICE` | `webui` / `api` / `both` | webui |
| `TUNNEL` | `cf` / `ngrok` / `none` | cf |
| `PORT` | 本地端口（WebUI 7860 / API 8000） | 按服务类型 |
| `WEBUI_ARGS` | 追加 webui 参数（如 `--fp16`） | 空 |
| `API_ARGS` | 追加 API 参数（如 `--qwen-emo --deepspeed`） | 空 |
| `INDEXTTS_API_TOKEN` | API 鉴权 Key；默认固定 `indextts-fixed-key-2026`，可自定义，置空 `""` 关闭 | 固定 `indextts-fixed-key-2026` |
| `NGROK_TOKEN` | ngrok authtoken（TUNNEL=ngrok 时建议） | 空 |
| `KEEPALIVE` | 心跳保活 1 开 / 0 关 | 1 |

### 第 3 步：查看日志（排查问题）

```bash
bash deploy/scripts/logs.sh            # 查看 WebUI 日志最后 50 行
bash deploy/scripts/logs.sh api        # 查看 API 日志 (api.log)
bash deploy/scripts/logs.sh -f         # 实时跟踪日志
tail -f webui.log                      # 等价实时跟踪
```

服务启动后 `serve.sh` 会自动打印最近 20 行日志；后台运行期间也可随时
`tail -f` 查看。日志文件：

| 文件 | 内容 |
| --- | --- |
| `webui.log` | WebUI (gradio) 服务日志 |
| `api.log` | API (FastAPI) 服务日志 |
| `serve_console.log` | serve.sh 启动过程输出（含公网 URL） |
| `keepalive.log` | 心跳保活 ping 记录 |

### 第 4 步（可选）：命令行合成验证

```python
from indextts.utils.examples_downloader import ensure_examples_available
ensure_examples_available()

from indextts.infer_v2_5 import IndexTTS2
tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints", use_bf16=True)

tts.infer(
    spk_audio_prompt="examples/voice_01.wav",
    text="你好，我是 IndexTTS-2.5，欢迎测试多语言语音合成。",
    lang="ZH",  # ZH / EN / JA / ES / AR
    output_path="output_zh.wav",
    verbose=True,
)
```

## 🔒 会话防关闭（Colab / Kaggle）

| 平台 | 空闲超时 | 防断连措施 |
| --- | --- | --- |
| Colab 免费版 | 约 90 分钟无操作断连 | ① serve.sh 心跳保活（每 120s ping）；② notebook 内**防断连 JS**（每 60s 自动点"连接"按钮，需保持标签页打开） |
| Kaggle | 约 20 分钟空闲回收 | ① 心跳保活；② 会话运行在服务端，**关闭标签页不影响**；上限 12 小时（平台硬限制） |

- **Colab**：运行 notebook 中的「防断连」单元格即可（`display(Javascript(...))`
  定时点击连接按钮）；配合 `serve.sh` 心跳，可显著降低断连概率。
- **Kaggle**：心跳保活降低空闲回收概率；12 小时硬上限无法延长，可把代码与权重
  打包进 Dataset 减少每次启动耗时。
- 心跳默认开启，日志记录在 `keepalive.log`；`KEEPALIVE=0 bash deploy/scripts/serve.sh` 可关闭。

## Colab / Kaggle 使用

上传对应 notebook 后**只需运行前两个单元格**即可完成部署（第 3 步可选）：

| 平台 | Notebook | 注意事项 |
| --- | --- | --- |
| Colab | `colab/IndexTTS-2.5_Colab.ipynb` | 运行时选 GPU (T4)；WebUI 用 CF 隧道 |
| Kaggle | `kaggle/IndexTTS-2.5_Kaggle.ipynb` | Settings: Accelerator=GPU + Internet=ON |

notebook 内部即调用 `deploy/scripts/setup.sh` 与 `serve.sh`，克隆地址已指向本仓库。

## 常见问题

- **显存不足**：确认使用 `use_bf16=True`（2.5）/ `use_fp16=True`（2）；或
  `WEBUI_ARGS="--fp16" bash deploy/scripts/serve.sh`。
- **HF 下载慢/超时**：`export HF_ENDPOINT="https://hf-mirror.com"` 或
  `MODEL_SOURCE=modelscope`。
- **CF 隧道不稳定**：换 ngrok（需注册 token）或 `TUNNEL=none` 本地使用。
- **示例音频缺失**：运行 `ensure_examples_available()`（见上）。
