#!/usr/bin/env bash
# =============================================================================
# IndexTTS-2.5 服务启动脚本 (Colab / Kaggle / 本地 Linux 通用)
#
# 用法:
#   bash serve.sh                          # 启动 WebUI + Cloudflare 隧道
#   SERVICE=api bash serve.sh              # 启动 API 服务 (FastAPI, 端口 8000)
#   SERVICE=both bash serve.sh             # 同时启动 API + WebUI
#   TUNNEL=ngrok bash serve.sh             # 改用 ngrok 隧道
#   TUNNEL=none bash serve.sh              # 仅本地, 不打隧道
#   PORT=7860 WEBUI_ARGS="--fp16" bash serve.sh
#
# 环境变量:
#   SERVICE     webui (默认) | api | both
#   TUNNEL      ngrok (默认) | cf (Cloudflare 免注册) | none
#   PORT        本地端口 (WebUI 默认 7860; API 默认 8000)
#   WEBUI_ARGS  追加给 webui.py 的参数 (如 "--fp16 --deepspeed")
#   API_ARGS    追加给 deploy/service.py 的参数 (如 "--qwen-emo --deepspeed")
#   NGROK_TOKEN ngrok authtoken (TUNNEL=ngrok 时建议设置, 否则免费额度受限)
#   INDEXTTS_API_TOKEN API 鉴权 Key; 默认固定(见启动日志), 可自定义或置空 "" 关闭
#   REPO_DIR    本地目录名 (默认 index-tts)
#   KEEPALIVE   1 (默认) 后台心跳防空闲断连 | 0 关闭
# =============================================================================
set -euo pipefail

SERVICE="${SERVICE:-webui}"
TUNNEL="${TUNNEL:-ngrok}"
PORT="${PORT:-}"
WEBUI_ARGS="${WEBUI_ARGS:-}"
API_ARGS="${API_ARGS:-}"
REPO_DIR="${REPO_DIR:-index-tts}"
KEEPALIVE="${KEEPALIVE:-1}"

# ---- 环境探测 (Colab / Kaggle / 本地) ----
if [ -d "/content" ]; then
  WORK_DIR="/content"
elif [ -d "/kaggle" ]; then
  WORK_DIR="/kaggle/working"
else
  WORK_DIR="$(pwd)"
fi
cd "${WORK_DIR}/${REPO_DIR}"

# ---- 按服务类型选择启动命令与默认端口 ----
case "${SERVICE}" in
  webui)
    PORT="${PORT:-7860}"
    LAUNCH_CMD="uv run --all-extras webui.py --host 0.0.0.0 --port ${PORT} ${WEBUI_ARGS}"
    LOG_FILE="webui.log"
    echo "==> [1/2] 后台启动 WebUI (http://127.0.0.1:${PORT})"
    ;;
  api)
    PORT="${PORT:-8000}"
    LAUNCH_CMD="uv run --all-extras python deploy/service.py --mode api --port ${PORT} ${API_ARGS}"
    LOG_FILE="api.log"
    echo "==> [1/2] 后台启动 API 服务 (http://127.0.0.1:${PORT}, /docs)"
    ;;
  both)
    PORT="${PORT:-8000}"
    LAUNCH_CMD="uv run --all-extras python deploy/service.py --mode both --port ${PORT} ${API_ARGS}"
    LOG_FILE="api.log"
    echo "==> [1/2] 后台启动 API + WebUI (http://127.0.0.1:${PORT}, /ui, /docs)"
    ;;
  *)
    echo "!! 未知 SERVICE=${SERVICE} (可选 webui|api|both)" >&2
    exit 1
    ;;
esac

# 注意: 必须 --all-extras, 否则 uv run 会按默认特性集重新同步, 剪掉 gradio(webui extra)
nohup ${LAUNCH_CMD} > "${LOG_FILE}" 2>&1 &

echo "==> 等待服务就绪 (最多 300 秒)..."
ready=""
for i in $(seq 1 60); do
  if curl -sf -o /dev/null "http://127.0.0.1:${PORT}"; then
    ready="yes"
    break
  fi
  sleep 5
done
if [ -z "${ready}" ]; then
  echo "!! 服务未在 300 秒内就绪, 最后日志:" >&2
  tail -30 "${LOG_FILE}" >&2
  exit 1
fi
echo "==> 服务已就绪: http://127.0.0.1:${PORT}"
# 从日志提取 API Key (service.py 启动横幅中打印), 方便直接复制调用
API_KEY=$(grep -m1 "API Key:" "${LOG_FILE}" | awk '{print $NF}')
if [ -n "${API_KEY}" ]; then
  echo "==> 🔑 API Key: ${API_KEY}"
  echo "    调用示例: curl -H \"Authorization: Bearer ${API_KEY}\" -F text='你好' -F spk_audio=@ref.wav http://127.0.0.1:${PORT}/api/tts"
fi
echo "==> 最近日志 (完整日志: tail -f ${LOG_FILE}):"
tail -n 20 "${LOG_FILE}" 2>/dev/null || true

# ---- 心跳保活: 周期性请求本地端口, 防止 Colab/Kaggle 空闲断连 ----
if [ "${KEEPALIVE}" = "1" ]; then
  (
    while true; do
      curl -sf -o /dev/null "http://127.0.0.1:${PORT}" && echo "[$(date '+%H:%M:%S')] keepalive ping ok" >> keepalive.log || true
      sleep 120
    done
  ) &
  KEEPALIVE_PID=$!
  echo "==> 心跳已启动 (PID ${KEEPALIVE_PID}, 每 120s ping 一次, KEEPALIVE=0 可关闭)"
fi

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
    # 官方 ngrok 二进制方式（比 pyngrok 更稳定，失败时有明确输出）
    if [ ! -x ./ngrok ]; then
      echo "    下载 ngrok 二进制..."
      curl -sL -o /tmp/ngrok.zip \
        "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.zip" || {
        echo "!! ngrok 下载失败，请检查网络或改用 TUNNEL=cf" >&2
        exit 1
      }
      (command -v unzip >/dev/null && unzip -o -q /tmp/ngrok.zip -d .) || {
        echo "!! 解压 ngrok 失败，请检查 unzip" >&2
        exit 1
      }
      chmod +x ./ngrok
    fi
    if [ -n "${NGROK_TOKEN:-}" ]; then
      echo "==> 配置 ngrok authtoken..."
      ./ngrok config add-authtoken "${NGROK_TOKEN}" 2>&1 | tail -3
    else
      echo "!! 未设置 NGROK_TOKEN，免费版隧道必须配置 authtoken" >&2
    fi
    echo "==> 启动 ngrok 隧道 (http://127.0.0.1:${PORT})..."
    # 必须 exec 前台运行：输出直接进 serve.sh 的 stdout（serve_console.log），
    # notebook 轮询 serve_console.log 才能提取到 Public URL。
    # 不能重定向到 ngrok.log——notebook 看不到那个文件，会报「获取不到公网 URL」。
    exec ./ngrok http "${PORT}" --log=stdout
    ;;
  none)
    echo "==> 未启用隧道, 仅本机可访问: http://127.0.0.1:${PORT}"
    echo "    如需公网访问, 重启时加 TUNNEL=cf 或 TUNNEL=ngrok"
    tail -f "${LOG_FILE}"
    ;;
  *)
    echo "!! 未知 TUNNEL=${TUNNEL} (可选 cf|ngrok|none)" >&2
    exit 1
    ;;
esac
