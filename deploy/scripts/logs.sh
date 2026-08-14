#!/usr/bin/env bash
# =============================================================================
# IndexTTS-2.5 日志查看脚本 (Colab / Kaggle / 本地通用)
#
# 用法:
#   bash logs.sh            # 查看 WebUI 日志 (webui.log)
#   bash logs.sh api        # 查看 API 服务日志 (api.log)
#   bash logs.sh api 50     # 查看最后 50 行
#   bash logs.sh -f         # 实时跟踪 (等价 tail -f)
#   bash logs.sh api -f     # 实时跟踪 API 日志
#
# 参数:
#   $1  服务类型: webui (默认) | api | both(同 api.log)
#   $2  -f 实时跟踪 | 行数 (默认 50)
# =============================================================================
set -euo pipefail

SERVICE_ARG="${1:-webui}"
MODE_ARG="${2:-50}"

# ---- 环境探测 (Colab / Kaggle / 本地) ----
if [ -d "/content" ]; then
  WORK_DIR="/content"
elif [ -d "/kaggle" ]; then
  WORK_DIR="/kaggle/working"
else
  WORK_DIR="$(pwd)"
fi
REPO_DIR="${REPO_DIR:-index-tts}"
cd "${WORK_DIR}/${REPO_DIR}"

case "${SERVICE_ARG}" in
  webui) LOG_FILE="webui.log" ;;
  api|both) LOG_FILE="api.log" ;;
  *)
    echo "!! 未知服务类型: ${SERVICE_ARG} (可选 webui|api|both)" >&2
    exit 1
    ;;
esac

if [ ! -f "${LOG_FILE}" ]; then
  echo "!! 找不到日志文件: ${LOG_FILE} (服务可能尚未启动)" >&2
  exit 1
fi

echo "==> 日志文件: ${LOG_FILE}"
if [ "${MODE_ARG}" = "-f" ]; then
  tail -f "${LOG_FILE}"
else
  tail -n "${MODE_ARG}" "${LOG_FILE}"
fi
