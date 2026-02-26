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
        
        # 加速优化选项
        self.use_accel = True  # GPT加速引擎 (FlashAttention优化)
        self.use_deepspeed = True  # DeepSpeed推理加速
        self.use_cuda_kernel = True  # BigVGAN CUDA内核加速
        self.use_torch_compile = False  # PyTorch编译优化 (Colab/Kaggle可能有兼容性问题)
    
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
        print(f"   配置文件: {self.config.cfg_path}")
        print(f"   模型目录: {self.config.model_dir}")
        print(f"   设备: {self.config.device}")
        print(f"   FP16: {self.config.use_fp16}")
        print("="*60, flush=True)
        
        if not os.path.exists(self.config.cfg_path):
            raise FileNotFoundError(f"找不到配置文件: {self.config.cfg_path}")
        
        # 检测是否在Colab/Kaggle环境
        is_notebook_env = self._is_notebook_environment()
        
        # 根据环境自动调整优化选项
        use_accel = self.config.use_accel
        use_deepspeed = self.config.use_deepspeed
        use_cuda_kernel = self.config.use_cuda_kernel
        use_torch_compile = self.config.use_torch_compile
        
        if is_notebook_env:
            print("📓 检测到Notebook环境 (Colab/Kaggle)")
            # 在Notebook环境中，降低部分优化的要求
            use_torch_compile = False  # torch.compile在某些Notebook环境可能不稳定
            # DeepSpeed和CUDA内核保持启用，但失败时会自动回退
        
        print(f"🚀 启用优化: FP16={self.config.use_fp16}, Accel={use_accel}, DeepSpeed={use_deepspeed}, CUDA内核={use_cuda_kernel}, Torch编译={use_torch_compile}")
        
        try:
            self.tts = IndexTTS2(
                cfg_path=self.config.cfg_path,
                model_dir=self.config.model_dir,
                use_fp16=self.config.use_fp16,
                device=self.config.device,
                use_accel=use_accel,
                use_deepspeed=use_deepspeed,
                use_cuda_kernel=use_cuda_kernel,
                use_torch_compile=use_torch_compile
            )
        except Exception as e:
            print(f"⚠️ 启用全部优化失败: {e}")
            print("🔄 回退到基础配置...")
            # 回退到最基础的配置
            self.tts = IndexTTS2(
                cfg_path=self.config.cfg_path,
                model_dir=self.config.model_dir,
                use_fp16=self.config.use_fp16,
                device=self.config.device,
                use_accel=False,
                use_deepspeed=False,
                use_cuda_kernel=False,
                use_torch_compile=False
            )
        
        elapsed = time.time() - start_time
        print("="*60)
        print(f"✅ 模型加载完成!")
        print(f" 耗时: {elapsed:.1f}秒")
        print(f" 设备: {self.config.device}")
        print(f" 实际启用的优化: Accel={getattr(self.tts, 'use_accel', False)}, DeepSpeed={getattr(self.tts, 'use_deepspeed', False)}, CUDA内核={getattr(self.tts, 'use_cuda_kernel', False)}")
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
            emo_alpha: float = Form(1.0),
            authenticated: bool = Depends(self._verify_token)
        ):
            """TTS API接口 (需要token鉴权)"""
            try:
                if self.tts is None:
                    return JSONResponse(
                        status_code=503, 
                        content={"error": "模型未加载"}
                    )
                
                # 保存参考音频
                with NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                    shutil.copyfileobj(spk_audio.file, tmp)
                    spk_path = tmp.name
                
                # 生成音频
                output = "/tmp/out.wav"
                self.tts.infer(
                    spk_audio_prompt=spk_path,
                    text=text,
                    output_path=output,
                    emo_alpha=emo_alpha,
                    verbose=False
                )
                os.unlink(spk_path)
                
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
        """配置WebUI - 使用HTML iframe内嵌base64音频，绕过Gradio文件服务"""
        if self.tts is None:
            raise RuntimeError("模型未加载，无法设置WebUI")

        def ui_tts(text, audio, alpha):
            import time
            import base64
            out = "/tmp/tts_output.wav"
            self.tts.infer(
                spk_audio_prompt=audio,
                text=text,
                output_path=out,
                emo_alpha=alpha,
                verbose=False
            )
            # 读取并转为base64
            with open(out, 'rb') as f:
                audio_bytes = f.read()
            audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
            # 使用HTML5 audio标签播放base64音频
            html = f'''<audio controls style="width:100%;" autoplay>
  <source src="data:audio/wav;base64,{audio_b64}" type="audio/wav">
  您的浏览器不支持音频播放。
</audio>'''
            return html

        with gr.Blocks(title="IndexTTS2") as demo:
            gr.Markdown("# 🎙️ IndexTTS2")
            with gr.Row():
                with gr.Column():
                    txt = gr.Textbox(label="文本", lines=4)
                    aud = gr.Audio(label="参考音频", type="filepath")
                    alpha = gr.Slider(0, 2, value=1, step=0.1, label="情感强度")
                    btn = gr.Button("生成", variant="primary")
                with gr.Column():
                    gr.Markdown("### 生成结果")
                    out = gr.HTML()
            btn.click(ui_tts, [txt, aud, alpha], out)
        
        self.app = gr.mount_gradio_app(self.app, demo, path="/ui")
    
    def _is_notebook_environment(self):
        """检测是否在Notebook环境（Colab/Kaggle）"""
        try:
            # 检测是否在Colab
            import google.colab
            return True
        except ImportError:
            pass
        
        # 检测是否在Kaggle
        if os.environ.get('KAGGLE_KERNEL_RUN_TYPE') is not None:
            return True
        
        # 检测Jupyter Notebook
        try:
            from IPython import get_ipython
            if get_ipython() is not None:
                return True
        except ImportError:
            pass
        
        return False
    
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
    
    # 加速优化选项
    parser.add_argument("--no-accel", action="store_true",
                        help="禁用GPT加速引擎")
    parser.add_argument("--no-deepspeed", action="store_true",
                        help="禁用DeepSpeed")
    parser.add_argument("--no-cuda-kernel", action="store_true",
                        help="禁用CUDA内核")
    parser.add_argument("--torch-compile", action="store_true",
                        help="启用PyTorch编译优化 (不推荐在Colab/Kaggle使用)")

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
    config.use_accel = not args.no_accel
    config.use_deepspeed = not args.no_deepspeed
    config.use_cuda_kernel = not args.no_cuda_kernel
    config.use_torch_compile = args.torch_compile

    print(f" 模式: {config.mode}")
    print(f" 端口: {config.port}")
    print(f" 项目路径: {config.repo_dir}")
    print(f" 加速优化: FP16={config.use_fp16}, Accel={config.use_accel}, DeepSpeed={config.use_deepspeed}, CUDA内核={config.use_cuda_kernel}, Torch编译={config.use_torch_compile}")
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
