#!/usr/bin/env bash
# =============================================================================
# IndexTTS-2.5 一键部署脚本 (Colab / Kaggle / 本地 Linux 通用)
#
# 用法:
#   bash setup.sh                          # 全部默认值
#   MODEL_SOURCE=modelscope bash setup.sh  # 走 ModelScope 下载
#   REPO_URL=... bash setup.sh             # 自定义仓库地址
#
# 环境变量:
#   REPO_URL      项目仓库地址 (默认本仓库: infinite-gaming-studio/index-tts)
#   REPO_DIR      本地目录名 (默认 index-tts)
#   MODEL_SOURCE  huggingface | modelscope (默认 huggingface)
#   HF_ENDPOINT   HuggingFace 镜像 (可选, 如 https://hf-mirror.com)
# =============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/infinite-gaming-studio/index-tts.git}"
REPO_DIR="${REPO_DIR:-index-tts}"
MODEL_SOURCE="${MODEL_SOURCE:-huggingface}"

# ---- 环境探测 (Colab / Kaggle / 本地) ----
if [ -d "/content" ]; then
  WORK_DIR="/content"
elif [ -d "/kaggle" ]; then
  WORK_DIR="/kaggle/working"
else
  WORK_DIR="$(pwd)"
fi

echo "==> [1/3] 克隆仓库: ${REPO_URL}"
mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"
if [ ! -d "${REPO_DIR}" ]; then
  git clone --depth 1 "${REPO_URL}" "${REPO_DIR}"
else
  echo "    已存在 ${REPO_DIR}, 跳过克隆"
fi
cd "${REPO_DIR}"

echo "==> [2/3] 安装 uv 并同步依赖 (含 webui/deepspeed extras)"
pip install -U uv -q
uv sync --all-extras

echo "==> [3/3] 下载 IndexTTS-2.5 权重 (来源: ${MODEL_SOURCE})"
case "${MODEL_SOURCE}" in
  modelscope)
    uv tool install modelscope -q
    modelscope download --model IndexTeam/IndexTTS-2.5 --local_dir checkpoints
    ;;
  huggingface)
    uv tool install huggingface-hub -q
    hf download IndexTeam/IndexTTS-2.5 --local-dir=checkpoints
    ;;
  *)
    echo "!! 未知 MODEL_SOURCE=${MODEL_SOURCE} (可选 huggingface|modelscope)" >&2
    exit 1
    ;;
esac

echo ""
echo "============================================================"
echo "  部署完成 ✓  仓库: ${WORK_DIR}/${REPO_DIR}"
echo "  下一步: 启动服务  ->  bash serve.sh  (或参考 deploy/README.md)"
echo "============================================================"
