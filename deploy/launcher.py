"""
IndexTTS2 部署启动器
用于从Notebook快速启动服务
"""

import os
import sys
import time
import subprocess
import signal
from pathlib import Path

# 添加deploy目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from utils import load_config, get_gpu_info


class ServiceLauncher:
    """服务启动器"""
    
    def __init__(self):
        self.config = load_config()
        self.process = None
        self.log_file = None
    
    def stop_existing(self):
        """停止已有服务"""
        print("🛑 停止已有服务...")
        
        # 从文件读取PID
        pid_file = "/tmp/indextts_service.pid"
        if os.path.exists(pid_file):
            try:
                with open(pid_file) as f:
                    old_pid = int(f.read().strip())
                os.kill(old_pid, signal.SIGTERM)
                print(f"  停止旧进程: {old_pid}")
            except (ProcessLookupError, ValueError):
                pass
            os.remove(pid_file)
        
        # 清理其他进程
        subprocess.run(["pkill", "-f", "service.py"], capture_output=True)
        subprocess.run(["pkill", "-f", "ngrok"], capture_output=True)
        time.sleep(1)
    
    def start(self, port: int = 8000, mode: str = "both", ngrok_token: str = None):
        """启动服务"""
        
        self.stop_existing()
        
        print(f"🚀 启动服务 (端口: {port}, 模式: {mode})...")
        
        # 准备服务脚本路径
        service_script = Path(__file__).parent / "service.py"
        repo_dir = self.config.get("repo_dir", "/tmp/index-tts")
        
        # 打开日志文件
        log_path = os.path.join(repo_dir, "service.log")
        self.log_file = open(log_path, "w")
        
        # 启动服务进程
        cmd = [
            sys.executable,
            str(service_script),
            "--port", str(port),
            "--mode", mode,
            "--repo-dir", repo_dir
        ]
        
        # 使用subprocess启动，脱离Jupyter控制
        self.process = subprocess.Popen(
            cmd,
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            cwd=repo_dir
        )
        
        # 保存PID
        with open("/tmp/indextts_service.pid", "w") as f:
            f.write(str(self.process.pid))
        
        print(f"  服务PID: {self.process.pid}")
        
        # 等待服务启动
        print("⏳ 等待服务启动 (约30秒)...")
        time.sleep(30)
        
        # 检查是否启动成功
        if self.process.poll() is not None:
            self.log_file.flush()
            with open(log_path) as f:
                print(f.read())
            raise RuntimeError("服务启动失败")
        
        print("✅ 服务启动成功")
        
        # 设置ngrok
        if ngrok_token:
            self._setup_ngrok(port, ngrok_token)
        else:
            print(f"\n🔗 本地地址: http://localhost:{port}")
    
    def _setup_ngrok(self, port: int, token: str):
        """配置ngrok"""
        try:
            from pyngrok import ngrok
            
            ngrok.set_auth_token(token)
            public_url = ngrok.connect(port, "http")
            
            print(f"\n{'='*60}")
            print(f"✅ 公网地址: {public_url}")
            print(f"  API: {public_url}/api/tts")
            print(f"  WebUI: {public_url}/ui")
            print(f"  Docs: {public_url}/docs")
            print(f"{'='*60}")
        except Exception as e:
            print(f"⚠️ ngrok启动失败: {e}")
    
    def status(self):
        """检查服务状态"""
        if self.process is None:
            # 尝试读取PID文件
            pid_file = "/tmp/indextts_service.pid"
            if os.path.exists(pid_file):
                with open(pid_file) as f:
                    pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)  # 检查进程是否存在
                    print(f"✅ 服务运行中 (PID: {pid})")
                    return True
                except ProcessLookupError:
                    print("❌ 服务未运行")
                    return False
            else:
                print("❌ 服务未运行")
                return False
        else:
            if self.process.poll() is None:
                print(f"✅ 服务运行中 (PID: {self.process.pid})")
                return True
            else:
                print(f"❌ 服务已退出 (code: {self.process.returncode})")
                return False
    
    def stop(self):
        """停止服务"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            print("✅ 服务已停止")
        
        if self.log_file:
            self.log_file.close()
        
        pid_file = "/tmp/indextts_service.pid"
        if os.path.exists(pid_file):
            os.remove(pid_file)
    
    def logs(self, lines: int = 20):
        """查看日志"""
        repo_dir = self.config.get("repo_dir", "/tmp/index-tts")
        log_path = os.path.join(repo_dir, "service.log")
        
        if os.path.exists(log_path):
            with open(log_path) as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    print(line, end='')
        else:
            print("日志文件不存在")


def quick_start(port: int = 8000, mode: str = "both", ngrok_token: str = None):
    """快速启动 - 供Notebook调用"""
    launcher = ServiceLauncher()
    launcher.start(port, mode, ngrok_token)
    return launcher


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="IndexTTS2 服务启动器")
    parser.add_argument("command", choices=["start", "stop", "status", "logs"],
                       help="命令")
    parser.add_argument("--port", type=int, default=8000, help="端口")
    parser.add_argument("--mode", choices=["api", "webui", "both"], 
                       default="both", help="模式")
    parser.add_argument("--ngrok-token", type=str, default=None,
                       help="ngrok token")
    
    args = parser.parse_args()
    
    launcher = ServiceLauncher()
    
    if args.command == "start":
        launcher.start(args.port, args.mode, args.ngrok_token)
    elif args.command == "stop":
        launcher.stop()
    elif args.command == "status":
        launcher.status()
    elif args.command == "logs":
        launcher.logs()


if __name__ == "__main__":
    main()
