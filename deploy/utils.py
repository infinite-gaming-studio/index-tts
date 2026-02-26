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


class MambaInstaller:
    """独立安装mamba (不依赖conda)"""
    
    @staticmethod
    def check_mamba() -> bool:
        """检查mamba是否可用且是包管理器（不是测试框架）"""
        try:
            result = subprocess.run(["mamba", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                return False
            output = result.stdout.lower() + result.stderr.lower()
            return 'mamba' in output and 'coverage' not in output and 'test' not in output
        except:
            return False
    
    @classmethod
    def install_micromamba(cls, work_dir: str = "/tmp") -> bool:
        """安装micromamba (独立的轻量级mamba)"""
        print("🔧 安装 micromamba (独立mamba)...")
        mamba_root = f"{work_dir}/mamba"
        
        try:
            # 下载安装脚本
            import urllib.request
            installer_url = "https://micro.mamba.pm/install.sh"
            install_script = f"{work_dir}/micromamba_install.sh"
            urllib.request.urlretrieve(installer_url, install_script)
            os.chmod(install_script, 0o755)
            
            # 执行安装
            env = os.environ.copy()
            env['MAMBA_ROOT_PREFIX'] = mamba_root
            
            result = subprocess.run(['bash', install_script], env=env, capture_output=True, text=True)
            if result.returncode == 0:
                # 添加到PATH
                bin_path = f"{mamba_root}/bin"
                os.environ['PATH'] = f"{bin_path}:{os.environ['PATH']}"
                
                # 创建mamba别名指向micromamba
                micromamba_bin = f"{bin_path}/micromamba"
                mamba_bin = f"{bin_path}/mamba"
                if os.path.exists(micromamba_bin) and not os.path.exists(mamba_bin):
                    os.symlink(micromamba_bin, mamba_bin)
                
                print(f"✅ micromamba 安装完成 (路径: {bin_path})")
                return True
            else:
                print(f"⚠️ micromamba安装失败")
                return False
        except Exception as e:
            print(f"⚠️ micromamba安装异常: {e}")
            return False
    
    @classmethod
    def install_via_conda(cls) -> bool:
        """通过conda安装mamba"""
        try:
            result = subprocess.run(["conda", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                return False
            
            print("🔧 通过conda安装mamba...")
            subprocess.run(["conda", "install", "-y", "-c", "conda-forge", "mamba"], check=True)
            return cls.check_mamba()
        except:
            return False
    
    @classmethod
    def install(cls, work_dir: str = "/tmp") -> bool:
        """安装mamba (优先micromamba)"""
        if cls.check_mamba():
            print("✅ mamba已可用")
            return True
        
        # 方法1: micromamba (独立，不依赖conda)
        if cls.install_micromamba(work_dir):
            return True
        
        # 方法2: 通过conda安装
        if cls.install_via_conda():
            return True
        
        print("⚠️ 无法安装mamba，将使用pip")
        return False
    
    @classmethod
    def install_packages(cls, packages: list, channels: list = None) -> bool:
        """使用mamba安装包"""
        if not cls.check_mamba():
            return False
        
        try:
            cmd = ["mamba", "install", "-y"]
            if channels:
                for ch in channels:
                    cmd.extend(["-c", ch])
            cmd.extend(packages)
            subprocess.run(cmd, check=True)
            return True
        except:
            return False


class DependencyInstaller:
    """依赖安装器 - 支持mamba加速"""
    
    # 可用mamba安装的包（更快）
    MAMBA_DEPS = [
        "python=3.10",
        "cudatoolkit=11.8",
    ]
    
    # 必须用pip安装的包
    PIP_DEPS = [
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "--index-url", "https://download.pytorch.org/whl/cu128",
    ]
    
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
    def _check_mamba(cls) -> bool:
        """检查mamba是否可用（且是conda包管理器，不是测试框架）"""
        try:
            result = subprocess.run(["mamba", "--version"], capture_output=True, text=True)
            if result.returncode != 0:
                return False
            # 检查是否是conda的mamba（不是Python测试框架mamba）
            # conda mamba会显示版本号，测试框架会显示帮助信息包含"coverage"
            output = result.stdout.lower() + result.stderr.lower()
            if 'coverage' in output or 'test' in output:
                return False
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @classmethod
    def _check_conda(cls) -> bool:
        """检查conda是否可用"""
        try:
            subprocess.run(["conda", "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    @classmethod
    def setup_mamba_colab(cls):
        """在Colab安装mamba (通过condacolab)"""
        print("🔧 Colab环境: 安装condacolab...")
        subprocess.run(["pip", "install", "-q", "condacolab"], check=True)
        import condacolab
        condacolab.install()
        print("✅ condacolab安装完成")
    
    @classmethod
    def setup_mamba_kaggle(cls):
        """在Kaggle安装mamba（如果可用）"""
        print("🔧 Kaggle环境: 检查mamba...")
        # Kaggle的mamba可能是测试框架，先检查
        if cls._check_mamba():
            print("✅ mamba已可用")
            return True
        # 尝试安装conda的mamba
        try:
            subprocess.run([
                "conda", "install", "-y", "-c", "conda-forge", "mamba"
            ], check=True)
            # 再次检查
            if cls._check_mamba():
                print("✅ mamba安装完成")
                return True
            else:
                print("⚠️ 安装的mamba不是包管理器，使用conda")
                return False
        except Exception as e:
            print(f"⚠️ mamba安装失败: {e}，使用conda")
            return False
    
    @classmethod
    def install_with_conda(cls) -> bool:
        """使用conda安装依赖"""
        if not cls._check_conda():
            return False
        print("🚀 使用conda安装基础依赖...")
        try:
            cmd = ["conda", "install", "-y", "-c", "conda-forge", "-c", "nvidia"] + cls.MAMBA_DEPS
            subprocess.run(cmd, check=True)
            print("✅ conda依赖安装完成")
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️ conda安装失败: {e}")
            return False
    
    @classmethod
    def install_with_mamba(cls, in_colab: bool = False, in_kaggle: bool = False):
        """使用mamba安装依赖（更快），失败时回退到conda或pip"""
        
        # 根据环境安装/检查mamba
        if in_colab and not cls._check_mamba():
            cls.setup_mamba_colab()
        elif in_kaggle and not cls._check_mamba():
            # Kaggle使用conda安装mamba
            cls.setup_mamba_kaggle()
        
        # 尝试使用mamba
        if cls._check_mamba():
            print("🚀 使用mamba安装基础依赖（更快）...")
            try:
                cmd = ["mamba", "install", "-y", "-c", "conda-forge", "-c", "nvidia"] + cls.MAMBA_DEPS
                subprocess.run(cmd, check=True)
                print("✅ mamba依赖安装完成")
                return True
            except subprocess.CalledProcessError as e:
                print(f"⚠️ mamba安装失败: {e}，尝试conda")
        
        # 回退到conda
        if cls._check_conda():
            return cls.install_with_conda()
        
        print("⚠️ conda/mamba都不可用，回退到pip安装")
        return False
    
    @classmethod
    def install_pytorch(cls):
        """安装PyTorch (带fallback)"""
        print("📦 安装PyTorch (尝试cu128)...")
        try:
            # 首先尝试项目要求的cu128
            cmd = ["pip", "install", "-q"] + cls.PIP_DEPS
            subprocess.run(cmd, check=True)
            print("✅ PyTorch cu128 安装完成")
        except subprocess.CalledProcessError:
            print("⚠️ cu128不可用，尝试cu121...")
            try:
                # 回退到cu121
                fallback_cmd = [
                    "pip", "install", "-q",
                    "torch==2.5.1", "torchaudio==2.5.1",
                    "--index-url", "https://download.pytorch.org/whl/cu121"
                ]
                subprocess.run(fallback_cmd, check=True)
                print("✅ PyTorch cu121 (2.5.1) 安装完成")
            except subprocess.CalledProcessError:
                print("⚠️ CUDA版本均不可用，使用标准pip...")
                # 最后回退到标准pip
                subprocess.run(["pip", "install", "-q", "torch", "torchaudio"], check=True)
                print("✅ PyTorch (标准版) 安装完成")
    
    @classmethod
    def install_flash_attn(cls, force: bool = False):
        """安装 flash-attention (Accel加速必需)
        
        Args:
            force: 强制重新安装
        """
        # 检查是否已安装
        if not force:
            try:
                import flash_attn
                print(f"✅ flash-attention 已安装 ({flash_attn.__version__})")
                return True
            except ImportError:
                pass
        
        print("📦 安装 flash-attention (Accel加速必需，约需5-10分钟)...")
        print("⏳ 正在编译安装，请耐心等待...")
        
        try:
            # 安装依赖
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-q",
                "ninja", "packaging"
            ], check=True)
            
            # 安装 flash-attn (从源码编译)
            # 使用 --no-build-isolation 避免隔离环境缺少依赖
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-v",
                "flash-attn", "--no-build-isolation"
            ], capture_output=True, text=True, timeout=600)  # 10分钟超时
            
            if result.returncode == 0:
                print("✅ flash-attention 安装成功")
                return True
            else:
                print(f"⚠️ flash-attention 安装失败")
                print(f"错误: {result.stderr[:500]}")
                return False
        except subprocess.TimeoutExpired:
            print("⚠️ flash-attention 安装超时 (>10分钟)")
            return False
        except Exception as e:
            print(f"⚠️ flash-attention 安装异常: {e}")
            return False
    
    @classmethod
    def install_deepspeed(cls):
        """安装 DeepSpeed (可选加速)"""
        try:
            import deepspeed
            print(f"✅ DeepSpeed 已安装")
            return True
        except ImportError:
            pass
        
        print("📦 安装 DeepSpeed (可选，约需2-5分钟)...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-q", "deepspeed"
            ], check=True, timeout=300)
            print("✅ DeepSpeed 安装成功")
            return True
        except Exception as e:
            print(f"⚠️ DeepSpeed 安装失败: {e}")
            print("💡 DeepSpeed 是可选依赖，服务仍可正常运行")
            return False

    @classmethod
    def install_deps(cls, use_mamba: bool = True, in_colab: bool = False, in_kaggle: bool = False, 
                     install_flash: bool = True, install_ds: bool = True):
        """安装核心依赖 (python/cuda 已在Cell 1用mamba安装)

        Args:
            use_mamba: Cell 1是否成功安装了mamba（仅用于显示信息）
            in_colab: 是否在Colab环境
            in_kaggle: 是否在Kaggle环境
            install_flash: 是否安装 flash-attention (Accel加速必需，耗时5-10分钟)
            install_ds: 是否安装 DeepSpeed (可选加速，耗时2-5分钟)
        """
        # 安装PyTorch
        cls.install_pytorch()

        # 安装其他依赖
        print("📦 安装核心依赖...")
        for dep in cls.CORE_DEPS:
            subprocess.run(["pip", "install", "-q", dep], check=True)
        print("✅ 核心依赖安装完成")
        
        # 安装 flash-attention (可选，用于Accel加速)
        if install_flash:
            flash_installed = cls.install_flash_attn()
            if not flash_installed:
                print("⚠️ flash-attention 安装失败，Accel加速将不可用")
                print("💡 服务仍可正常运行，但速度较慢 (RTF ~0.5)")
                print("💡 安装 flash-attention 后可提升至 RTF ~0.2 (2.5倍提速)")
        
        # 安装 DeepSpeed (可选)
        if install_ds:
            cls.install_deepspeed()


class ModelDownloader:
    """模型下载器 - 使用Python API而非命令行"""
    
    MODEL_ID = "IndexTeam/IndexTTS-2"
    MODELSCOPE_MODEL_ID = "IndexTeam/IndexTTS-2"
    
    @classmethod
    def _ensure_package(cls, package_name: str, import_name: str = None):
        """确保包已安装，如未安装则自动安装"""
        import_name = import_name or package_name
        try:
            __import__(import_name)
            return True
        except ImportError:
            print(f"   安装 {package_name}...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-q", package_name],
                    check=True,
                    capture_output=True
                )
                return True
            except Exception as e:
                print(f"   ⚠️ 安装 {package_name} 失败: {e}")
                return False
    
    @classmethod
    def download_from_hf(cls, target_dir: str) -> bool:
        """从HuggingFace下载 - 使用Python API"""
        # 确保 huggingface-hub 已安装
        if not cls._ensure_package("huggingface-hub", "huggingface_hub"):
            return False
        
        try:
            from huggingface_hub import snapshot_download
            
            print(f"   从 HuggingFace 下载模型...")
            print(f"   模型ID: {cls.MODEL_ID}")
            print(f"   目标目录: {target_dir}")
            
            # 检查网络连通性
            print("   检查 HuggingFace 连通性...")
            import urllib.request
            try:
                urllib.request.urlopen('https://huggingface.co', timeout=10)
                print("   ✅ HuggingFace 可访问")
            except Exception as e:
                print(f"   ⚠️ 警告: HuggingFace 可能无法访问 ({e})")
            
            snapshot_download(
                repo_id=cls.MODEL_ID,
                local_dir=target_dir,
                resume_download=True,
                local_dir_use_symlinks=False
            )
            print("   ✅ HuggingFace 下载成功")
            return True
        except Exception as e:
            print(f"   ❌ HuggingFace 下载失败: {e}")
            import traceback
            print(f"   详细错误:\n{traceback.format_exc()}")
            return False
    
    @classmethod
    def download_from_modelscope(cls, target_dir: str) -> bool:
        """从ModelScope下载 - 使用Python API"""
        # 确保 modelscope 已安装
        if not cls._ensure_package("modelscope"):
            return False
        
        try:
            from modelscope.hub.snapshot_download import snapshot_download
            
            print(f"   从 ModelScope 下载模型...")
            print(f"   模型ID: {cls.MODELSCOPE_MODEL_ID}")
            print(f"   目标目录: {target_dir}")
            
            # 检查网络连通性
            print("   检查 ModelScope 连通性...")
            import urllib.request
            try:
                urllib.request.urlopen('https://www.modelscope.cn', timeout=10)
                print("   ✅ ModelScope 可访问")
            except Exception as e:
                print(f"   ⚠️ 警告: ModelScope 可能无法访问 ({e})")
            
            snapshot_download(
                model_id=cls.MODELSCOPE_MODEL_ID,
                local_dir=target_dir
            )
            print("   ✅ ModelScope 下载成功")
            return True
        except Exception as e:
            print(f"   ❌ ModelScope 下载失败: {e}")
            import traceback
            print(f"   详细错误:\n{traceback.format_exc()}")
            return False
    
    @classmethod
    def download(cls, target_dir: str, source: str = "auto"):
        """
        下载模型
        
        Args:
            target_dir: 下载目标目录
            source: 下载源，"auto" | "huggingface" | "modelscope"
        """
        os.makedirs(target_dir, exist_ok=True)
        
        # 显示当前目录内容（用于调试）
        print(f"   当前目录内容: {os.listdir(target_dir) if os.path.exists(target_dir) else '目录不存在'}")
        
        # 自动选择下载源（优先HuggingFace）
        if source == "auto":
            sources = [("huggingface", cls.download_from_hf), 
                       ("modelscope", cls.download_from_modelscope)]
        elif source == "huggingface":
            sources = [("huggingface", cls.download_from_hf)]
        elif source == "modelscope":
            sources = [("modelscope", cls.download_from_modelscope)]
        else:
            sources = [("huggingface", cls.download_from_hf), 
                       ("modelscope", cls.download_from_modelscope)]
        
        for name, download_func in sources:
            print(f"\n   尝试从 {name} 下载...")
            if download_func(target_dir):
                # 验证下载结果
                print(f"   验证下载结果...")
                files = os.listdir(target_dir)
                model_files = [f for f in files if f.endswith(('.pt', '.bin', '.pth', '.safetensors', '.ckpt'))]
                print(f"   下载后文件列表: {files}")
                print(f"   模型权重文件: {model_files}")
                
                if model_files:
                    print(f"   ✅ 验证成功: 找到 {len(model_files)} 个权重文件")
                    return True
                else:
                    print(f"   ⚠️ 警告: 下载完成但未找到权重文件")
            print(f"   {name} 下载失败，尝试其他源...")
        
        print("\n   ❌ 所有下载源都失败了")
        print("   可能原因:")
        print("   1. 网络连接问题（无法访问HuggingFace/ModelScope）")
        print("   2. 模型ID错误或被移除")
        print("   3. 存储空间不足")
        print("   4. 权限问题")
        return False


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
