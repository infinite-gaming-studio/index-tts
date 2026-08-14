# IndexTTS-2.5 部署指南（Colab / Kaggle）

本目录提供面向 **IndexTTS-2.5**（当前仓库 main 分支，已同步 upstream 最新版）的
一键部署文件，适用于免费 GPU 环境快速测试。

## 文件说明

| 文件 | 平台 | 说明 |
| --- | --- | --- |
| `colab/IndexTTS-2.5_Colab.ipynb` | Google Colab | 免费 T4 GPU，含 WebUI 隧道方案 |
| `kaggle/IndexTTS-2.5_Kaggle.ipynb` | Kaggle Notebook | P100/T4 GPU，含 Output 下载 |

两个 notebook 流程一致：

1. 检查 GPU
2. 克隆仓库（默认上游 `index-tts/index-tts`，可改成你的 fork）
3. `uv sync --all-extras` 安装全部依赖
4. 下载 IndexTTS-2.5 权重到 `checkpoints/`（HuggingFace 或 ModelScope）
5. 环境自检 `uv run tools/gpu_check.py`
6. 初始化 `IndexTTS2(..., use_bf16=True)`（BF16 省显存）
7. 语音克隆合成
8. 情感控制合成（`emo_audio_prompt` + `emo_alpha`）
9. 下载结果（Colab 直接下载 / Kaggle 走 Output 标签页）

## 使用前须知

- **Colab**：运行时类型选 **GPU**（T4）。WebUI 需用 cloudflared/ngrok 隧道暴露
  `127.0.0.1:7860`，notebook 末尾已附示例。
- **Kaggle**：Settings 里 **Accelerator = GPU**，且 **Internet 必须开启**（下载
  权重需要联网）。
- 权重约 3~4 GB，首次下载视网速约 5~15 分钟。
- 国内网络慢时，先运行 `%env HF_ENDPOINT=https://hf-mirror.com`，或用 ModelScope
  下载（notebook 中已附备选命令）。

## 参考命令速查（本地 / 服务器通用）

```bash
pip install -U uv
git clone https://github.com/index-tts/index-tts.git && cd index-tts
uv sync --all-extras

# 下载 IndexTTS-2.5 权重
uv tool install huggingface-hub
hf download IndexTeam/IndexTTS-2.5 --local-dir=checkpoints

# 环境自检
uv run tools/gpu_check.py

# 启动 WebUI（默认 IndexTTS-2.5）
uv run webui.py
```

## Python API 最小示例

```python
from indextts.infer_v2_5 import IndexTTS2

tts = IndexTTS2(cfg_path="checkpoints/config.yaml", model_dir="checkpoints", use_bf16=True)

# 语音克隆（多语言，lang 支持 ZH/EN/JA/ES/AR）
tts.infer(
    spk_audio_prompt="examples/voice_01.wav",
    text="你好，我是 IndexTTS-2.5，欢迎测试多语言语音合成。",
    lang="ZH",
    output_path="output_zh.wav",
    verbose=True,
)

# 情感控制
tts.infer(
    spk_audio_prompt="examples/voice_07.wav",
    text="酒楼丧尽天良，开始借机竞拍房间，哎，一群蠢货。",
    lang="ZH",
    output_path="output_emo.wav",
    emo_audio_prompt="examples/emo_sad.wav",
    emo_alpha=0.9,
    verbose=True,
)
```

## 常见问题

- **显存不足**：确认使用 `use_bf16=True`（IndexTTS-2.5）/ `use_fp16=True`
  （IndexTTS-2）；关闭 `use_deepspeed` / `use_cuda_kernel` 可进一步省显存。
- **HF 下载超时**：`export HF_ENDPOINT="https://hf-mirror.com"` 或改用
  ModelScope 下载。
- **首次运行报错缺音频示例**：运行
  `python -c "from indextts.utils.examples_downloader import ensure_examples_available; ensure_examples_available()"`。
