"""
IndexTTS2 部署服务核心
处理模型加载、API和WebUI服务
"""

import os
import sys
import json
import argparse
import torch
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Form, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uvicorn
import shutil
import gradio as gr
from tempfile import NamedTemporaryFile

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from indextts.infer_v2 import IndexTTS2


class TTSConfig:
    """配置类"""
    def __init__(self):
        self.repo_dir = self._get_repo_dir()
        self.cfg_path = os.path.join(self.repo_dir, "checkpoints/config.yaml")
        self.model_dir = os.path.join(self.repo_dir, "checkpoints")
        self.port = 8000
        self.mode = "both"  # api | webui | both
        self.use_fp16 = True
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.api_token = os.environ.get("INDEXTTS_API_TOKEN")  # API鉴权token

    def _get_repo_dir(self):
        """获取项目根目录"""
        # 方式1: 环境变量
        repo_dir = os.environ.get("INDEXTTS_REPO_DIR")
        if repo_dir:
            return repo_dir

        # 方式2: 配置文件
        config_file = "/tmp/notebook_config.json"
        if os.path.exists(config_file):
            with open(config_file) as f:
                config = json.load(f)
            return config.get("repo_dir", "/tmp/index-tts")

        # 方式3: 相对路径
        return str(Path(__file__).parent.parent)


class TTSApp:
    """TTS应用服务"""

    def __init__(self, config: TTSConfig = None):
        self.config = config or TTSConfig()
        self.tts = None
        self.app = FastAPI(title="IndexTTS2")
        self.security = HTTPBearer(auto_error=False)
        self._setup_routes()

    def load_model(self):
        """加载模型"""
        import time
        start_time = time.time()

        print("="*60)
        print("🔄 开始加载模型...")
        print(f" 配置文件: {self.config.cfg_path}")
        print(f" 模型目录: {self.config.model_dir}")
        print(f" 设备: {self.config.device}")
        print(f" FP16: {self.config.use_fp16}")
        print("="*60, flush=True)

        if not os.path.exists(self.config.cfg_path):
            raise FileNotFoundError(f"找不到配置文件: {self.config.cfg_path}")

        # 加载模型（简化版本，无加速选项）
        self.tts = IndexTTS2(
            cfg_path=self.config.cfg_path,
            model_dir=self.config.model_dir,
            use_fp16=self.config.use_fp16,
            device=self.config.device
        )

        elapsed = time.time() - start_time
        print("="*60)
        print(f"✅ 模型加载完成!")
        print(f" 耗时: {elapsed:.1f}秒")
        print(f" 设备: {self.config.device}")
        print("="*60, flush=True)

    def _verify_token(self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))):
        """验证API Token"""
        # 如果没有配置token，则无需鉴权
        if not self.config.api_token:
            return True

        # 检查token
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if credentials.credentials != self.config.api_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return True

    def _setup_routes(self):
        """设置路由"""

        @self.app.post("/api/tts")
        async def tts(
            text: str = Form(...),
            spk_audio: UploadFile = File(...),
            emo_mode: int = Form(0, description="情感控制模式: 0=与音色相同, 1=情感参考音频, 2=情感向量, 3=情感文本(实验)"),
            emo_alpha: float = Form(1.0, description="情感强度系数 (0.0-2.0)"),
            emo_audio: UploadFile = File(None, description="情感参考音频 (emo_mode=1时使用)"),
            emo_vector: str = Form(None, description="8维情感向量JSON数组 [喜,怒,哀,惧,厌恶,低落,惊喜,平静], emo_mode=2时使用"),
            emo_text: str = Form(None, description="情感描述文本, emo_mode=3时使用"),
            use_random: bool = Form(False, description="情感随机采样 (emo_mode=2时可用)"),
            speed: float = Form(1.0, description="语速调节系数 (0.5-2.0, 默认1.0)"),
            target_length_ms: int = Form(None, description="绝对目标时长毫秒数 (可选)"),
            do_sample: bool = Form(True),
            top_p: float = Form(0.8),
            top_k: int = Form(30),
            temperature: float = Form(0.8),
            length_penalty: float = Form(0.0),
            num_beams: int = Form(3),
            repetition_penalty: float = Form(10.0),
            max_mel_tokens: int = Form(1500),
            max_text_tokens_per_segment: int = Form(120),
            authenticated: bool = Depends(self._verify_token)
        ):
            """TTS API接口 (需要token鉴权)

            情感控制模式:
              0 - 与音色参考音频相同 (默认, 使用说话人的声音情感)
              1 - 使用情感参考音频 (需上传 emo_audio)
              2 - 使用情感向量控制 (需传入 emo_vector, 如 [0.8,0,0,0,0,0,0,0] 表示开心)
              3 - 使用情感描述文本控制 (实验性, 需传入 emo_text)
            """
            try:
                if self.tts is None:
                    return JSONResponse(
                        status_code=503,
                        content={"error": "模型未加载"}
                    )

                # 保存说话人参考音频
                with NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    shutil.copyfileobj(spk_audio.file, tmp)
                    spk_path = tmp.name

                # 处理情感参考音频 (mode=1)
                emo_audio_prompt = None
                if emo_mode == 1 and emo_audio is not None:
                    with NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                        shutil.copyfileobj(emo_audio.file, tmp)
                        emo_audio_prompt = tmp.name

                # 处理情感向量 (mode=2)
                vec = None
                if emo_mode == 2 and emo_vector is not None:
                    import json as _json
                    vec = _json.loads(emo_vector)
                    if not isinstance(vec, list) or len(vec) != 8:
                        return JSONResponse(
                            status_code=400,
                            content={"error": "emo_vector 必须是长度为8的JSON数组 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]"}
                        )
                    vec = self.tts.normalize_emo_vec(vec, apply_bias=True)

                # 处理情感文本 (mode=3)
                use_emo_text = (emo_mode == 3)
                if emo_text == "":
                    emo_text = None

                # 构建生成参数
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

                # 生成音频
                output = "/tmp/out.wav"
                target_len_val = None
                if target_length_ms is not None and target_length_ms > 0:
                    target_len_val = int(target_length_ms)

                self.tts.infer(
                    spk_audio_prompt=spk_path,
                    text=text,
                    output_path=output,
                    emo_audio_prompt=emo_audio_prompt,
                    emo_alpha=emo_alpha,
                    emo_vector=vec,
                    use_emo_text=use_emo_text,
                    emo_text=emo_text,
                    use_random=use_random,
                    verbose=False,
                    max_text_tokens_per_segment=int(max_text_tokens_per_segment),
                    speed=float(speed),
                    target_length_ms=target_len_val,
                    **generation_kwargs
                )
                os.unlink(spk_path)
                if emo_audio_prompt is not None:
                    os.unlink(emo_audio_prompt)

                return FileResponse(output, media_type="audio/wav")
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e)}
                )

        @self.app.get("/api/health")
        async def health():
            """健康检查 (公开接口，无需鉴权)"""
            return {
                "status": "ok",
                "model": "IndexTTS2",
                "device": str(self.tts.device if self.tts else "not loaded"),
                "loaded": self.tts is not None
            }

        @self.app.get("/")
        async def root():
            """首页"""
            return HTMLResponse(content="""
            <h1>🎙️ IndexTTS2 服务</h1>
            <p>API: <code>POST /api/tts</code> | WebUI: <a href="/ui">/ui</a> | Docs: <a href="/docs">/docs</a></p>
            """)

    def setup_webui(self):
        """配置WebUI - 完整支持4种情感控制模式"""
        if self.tts is None:
            raise RuntimeError("模型未加载，无法设置WebUI")

        def ui_tts(text, audio, emo_mode, emo_audio, emo_weight,
                   vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8,
                   emo_text, emo_random,
                   speed, target_length_ms,
                   do_sample, top_p, top_k, temperature,
                   length_penalty, num_beams, repetition_penalty, max_mel_tokens,
                   max_text_tokens_per_segment):
            import time
            import base64
            out = "/tmp/tts_output.wav"

            # 情感参考音频
            emo_audio_prompt = None
            if emo_mode == 1 and emo_audio is not None:
                emo_audio_prompt = emo_audio

            # 情感向量
            vec = None
            if emo_mode == 2:
                vec = [vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8]
                vec = self.tts.normalize_emo_vec(vec, apply_bias=True)

            # 情感文本
            use_emo_text = (emo_mode == 3)
            if emo_text == "":
                emo_text = None

            kwargs = {
                "do_sample": bool(do_sample),
                "top_p": float(top_p),
                "top_k": int(top_k) if int(top_k) > 0 else None,
                "temperature": float(temperature),
                "length_penalty": float(length_penalty),
                "num_beams": int(num_beams),
                "repetition_penalty": float(repetition_penalty),
                "max_mel_tokens": int(max_mel_tokens),
            }

            target_len_val = None
            if target_length_ms is not None and target_length_ms > 0:
                target_len_val = int(target_length_ms)

            self.tts.infer(
                spk_audio_prompt=audio,
                text=text,
                output_path=out,
                emo_audio_prompt=emo_audio_prompt,
                emo_alpha=emo_weight,
                emo_vector=vec,
                use_emo_text=use_emo_text,
                emo_text=emo_text,
                use_random=emo_random,
                verbose=False,
                max_text_tokens_per_segment=int(max_text_tokens_per_segment),
                speed=float(speed),
                target_length_ms=target_len_val,
                **kwargs
            )
            # 读取并转为base64
            with open(out, 'rb') as f:
                audio_bytes = f.read()
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            # 使用HTML5 audio标签播放base64音频
            html = f'''<audio controls style="width:100%;" autoplay>
            <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
            您的浏览器不支持音频播放。
            '''
            return html

        def on_mode_change(emo_mode):
            """根据情感模式切换UI可见性"""
            if emo_mode == 1:  # 情感参考音频
                return (gr.update(visible=True),   # emo_audio_group
                        gr.update(visible=False),   # emo_vector_group
                        gr.update(visible=False),   # emo_text_group
                        gr.update(visible=False),   # emo_random_group
                        gr.update(visible=True))    # emo_weight_group
            elif emo_mode == 2:  # 情感向量
                return (gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=True))
            elif emo_mode == 3:  # 情感文本
                return (gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=True),
                        gr.update(visible=False),
                        gr.update(visible=True))
            else:  # 0: 与音色相同
                return (gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False),
                        gr.update(visible=False))

        with gr.Blocks(title="IndexTTS2") as demo:
            gr.Markdown("# IndexTTS2")
            with gr.Row():
                with gr.Column():
                    txt = gr.Textbox(label="文本", lines=4)
                    aud = gr.Audio(label="音色参考音频", type="filepath")

                    # 情感控制模式
                    emo_mode = gr.Radio(
                        choices=["与音色参考音频相同", "使用情感参考音频", "使用情感向量控制", "使用情感描述文本控制(实验)"],
                        type="index",
                        value="与音色参考音频相同",
                        label="情感控制方式"
                    )

                    # 情感参考音频 (mode=1)
                    with gr.Group(visible=False) as emo_audio_group:
                        emo_audio = gr.Audio(label="上传情感参考音频", type="filepath")

                    # 情感随机采样 (mode=2)
                    with gr.Row(visible=False) as emo_random_group:
                        emo_random = gr.Checkbox(label="情感随机采样", value=False)

                    # 情感向量 (mode=2)
                    with gr.Group(visible=False) as emo_vector_group:
                        with gr.Row():
                            with gr.Column():
                                vec1 = gr.Slider(label="喜", minimum=0.0, maximum=1.0, value=0.0, step=0.05)
                                vec2 = gr.Slider(label="怒", minimum=0.0, maximum=1.0, value=0.0, step=0.05)
                                vec3 = gr.Slider(label="哀", minimum=0.0, maximum=1.0, value=0.0, step=0.05)
                                vec4 = gr.Slider(label="惧", minimum=0.0, maximum=1.0, value=0.0, step=0.05)
                            with gr.Column():
                                vec5 = gr.Slider(label="厌恶", minimum=0.0, maximum=1.0, value=0.0, step=0.05)
                                vec6 = gr.Slider(label="低落", minimum=0.0, maximum=1.0, value=0.0, step=0.05)
                                vec7 = gr.Slider(label="惊喜", minimum=0.0, maximum=1.0, value=0.0, step=0.05)
                                vec8 = gr.Slider(label="平静", minimum=0.0, maximum=1.0, value=0.0, step=0.05)

                    # 情感文本 (mode=3)
                    with gr.Group(visible=False) as emo_text_group:
                        emo_text = gr.Textbox(
                            label="情感描述文本",
                            placeholder="请输入情绪描述（或留空以自动使用目标文本）",
                            value=""
                        )

                    # 情感权重 (mode=1/2/3)
                    with gr.Group(visible=False) as emo_weight_group:
                        emo_weight = gr.Slider(label="情感权重", minimum=0.0, maximum=2.0, value=1.0, step=0.01)

                    with gr.Accordion("高级生成参数", open=False):
                        with gr.Row():
                            speed = gr.Slider(label="语速 (Speed)", minimum=0.5, maximum=2.0, value=1.0, step=0.05)
                            target_length_ms = gr.Number(label="目标时长毫秒 (Target Length in ms)", value=0, precision=0)
                        with gr.Row():
                            do_sample = gr.Checkbox(label="do_sample", value=True)
                            temperature = gr.Slider(label="temperature", minimum=0.1, maximum=2.0, value=0.8, step=0.1)
                        with gr.Row():
                            top_p = gr.Slider(label="top_p", minimum=0.0, maximum=1.0, value=0.8, step=0.01)
                            top_k = gr.Slider(label="top_k", minimum=0, maximum=100, value=30, step=1)
                            num_beams = gr.Slider(label="num_beams", value=3, minimum=1, maximum=10, step=1)
                        with gr.Row():
                            repetition_penalty = gr.Number(label="repetition_penalty", value=10.0, minimum=0.1, maximum=20.0, step=0.1)
                            length_penalty = gr.Number(label="length_penalty", value=0.0, minimum=-2.0, maximum=2.0, step=0.1)
                        max_mel_tokens = gr.Slider(label="max_mel_tokens", value=1500, minimum=50, maximum=4096, step=10)
                        max_text_tokens_per_segment = gr.Slider(label="分句最大Token数", value=120, minimum=20, maximum=512, step=2)

                    btn = gr.Button("生成", variant="primary")
                with gr.Column():
                    gr.Markdown("### 生成结果")
                    out = gr.HTML()

                # 模式切换联动
                emo_mode.change(
                    on_mode_change,
                    inputs=[emo_mode],
                    outputs=[emo_audio_group, emo_vector_group, emo_text_group, emo_random_group, emo_weight_group]
                )

                btn.click(
                    ui_tts,
                    [txt, aud, emo_mode, emo_audio, emo_weight,
                     vec1, vec2, vec3, vec4, vec5, vec6, vec7, vec8,
                     emo_text, emo_random,
                     speed, target_length_ms,
                     do_sample, top_p, top_k, temperature,
                     length_penalty, num_beams, repetition_penalty, max_mel_tokens,
                     max_text_tokens_per_segment],
                    out
                )

        self.app = gr.mount_gradio_app(self.app, demo, path="/ui")

    def run(self):
        """运行服务"""
        print("\n" + "="*60)
        print("🚀 启动服务...")
        print(f" 地址: http://0.0.0.0:{self.config.port}")
        print(f" API文档: http://localhost:{self.config.port}/docs")
        print(f" WebUI: http://localhost:{self.config.port}/ui")
        print("="*60 + "\n", flush=True)
        uvicorn.run(self.app, host="0.0.0.0", port=self.config.port)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="IndexTTS2 部署服务")
    parser.add_argument("--port", type=int, default=8000, help="服务端口")
    parser.add_argument("--mode", choices=["api", "webui", "both"], default="both",
                        help="部署模式: api仅API, webui仅WebUI, both两者")
    parser.add_argument("--repo-dir", type=str, default=None,
                        help="项目根目录路径")
    parser.add_argument("--no-fp16", action="store_true",
                        help="禁用FP16")

    args = parser.parse_args()

    # 环境变量覆盖
    if args.repo_dir:
        os.environ["INDEXTTS_REPO_DIR"] = args.repo_dir

    print("\n" + "="*60)
    print("🎙️ IndexTTS2 部署服务")
    print("="*60)

    # 创建配置
    config = TTSConfig()
    config.port = args.port
    config.mode = args.mode
    config.use_fp16 = not args.no_fp16

    print(f" 模式: {config.mode}")
    print(f" 端口: {config.port}")
    print(f" 项目路径: {config.repo_dir}")
    print(f" FP16: {config.use_fp16}")
    print("="*60 + "\n", flush=True)

    # 启动服务
    app = TTSApp(config)
    app.load_model()

    if config.mode in ["webui", "both"]:
        print("\n🎨 设置WebUI...", flush=True)
        app.setup_webui()
        print("✅ WebUI设置完成\n", flush=True)

    app.run()


if __name__ == "__main__":
    main()
