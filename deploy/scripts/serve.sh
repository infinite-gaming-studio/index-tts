#!/usr/bin/env bash
# =============================================================================
# IndexTTS-2.5 服务启动脚本 (Colab / Kaggle / 本地 Linux 通用)
#
# 用法:
#   bash serve.sh                          # 启动 WebUI + Cloudflare 隧道
#   TUNNEL=ngrok bash serve.sh             # 改用 ngrok 隧道
#   TUNNEL=none bash serve.sh              # 仅本地, 不打隧道
#   PORT=7860 WEBUI_ARGS="--fp16" bash serve.sh
#
# 环境变量:
#   TUNNEL      cf (默认, Cloudflare 免注册) | ngrok | none
#   PORT        本地端口 (默认 7860)
#   WEBUI_ARGS  追加给 webui.py 的参数 (如 "--fp16 --deepspeed")
#   NGROK_TOKEN ngrok authtoken (TUNNEL=ngrok 时建议设置, 否则免费额度受限)
#   REPO_DIR    本地目录名 (默认 index-tts)
# =============================================================================
set -euo pipefail

TUNNEL="${TUNNEL:-cf}"
PORT="${PORT:-7860}"
WEBUI_ARGS="${WEBUI_ARGS:-}"
REPO_DIR="${REPO_DIR:-index-tts}"

# ---- 环境探测 (Colab / Kaggle / 本地) ----
if [ -d "/content" ]; then
  WORK_DIR="/content"
elif [ -d "/kaggle" ]; then
  WORK_DIR="/kaggle/working"
else
  WORK_DIR="$(pwd)"
fi
cd "${WORK_DIR}/${REPO_DIR}"

echo "==> [1/2] 后台启动 WebUI (http://127.0.0.1:${PORT})"
# webui.py 默认 IndexTTS-2.5, 权重目录 ./checkpoints
nohup uv run webui.py --host 0.0.0.0 --port "${PORT}" ${WEBUI_ARGS} > webui.log 2>&1 &

echo "==> 等待 WebUI 就绪 (最多 300 秒)..."
ready=""
for i in $(seq 1 60); do
  if curl -sf -o /dev/null "http://127.0.0.1:${PORT}"; then
    ready="yes"
    break
  fi
  sleep 5
done
if [ -z "${ready}" ]; then
  echo "!! WebUI 未在 300 秒内就绪, 最后日志:" >&2
  tail -30 webui.log >&2
  exit 1
fi
echo "==> WebUI 已就绪: http://127.0.0.1:${PORT}"

echo "==> [2/2] 建立公网隧道 (方式: ${TUNNEL})"
case "${TUNNEL}" in
  cf)
    # Cloudflare 快速隧道: 免注册, 直接生成 trycloudflare.com 公网链接
    if [ ! -x ./cloudflared ]; then
      echo "    下载 cloudflared..."
      curl -sL -o ./cloudflared \
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
      chmod +x ./cloudflared
    fi
    ./cloudflared tunnel --url "http://127.0.0.1:${PORT}"
    ;;
  ngrok)
    pip install -q pyngrok
    if [ -n "${NGROK_TOKEN:-}" ]; then
      python -c "from pyngrok import ngrok; ngrok.set_auth_token('${NGROK_TOKEN}')"
    fi
    python -c "from pyngrok import ngrok; print('Public URL:', ngrok.connect(${PORT}).public_url)"
    echo "==> ngrok 隧道已建立 (Ctrl+C 退出)"
    sleep infinity
    ;;
  none)
    echo "==> 未启用隧道, 仅本机可访问: http://127.0.0.1:${PORT}"
    echo "    如需公网访问, 重启时加 TUNNEL=cf 或 TUNNEL=ngrok"
    tail -f webui.log
    ;;
  *)
    echo "!! 未知 TUNNEL=${TUNNEL} (可选 cf|ngrok|none)" >&2
    exit 1
    ;;
esac
