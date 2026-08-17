"""
IndexTTS-2.5 API 服务 (FastAPI)
================================

参考旧版 `deploy/service.py` 的 API 文档重新实现, 底层引擎升级为 **IndexTTS-2.5**
(`indextts.infer_v2_5.IndexTTS2`), 并加入 2.5 的新特性:

- 多语言: ``lang`` 参数 (ZH / EN / JA / ES / AR / ZHEN)
- 时长/语速控制: ``duration_factor`` (0.5 - 2.0)
- Qwen 情感文本 (emo_mode=3) 需在启动时加 ``--qwen-emo``
- BF16 半精度 (2.5 默认, 旧版为 FP16)
- 加速选项: ``--deepspeed`` / ``--cuda-kernel`` / ``--accel`` / ``--torch-compile``
- 可选 JSON (base64) 响应, 线程锁保证并发请求安全

依赖: fastapi / uvicorn / python-multipart (随 ``uv sync --all-extras`` 一并安装)。

用法:
    uv run --all-extras python deploy/service.py --mode api --port 8000
    uv run --all-extras python deploy/service.py --mode both          # API + WebUI(/ui)
"""

import os
import sys
import json
import time
import base64
import argparse
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import torch
    from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status
    from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    import uvicorn
except ImportError as e:
    raise SystemExit(
        f"[IndexTTS-2.5 API] 缺少依赖: {e}\n"
        f"请先在项目根目录运行:  uv sync --all-extras  (fastapi/uvicorn 随 webui 依赖安装)"
    )

try:
    import gradio as gr
    _HAS_GRADIO = True
except ImportError:
    _HAS_GRADIO = False

from indextts.infer_v2_5 import IndexTTS2

DEFAULT_LANGS = ("ZH", "EN", "JA", "ES", "AR", "ZHEN")
DEFAULT_API_TOKEN = "indextts-fixed-key-2026"  # 默认固定鉴权 Key (见启动日志)


class TTSConfig:
    """IndexTTS-2.5 服务配置"""

    def __init__(self):
        self.repo_dir = self._get_repo_dir()
        self.cfg_path = os.path.join(self.repo_dir, "checkpoints/config.yaml")
        self.model_dir = os.path.join(self.repo_dir, "checkpoints")
        self.port = 8000
        self.mode = "api"  # api | webui | both
        self.use_bf16 = True
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.use_deepspeed = False
        self.use_cuda_kernel = None
        self.use_accel = False
        self.use_torch_compile = False
        self.use_qwen_emo = False
        # 鉴权: 默认固定 Key (方便直接调用, 见启动日志);
        #   覆盖:  export INDEXTTS_API_TOKEN=my-key  (自定义/更安全)
        #   关闭:  export INDEXTTS_API_TOKEN=""       (仅建议内网/本机)
        # 注意: 本仓库公开时默认 Key 同样公开, 生产环境请用 env 覆盖
        raw_token = os.environ.get("INDEXTTS_API_TOKEN")
        if raw_token is None:
            self.api_token = DEFAULT_API_TOKEN
        elif raw_token == "":
            self.api_token = None
        else:
            self.api_token = raw_token
        self.default_lang = "ZH"

    def _get_repo_dir(self):
        repo_dir = os.environ.get("INDEXTTS_REPO_DIR")
        if repo_dir:
            return repo_dir
        config_file = "/tmp/notebook_config.json"
        if os.path.exists(config_file):
            with open(config_file) as f:
                return json.load(f).get("repo_dir", str(Path(__file__).resolve().parent.parent))
        return str(Path(__file__).resolve().parent.parent)


class TTSApp:
    """IndexTTS-2.5 API + WebUI 应用服务"""

    def __init__(self, config: TTSConfig = None):
        self.config = config or TTSConfig()
        self.tts = None
        self.app = FastAPI(title="IndexTTS-2.5", version="2.5.0")
        self.security = HTTPBearer(auto_error=False)
        # IndexTTS2 内部维护说话人/情感缓存, 并发请求必须串行化
        self._infer_lock = threading.Lock()
        self._setup_routes()

    # ------------------------------------------------------------------ 加载
    def load_model(self):
        start = time.perf_counter()
        cfg = self.config
        print("=" * 60, flush=True)
        print("🔄 加载 IndexTTS-2.5 模型...", flush=True)
        print(f"  配置: {cfg.cfg_path}", flush=True)
        print(f"  模型: {cfg.model_dir}", flush=True)
        print(f"  设备: {cfg.device}  BF16: {cfg.use_bf16}", flush=True)
        print("=" * 60, flush=True)

        if not os.path.exists(cfg.cfg_path):
            raise FileNotFoundError(f"找不到配置文件: {cfg.cfg_path}")

        self.tts = IndexTTS2(
            cfg_path=cfg.cfg_path,
            model_dir=cfg.model_dir,
            use_bf16=cfg.use_bf16,
            device=cfg.device,
            use_cuda_kernel=cfg.use_cuda_kernel,
            use_deepspeed=cfg.use_deepspeed,
            use_accel=cfg.use_accel,
            use_torch_compile=cfg.use_torch_compile,
            use_qwen_emo=cfg.use_qwen_emo,
        )
        print(f"✅ 模型加载完成, 耗时 {time.perf_counter() - start:.1f}s", flush=True)

    # ------------------------------------------------------------------ 鉴权
    def _verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))):
        if not self.config.api_token:
            return True
        if credentials is None or credentials.credentials != self.config.api_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return True

    # ------------------------------------------------------------------ 路由
    def _setup_routes(self):

        @self.app.get("/")
        async def root():
            html = """
            <html><body style="font-family:sans-serif;padding:2rem">
            <h1>🎙️ IndexTTS-2.5 API 服务</h1>
            <p>API: <code>POST /api/tts</code> · 健康检查: <code>GET /api/health</code></p>
            <p>文档: <a href="/docs">/docs (Swagger)</a> · WebUI: <a href="/ui">/ui</a></p>
            </body></html>"""
            return HTMLResponse(content=html)

        @self.app.get("/api/health")
        async def health():
            t = self.tts
            return {
                "status": "ok" if t is not None else "starting",
                "model": "IndexTTS-2.5",
                "version": "2.5.0",
                "device": str(t.device) if t else self.config.device,
                "loaded": t is not None,
                "bf16": bool(getattr(t, "use_bf16", False)) if t else self.config.use_bf16,
                "low_vram": bool(getattr(t, "low_vram", False)) if t else False,
                "qwen_emo": t is not None and getattr(t, "qwen_emo", None) is not None,
                "languages": list(DEFAULT_LANGS),
            }

        @self.app.post("/api/tts")
        async def tts(
            text: str = Form(..., description="要合成的文本"),
            spk_audio: UploadFile = File(..., description="音色参考音频 (WAV/MP3 等)"),
            lang: str = Form("ZH", description="语言: ZH/EN/JA/ES/AR/ZHEN"),
            emo_mode: int = Form(0, description="情感模式: 0=与音色相同, 1=情感参考音频, 2=情感向量, 3=情感文本(需 --qwen-emo)"),
            emo_alpha: float = Form(1.0, description="情感强度 (0.0-2.0)"),
            emo_audio: UploadFile = File(None, description="情感参考音频 (emo_mode=1)"),
            emo_vector: str = Form(None, description="8维情感向量 JSON (emo_mode=2) [喜,怒,哀,惧,厌恶,低落,惊喜,平静]"),
            emo_text: str = Form(None, description="情感描述文本 (emo_mode=3)"),
            use_random: bool = Form(False, description="情感向量随机采样 (emo_mode=2)"),
            duration_factor: float = Form(1.0, description="时长/语速因子 (0.5-2.0, 2.5 新特性)"),
            do_sample: bool = Form(True),
            top_p: float = Form(0.8),
            top_k: int = Form(30),
            temperature: float = Form(0.8),
            length_penalty: float = Form(0.0),
            num_beams: int = Form(3),
            repetition_penalty: float = Form(10.0),
            max_mel_tokens: int = Form(1500),
            max_text_tokens_per_segment: int = Form(120),
            response_format: str = Form("wav", description="wav | json (json 返回 base64)"),
            _auth: bool = Depends(self._verify_token),
        ):
            """语音合成 (音色克隆 + 4 种情感控制 + 多语言 + 语速控制)"""
            if self.tts is None:
                return JSONResponse(status_code=503, content={"error": "模型未加载"})

            # ---- 参数校验 ----
            if not text or not text.strip():
                return JSONResponse(status_code=400, content={"error": "text 不能为空"})
            lang = lang.upper()
            if lang not in DEFAULT_LANGS:
                return JSONResponse(status_code=400, content={"error": f"lang 必须为 {DEFAULT_LANGS} 之一"})

            tmp_files = []

            def _save_upload(upload: UploadFile, suffix=".wav"):
                tmp = NamedTemporaryFile(delete=False, suffix=suffix)
                tmp_files.append(tmp.name)
                import shutil
                shutil.copyfileobj(upload.file, tmp)
                tmp.close()
                return tmp.name

            try:
                spk_path = _save_upload(spk_audio)

                # 情感参考音频 (mode=1)
                emo_audio_prompt = None
                if emo_mode == 1:
                    if emo_audio is None:
                        return JSONResponse(status_code=400, content={"error": "emo_mode=1 需要上传 emo_audio"})
                    emo_audio_prompt = _save_upload(emo_audio)

                # 情感向量 (mode=2)
                vec = None
                if emo_mode == 2:
                    if not emo_vector:
                        return JSONResponse(status_code=400, content={"error": "emo_mode=2 需要传入 emo_vector"})
                    try:
                        vec = json.loads(emo_vector)
                    except json.JSONDecodeError:
                        return JSONResponse(status_code=400, content={"error": "emo_vector 必须是合法的 JSON 数组"})
                    if not isinstance(vec, list) or len(vec) != 8:
                        return JSONResponse(status_code=400, content={"error": "emo_vector 必须是长度为8的JSON数组 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]"})
                    vec = self.tts.normalize_emo_vec([float(x) for x in vec], apply_bias=True)

                # 情感文本 (mode=3)
                use_emo_text = emo_mode == 3
                if use_emo_text and not emo_text:
                    emo_text = None  # 缺省时使用主文本

                # 生成参数
                generation_kwargs = {
                    "do_sample": bool(do_sample),
                    "top_p": float(top_p),
                    "top_k": int(top_k) if int(top_k) > 0 else None,
                    "temperature": float(temperature),
                    "length_penalty": float(length_penalty),
                    "num_beams": int(num_beams),
                    "repetition_penalty": float(repetition_penalty),
                    "max_mel_tokens": int(max_mel_tokens),
                }

                # ---- 推理 (加锁, 保护内部缓存) ----
                out_path = NamedTemporaryFile(delete=False, suffix=".wav").name
                tmp_files.append(out_path)
                with self._infer_lock:
                    self.tts.infer(
                        spk_audio_prompt=spk_path,
                        text=text,
                        lang=lang,
                        output_path=out_path,
                        emo_audio_prompt=emo_audio_prompt,
                        emo_alpha=emo_alpha,
                        emo_vector=vec,
                        use_emo_text=use_emo_text,
                        emo_text=emo_text,
                        use_random=use_random,
                        duration_factor=duration_factor,
                        verbose=False,
                        max_text_tokens_per_segment=int(max_text_tokens_per_segment),
                        **generation_kwargs,
                    )

                if response_format == "json":
                    with open(out_path, "rb") as f:
                        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
                    return JSONResponse(content={
                        "audio_base64": audio_b64,
                        "sample_rate": 22050,
                        "format": "wav",
                        "lang": lang,
                    })
                return FileResponse(out_path, media_type="audio/wav", filename="index_tts_2_5.wav")
            except HTTPException:
                raise
            except RuntimeError as e:
                return JSONResponse(status_code=400, content={"error": str(e)})
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})
            finally:
                for f in tmp_files:
                    try:
                        os.unlink(f)
                    except OSError:
                        pass

    # ------------------------------------------------------------------ WebUI
    def setup_webui(self):
        """挂载精简 Gradio WebUI 到 /ui (与 API 共享同一个模型实例)"""
        if self.tts is None:
            raise RuntimeError("模型未加载, 无法设置 WebUI")
        if not _HAS_GRADIO:
            raise RuntimeError("缺少 gradio, 请用 uv sync --all-extras 安装")

        def ui_tts(text, audio, lang, emo_mode, emo_audio, emo_weight,
                   vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8,
                   emo_text, emo_random, duration_factor):
            vec = None
            emo_audio_prompt = None
            if emo_mode == 1 and emo_audio is not None:
                emo_audio_prompt = emo_audio
            if emo_mode == 2:
                vec = self.tts.normalize_emo_vec(
                    [vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8], apply_bias=True)
            use_emo_text = emo_mode == 3
            if use_emo_text and not emo_text:
                emo_text = None

            out = NamedTemporaryFile(delete=False, suffix=".wav").name
            try:
                with self._infer_lock:
                    self.tts.infer(
                        spk_audio_prompt=audio,
                        text=text,
                        lang=lang,
                        output_path=out,
                        emo_audio_prompt=emo_audio_prompt,
                        emo_alpha=emo_weight,
                        emo_vector=vec,
                        use_emo_text=use_emo_text,
                        emo_text=emo_text,
                        use_random=emo_random,
                        duration_factor=duration_factor,
                        verbose=False,
                    )
                return out
            finally:
                pass

        def on_mode_change(emo_mode):
            show_audio = emo_mode == 1
            show_vector = emo_mode == 2
            show_text = emo_mode == 3
            return (
                gr.update(visible=show_audio),
                gr.update(visible=show_vector),
                gr.update(visible=show_text),
                gr.update(visible=emo_mode in (2,)),
                gr.update(visible=emo_mode in (1, 2, 3)),
            )

        with gr.Blocks(title="IndexTTS-2.5") as demo:
            gr.Markdown("# IndexTTS-2.5")
            with gr.Row():
                with gr.Column():
                    txt = gr.Textbox(label="文本", lines=4)
                    aud = gr.Audio(label="音色参考音频", type="filepath")
                    lang = gr.Dropdown(choices=list(DEFAULT_LANGS), value=self.config.default_lang, label="语言")
                    emo_mode = gr.Radio(
                        choices=["与音色参考音频相同", "使用情感参考音频", "使用情感向量控制", "使用情感描述文本控制"],
                        type="index", value="与音色参考音频相同", label="情感控制方式")
                    with gr.Group(visible=False) as emo_audio_group:
                        emo_audio = gr.Audio(label="上传情感参考音频", type="filepath")
                    with gr.Row(visible=False) as emo_random_group:
                        emo_random = gr.Checkbox(label="情感随机采样", value=False)
                    with gr.Group(visible=False) as emo_vector_group:
                        with gr.Row():
                            vecs = []
                            labels = ["喜", "怒", "哀", "惧", "厌恶", "低落", "惊喜", "平静"]
                            for i in range(4):
                                vecs.append(gr.Slider(label=labels[i], minimum=0.0, maximum=1.0, value=0.0, step=0.05))
                            for i in range(4, 8):
                                vecs.append(gr.Slider(label=labels[i], minimum=0.0, maximum=1.0, value=0.0, step=0.05))
                    with gr.Group(visible=False) as emo_text_group:
                        emo_text = gr.Textbox(label="情感描述文本", placeholder="请输入情绪描述(留空则使用主文本)", value="")
                    with gr.Group(visible=False) as emo_weight_group:
                        emo_weight = gr.Slider(label="情感权重", minimum=0.0, maximum=2.0, value=1.0, step=0.01)
                    duration_factor = gr.Slider(label="语速/时长因子", minimum=0.5, maximum=2.0, value=1.0, step=0.05)
                    btn = gr.Button("生成", variant="primary")
                with gr.Column():
                    gr.Markdown("### 生成结果")
                    out_audio = gr.Audio(label="结果", type="filepath")

            emo_mode.change(
                on_mode_change,
                inputs=[emo_mode],
                outputs=[emo_audio_group, emo_vector_group, emo_text_group, emo_random_group, emo_weight_group],
            )
            btn.click(
                ui_tts,
                [txt, aud, lang, emo_mode, emo_audio, emo_weight, *vecs, emo_text, emo_random, duration_factor],
                out_audio,
            )

        self.app = gr.mount_gradio_app(self.app, demo, path="/ui")

    # ------------------------------------------------------------------ 启动
    def run(self):
        print("\n" + "=" * 60, flush=True)
        print(f"🚀 IndexTTS-2.5 服务启动: http://0.0.0.0:{self.config.port}", flush=True)
        print(f"  API 文档: /docs  健康检查: /api/health  合成: POST /api/tts", flush=True)
        if self.config.mode in ("webui", "both"):
            print(f"  WebUI: /ui", flush=True)
        if self.config.api_token:
            print(f"  鉴权: Bearer token 已启用", flush=True)
            print(f"  🔑 API Key: {self.config.api_token}", flush=True)
            print(f"  curl 示例: curl -H \"Authorization: Bearer {self.config.api_token}\" -F text='你好' -F spk_audio=@ref.wav http://127.0.0.1:{self.config.port}/api/tts", flush=True)
        else:
            print(f"  鉴权: 已关闭 (INDEXTTS_API_TOKEN 显式置空)", flush=True)
        print("=" * 60 + "\n", flush=True)
        uvicorn.run(self.app, host="0.0.0.0", port=self.config.port)


def main():
    parser = argparse.ArgumentParser(description="IndexTTS-2.5 API 服务")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--mode", choices=["api", "webui", "both"], default="api",
                        help="api 仅API | webui 仅WebUI | both 两者")
    parser.add_argument("--repo-dir", type=str, default=None)
    parser.add_argument("--model-dir", type=str, default=None)
    parser.add_argument("--no-bf16", action="store_true", help="禁用 BF16 (2.5 默认开启)")
    parser.add_argument("--device", type=str, default=None, help="cuda:0 / cpu 等")
    parser.add_argument("--deepspeed", action="store_true")
    parser.add_argument("--cuda-kernel", action="store_true", help="启用 BigVGAN CUDA kernel")
    parser.add_argument("--accel", action="store_true", help="启用 GPT2 加速引擎")
    parser.add_argument("--torch-compile", action="store_true")
    parser.add_argument("--qwen-emo", action="store_true", help="加载 QwenEmotion (emo_mode=3 需要)")
    parser.add_argument("--default-lang", default="ZH", choices=list(DEFAULT_LANGS))

    args = parser.parse_args()
    if args.repo_dir:
        os.environ["INDEXTTS_REPO_DIR"] = args.repo_dir

    config = TTSConfig()
    config.port = args.port
    config.mode = args.mode
    config.use_bf16 = not args.no_bf16
    config.use_deepspeed = args.deepspeed
    config.use_accel = args.accel
    config.use_torch_compile = args.torch_compile
    config.use_qwen_emo = args.qwen_emo
    config.default_lang = args.default_lang
    if args.device:
        config.device = args.device
    if args.model_dir:
        config.model_dir = args.model_dir
    if args.cuda_kernel:
        config.use_cuda_kernel = True
    # CPU 设备强制关 BF16/加速
    if config.device.startswith("cpu"):
        config.use_bf16 = False
        config.use_cuda_kernel = False

    app = TTSApp(config)
    app.load_model()
    if config.mode in ("webui", "both"):
        print("🎨 挂载 WebUI 到 /ui ...", flush=True)
        app.setup_webui()
    app.run()


if __name__ == "__main__":
    main()
