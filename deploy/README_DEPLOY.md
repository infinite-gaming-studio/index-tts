# IndexTTS2 部署服务优化指南

## 已启用的优化功能

当前部署脚本已默认启用以下加速优化：

| 优化项 | 默认状态 | 说明 | 效果 |
|--------|----------|------|------|
| **FP16** | ✅ 启用 | 半精度推理 | 显存减半，速度提升20-50% |
| **Accel** | ✅ 启用 | GPT加速引擎 | FlashAttention优化，显著提升 |
| **DeepSpeed** | ✅ 启用 | DeepSpeed推理 | 额外10-20%加速 |
| **CUDA Kernel** | ✅ 启用 | BigVGAN CUDA内核 | 声码器加速 |
| **Torch Compile** | ❌ 禁用 | PyTorch编译优化 | 减少Python开销，但Notebook环境不稳定 |

## 环境适配

### 自动检测

脚本会自动检测是否在 Colab/Kaggle 环境：
- **Notebook环境**: 自动禁用 `torch.compile`（避免不稳定）
- **本地/服务器环境**: 全部优化启用

### 容错机制

如果启用全部优化失败，脚本会自动回退到基础配置：
```
⚠️ 启用全部优化失败: xxx
🔄 回退到基础配置...
```

## 命令行参数

### 启动服务

```bash
# 默认启动（推荐）
python deploy/service.py

# 仅API模式
python deploy/service.py --mode api

# 禁用特定优化
python deploy/service.py --no-accel --no-deepspeed

# 启用torch.compile（不推荐在Colab使用）
python deploy/service.py --torch-compile

# 完整命令示例
python deploy/service.py \
    --port 8000 \
    --mode both \
    --no-fp16 \
    --no-accel \
    --no-deepspeed \
    --no-cuda-kernel
```

### 参数说明

| 参数 | 说明 |
|------|------|
| `--port` | 服务端口（默认8000） |
| `--mode` | 部署模式：api/webui/both |
| `--repo-dir` | 项目根目录路径 |
| `--no-fp16` | 禁用FP16 |
| `--no-accel` | 禁用GPT加速引擎 |
| `--no-deepspeed` | 禁用DeepSpeed |
| `--no-cuda-kernel` | 禁用CUDA内核 |
| `--torch-compile` | 启用PyTorch编译（不推荐Colab） |

## Colab/Kaggle 部署

### Colab 示例

```python
# 安装依赖
!pip install -q uv
!uv sync --all-extras

# 下载模型
!uv tool install "huggingface-hub[cli,hf_xet]"
!hf download IndexTeam/IndexTTS-2 --local-dir=checkpoints

# 启动服务
!python deploy/service.py --mode both
```

### Kaggle 示例

```python
# 在Notebook单元格中
import subprocess
process = subprocess.Popen(
    ['python', 'deploy/service.py', '--mode', 'both'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)
```

## 性能对比

### RTF (实时率) 预期

| 配置 | RTF | 速度倍数 |
|------|-----|----------|
| 无优化 | ~0.8 | 1x |
| FP16 | ~0.5 | 1.6x |
| FP16 + Accel | ~0.3 | 2.7x |
| 全部优化 | ~0.2 | 4x |

*RTF < 1.0 表示实时生成，数值越小越快*

## 故障排除

### 显存不足

如果出现OOM错误，尝试：
```bash
# 禁用DeepSpeed和CUDA内核
python deploy/service.py --no-deepspeed --no-cuda-kernel

# 或禁用FP16（不推荐）
python deploy/service.py --no-fp16
```

### DeepSpeed安装失败

```bash
# 安装DeepSpeed
pip install deepspeed

# 如果失败，可以禁用
python deploy/service.py --no-deepspeed
```

### CUDA内核加载失败

脚本会自动回退到torch实现，无需手动处理。

## 验证优化是否生效

启动时会显示实际启用的优化：
```
🚀 启用优化: FP16=True, Accel=True, DeepSpeed=True, CUDA内核=True, Torch编译=False
✅ 模型加载完成!
实际启用的优化: Accel=True, DeepSpeed=True, CUDA内核=True
```

如果显示 `Accel=False`，说明加速引擎未成功加载。

## 其他优化建议

1. **使用更快的GPU**: T4 -> V100 -> A100
2. **减少参考音频长度**: 控制在10秒内
3. **限制生成长度**: 使用 `max_mel_tokens` 参数
4. **启用缓存**: 相同参考音频会自动缓存

## 技术支持

- GitHub Issues: https://github.com/index-tts/index-tts/issues
- QQ群: 663272642 (No.4), 1013410623 (No.5)
- Discord: https://discord.gg/uT32E7KDmy
