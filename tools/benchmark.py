#!/usr/bin/env python3
"""
IndexTTS-2.5 推理性能基准测试 (Colab / Kaggle / 本地通用)
=========================================================

一键验证优化效果: 检测 GPU 精度策略 + 实测合成 RTF (Real-Time Factor)。

用法:
    python tools/benchmark.py                          # 默认: 20 步扩散
    python tools/benchmark.py --diffusion-steps 25     # 对比: 25 步 (更稳)
    python tools/benchmark.py --diffusion-steps 15     # 对比: 15 步 (更快)
    python tools/benchmark.py --text "长文本..."       # 自定义文本
    python tools/benchmark.py --prompt examples/voice_01.wav

输出:
    - GPU 架构与精度策略 (BF16 / FP16 / FP32 自动选择)
    - 各阶段耗时 (GPT / s2mel / BigVGAN) 与 RTF
    - RTF < 1.0 表示生成 1 秒音频耗时 < 1 秒 (实时)

说明:
    首次运行需已部署模型 (checkpoints/ 下有 config.yaml 与权重),
    参考音频缺省用 examples/voice_01.wav (自动下载示例)。
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch


def detect_platform() -> str:
    if os.path.isdir("/content"):
        return "Colab"
    if os.path.isdir("/kaggle"):
        return "Kaggle"
    return "Local"


def main():
    parser = argparse.ArgumentParser(description="IndexTTS-2.5 推理基准")
    parser.add_argument("--text", type=str,
                        default="大家好，欢迎体验 IndexTTS 2.5。"
                                "这是一段用于性能测试的中文文本，包含数字 2025 年、"
                                "技术术语 API 与 GPU，以及 WiFi 连接。")
    parser.add_argument("--prompt", type=str, default=None,
                        help="参考音频路径 (默认 examples/voice_01.wav)")
    parser.add_argument("--diffusion-steps", type=int, default=None,
                        help="CFM 扩散步数 (默认自动: 20)")
    parser.add_argument("--lang", type=str, default="ZH")
    parser.add_argument("--no-cuda-kernel", action="store_true",
                        help="禁用 BigVGAN CUDA kernel")
    args = parser.parse_args()

    print("=" * 60)
    print(f"IndexTTS-2.5 基准测试 · 平台: {detect_platform()}")
    print(f"PyTorch: {torch.__version__} · CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        dev = torch.cuda.get_device_properties(0)
        cap = torch.cuda.get_device_capability(0)
        print(f"GPU: {dev.name} · {dev.total_memory / 1024**3:.1f} GB · sm_{cap[0]}{cap[1]}")
        # 与 infer_v2_5 相同的精度策略
        if cap[0] >= 8:
            print("精度策略: BF16 (Ampere+ 原生支持)")
        else:
            print("精度策略: FP16 (旧架构自动回退, 提速)")
    print("=" * 60)

    from indextts.utils.examples_downloader import ensure_examples_available
    ensure_examples_available()
    prompt = args.prompt or "examples/voice_01.wav"

    from indextts.infer_v2_5 import IndexTTS2
    tts = IndexTTS2(
        cfg_path="checkpoints/config.yaml",
        model_dir="checkpoints",
        use_bf16=True,              # T4/P100/V100 会自动回退 FP16
        use_cuda_kernel=not args.no_cuda_kernel,
        use_qwen_emo=False,
    )
    print(f"实际精度: {'BF16' if tts.use_bf16 else ('FP16' if tts.use_fp16 else 'FP32')}"
          f" · CUDA kernel: {tts.use_cuda_kernel}")

    kwargs = {}
    if args.diffusion_steps:
        kwargs["diffusion_steps"] = args.diffusion_steps
    elif tts.use_fp16:
        kwargs["diffusion_steps"] = 20   # 旧架构默认 20 步
        print("扩散步数: 20 (默认)")

    print(f"参考音频: {prompt}")
    print(f"文本: {args.text[:60]}{'...' if len(args.text) > 60 else ''}")
    print("-" * 60)

    t0 = time.perf_counter()
    tts.infer(
        spk_audio_prompt=prompt,
        text=args.text,
        lang=args.lang,
        output_path="/tmp/benchmark_out.wav",
        verbose=True,
        **kwargs,
    )
    wall = time.perf_counter() - t0
    print("-" * 60)
    print(f"含模型加载总耗时: {wall:.2f}s (首次运行含权重加载, 服务模式无此项)")

    # 第二次调用测纯推理 (缓存命中)
    t1 = time.perf_counter()
    tts.infer(
        spk_audio_prompt=prompt,
        text=args.text,
        lang=args.lang,
        output_path="/tmp/benchmark_out2.wav",
        verbose=False,
        **kwargs,
    )
    pure = time.perf_counter() - t1
    print(f"纯推理耗时(缓存命中): {pure:.2f}s")


if __name__ == "__main__":
    main()
