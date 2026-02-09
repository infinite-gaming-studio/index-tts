"""
IndexTTS2 部署工具
环境检测、模型下载、依赖安装
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Optional


class EnvDetector:
    """环境检测器"""
    
    @staticmethod
    def is_colab() -> bool:
        """是否在Google Colab"""
        return 'google.colab' in sys.modules
    
    @staticmethod
    def is_kaggle() -> bool:
        """是否在Kaggle"""
        return os.path.exists('/kaggle/input') or \
               os.environ.get('KAGGLE_KERNEL_RUN_TYPE') is not None
    
    @staticmethod
    def get_work_dir() -> str:
        """获取工作目录"""
        if EnvDetector.is_colab():
            return "/content"
        elif EnvDetector.is_kaggle():
            return "/kaggle/working"
        return "/tmp"
    
    @staticmethod
    def get_cuda_available() -> bool:
        """检测CUDA是否可用"""
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False


class DependencyInstaller:
    """依赖安装器"""
    
    CORE_DEPS = [
        "accelerate==1.8.1",
        "transformers==4.52.1",
        "tokenizers==0.21.0",
        "modelscope==1.27.0",
        "huggingface-hub",
        "sentencepiece>=0.2.1",
        "einops>=0.8.1",
        "safetensors==0.5.2",
        "omegaconf>=2.3.0",
        "librosa==0.10.2.post1",
        "soundfile",
        "ffmpeg-python==0.2.0",
        "jieba==0.42.1",
        "g2p-en==2.1.0",
        "cn2an==0.5.22",
        "cython==3.0.7",
        "matplotlib",
        "tensorboard",
        "pydub",
        "fastapi",
        "uvicorn",
        "python-multipart",
        "pyngrok",
        "gradio==5.45.0",
    ]
    
    @classmethod
    def install_pytorch(cls):
        """安装PyTorch"""
        cmd = [
            "pip", "install", "-q",
            "torch==2.8.0", "torchaudio==2.8.0",
            "--index-url", "https://download.pytorch.org/whl/cu121"
        ]
        subprocess.run(cmd, check=True)
    
    @classmethod
    def install_deps(cls):
        """安装核心依赖"""
        for dep in cls.CORE_DEPS:
            subprocess.run(["pip", "install", "-q", dep], check=True)
    
    @classmethod
    def install_conda_colab(cls):
        """在Colab安装conda"""
        subprocess.run([
            "pip", "install", "-q", "condacolab"
        ], check=True)
        import condacolab
        condacolab.install()


class ModelDownloader:
    """模型下载器"""
    
    MODEL_ID = "IndexTeam/IndexTTS-2"
    
    @classmethod
    def download_from_hf(cls, target_dir: str) -> bool:
        """从HuggingFace下载"""
        try:
            subprocess.run([
                "pip", "install", "-q", "huggingface-hub[cli]"
            ], check=True)
            
            subprocess.run([
                "huggingface-cli", "download",
                cls.MODEL_ID,
                "--local-dir", target_dir,
                "--resume-download"
            ], check=True)
            return True
        except Exception as e:
            print(f"HuggingFace下载失败: {e}")
            return False
    
    @classmethod
    def download_from_modelscope(cls, target_dir: str) -> bool:
        """从ModelScope下载"""
        try:
            subprocess.run([
                "pip", "install", "-q", "modelscope"
            ], check=True)
            
            subprocess.run([
                "modelscope", "download",
                "--model", cls.MODEL_ID,
                "--local_dir", target_dir
            ], check=True)
            return True
        except Exception as e:
            print(f"ModelScope下载失败: {e}")
            return False
    
    @classmethod
    def download(cls, target_dir: str, source: str = "huggingface"):
        """下载模型"""
        os.makedirs(target_dir, exist_ok=True)
        
        if source == "huggingface":
            if cls.download_from_hf(target_dir):
                return True
            print("尝试使用ModelScope...")
            return cls.download_from_modelscope(target_dir)
        else:
            return cls.download_from_modelscope(target_dir)


def save_config(repo_dir: str):
    """保存配置到文件"""
    config = {
        "work_dir": EnvDetector.get_work_dir(),
        "repo_dir": repo_dir
    }
    with open("/tmp/notebook_config.json", "w") as f:
        json.dump(config, f)


def load_config() -> dict:
    """从文件加载配置"""
    try:
        with open("/tmp/notebook_config.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "work_dir": EnvDetector.get_work_dir(),
            "repo_dir": str(Path(__file__).parent.parent)
        }


def clone_repo(target_dir: str, branch: str = "dev"):
    """克隆仓库"""
    repo_url = "https://github.com/infinite-gaming-studio/index-tts.git"
    
    # 删除旧目录
    if os.path.exists(target_dir):
        subprocess.run(["rm", "-rf", target_dir], check=True)
    
    # 克隆
    subprocess.run([
        "git", "clone", "-b", branch, repo_url, target_dir
    ], check=True)
    
    # 安装项目
    subprocess.run([
        "pip", "install", "-q", "-e", target_dir
    ], check=True)


def check_model_exists(checkpoint_dir: str) -> bool:
    """检查模型是否存在"""
    config_file = os.path.join(checkpoint_dir, "config.yaml")
    return os.path.exists(config_file)


def get_gpu_info() -> dict:
    """获取GPU信息"""
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "name": torch.cuda.get_device_name(0),
                "total_memory": torch.cuda.get_device_properties(0).total_memory / 1e9,
                "allocated": torch.cuda.memory_allocated() / 1e9
            }
    except ImportError:
        pass
    return {"available": False}


if __name__ == "__main__":
    # 测试
    print("环境检测:")
    print(f"  Colab: {EnvDetector.is_colab()}")
    print(f"  Kaggle: {EnvDetector.is_kaggle()}")
    print(f"  工作目录: {EnvDetector.get_work_dir()}")
    print(f"  CUDA: {EnvDetector.get_cuda_available()}")
