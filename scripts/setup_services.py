#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多模态子服务环境一键初始化脚本

用法：
    python scripts/setup_services.py              # 初始化所有服务
    python scripts/setup_services.py --doc        # 只初始化文档服务
    python scripts/setup_services.py --ocr        # 只初始化OCR服务
    python scripts/setup_services.py --asr        # 只初始化ASR服务
    python scripts/setup_services.py --clean      # 清理所有环境重建
    python scripts/setup_services.py --verify     # 验证所有环境

依赖来源：
    - doc: MinerU (https://github.com/opendatalab/MinerU)
    - ocr: PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR)
    - asr: FunASR (https://github.com/modelscope/FunASR)
"""

import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path
from typing import List, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
MULTIMODAL_DIR = PROJECT_ROOT / "src" / "services" / "multimodal"

# 服务配置
SERVICES = {
    "doc": {
        "name": "doc-service",
        "description": "MinerU document parser for PDF/Word/Excel/PPT",
        "port": 8010,
        "venv_dir": MULTIMODAL_DIR / "doc" / ".venv",
        "requirements": MULTIMODAL_DIR / "doc" / "requirements.txt",
    },
    "ocr": {
        "name": "ocr-service",
        "description": "PaddleOCR image text recognition",
        "port": 8011,
        "venv_dir": MULTIMODAL_DIR / "ocr" / ".venv",
        "requirements": MULTIMODAL_DIR / "ocr" / "requirements.txt",
    },
    "asr": {
        "name": "asr-service",
        "description": "FunASR speech to text",
        "port": 8012,
        "venv_dir": MULTIMODAL_DIR / "asr" / ".venv",
        "requirements": MULTIMODAL_DIR / "asr" / "requirements.txt",
    },
}


def get_python_executable() -> str:
    """Get Python executable path"""
    if sys.platform == "win32":
        return "python"
    return "python3"


def get_venv_python(venv_dir: Path) -> Path:
    """Get Python path in virtual environment"""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def get_venv_pip(venv_dir: Path) -> Path:
    """Get pip path in virtual environment"""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"


def run_command(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> bool:
    """Execute command and return success status"""
    try:
        print(f"  Running: {' '.join(str(c) for c in cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env or os.environ.copy(),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"  Exception: {e}")
        return False


def create_venv(venv_dir: Path) -> bool:
    """Create virtual environment"""
    if venv_dir.exists():
        print(f"  Venv exists: {venv_dir}")
        return True

    print(f"  Creating venv: {venv_dir}")
    python = get_python_executable()
    return run_command([python, "-m", "venv", str(venv_dir)])


def get_utf8_env() -> dict:
    """Get environment with UTF-8 encoding for Windows C++ compilation"""
    env = os.environ.copy()
    if sys.platform == "win32":
        # 设置 UTF-8 编码环境，解决 C++ 源码编译时的编码问题
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # 设置 MSVC 编译器使用 UTF-8
        env["CFLAGS"] = env.get("CFLAGS", "") + " /utf-8"
        env["CXXFLAGS"] = env.get("CXXFLAGS", "") + " /utf-8"
    return env


def install_requirements(venv_dir: Path, requirements: Path, service_name: str = "") -> bool:
    """Install dependencies"""
    if not requirements.exists():
        print(f"  requirements.txt not found: {requirements}")
        return False

    pip = get_venv_pip(venv_dir)
    if not pip.exists():
        print(f"  pip not found: {pip}")
        return False

    print(f"  Installing dependencies: {requirements}")

    # 使用 UTF-8 环境（解决 Windows 下 C++ 编译编码问题）
    env = get_utf8_env()

    # Upgrade pip first (use python -m pip to avoid permission issues)
    python = get_venv_python(venv_dir)
    run_command([str(python), "-m", "pip", "install", "--upgrade", "pip"], env=env)

    # Install dependencies
    return run_command([str(pip), "install", "-r", str(requirements)], env=env)


def verify_service(service_name: str, config: dict) -> bool:
    """Verify service environment is correct"""
    venv_dir = config["venv_dir"]
    python = get_venv_python(venv_dir)

    if not python.exists():
        print(f"  [FAIL] Python not found: {python}")
        return False

    # Verify core dependencies by service type
    verify_scripts = {
        "doc": "from magic_pdf.data.data_reader_writer import FileBasedDataReader; print('MinerU OK')",
        "ocr": "from paddleocr import PaddleOCR; print('PaddleOCR OK')",
        "asr": "from funasr import AutoModel; print('FunASR OK')",
    }

    script = verify_scripts.get(service_name)
    if not script:
        return True

    result = subprocess.run(
        [str(python), "-c", script],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"  [OK] {config['name']} verified")
        return True
    else:
        print(f"  [FAIL] {config['name']} verification failed: {result.stderr}")
        return False


def setup_service(service_name: str, config: dict) -> bool:
    """Initialize single service"""
    print(f"\n{'='*60}")
    print(f"Initializing {config['name']} ({service_name})")
    print(f"Description: {config['description']}")
    print(f"Port: {config['port']}")
    print(f"{'='*60}")

    # 1. Create virtual environment
    if not create_venv(config["venv_dir"]):
        return False

    # 2. Install dependencies
    if not install_requirements(config["venv_dir"], config["requirements"]):
        return False

    # 3. Verify installation
    if not verify_service(service_name, config):
        print(f"  [WARN] Verification failed, but environment created. May need manual check.")

    print(f"\n[OK] {config['name']} initialized")
    return True


def clean_service(service_name: str, config: dict) -> bool:
    """Clean service environment"""
    venv_dir = config["venv_dir"]
    if venv_dir.exists():
        print(f"  Cleaning venv: {venv_dir}")
        shutil.rmtree(venv_dir)
        print(f"  [OK] Cleaned")
    else:
        print(f"  Venv not exists, skipping")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Multimodal service environment setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/setup_services.py              # Initialize all services
    python scripts/setup_services.py --doc        # Initialize doc service only
    python scripts/setup_services.py --ocr        # Initialize OCR service only
    python scripts/setup_services.py --asr        # Initialize ASR service only
    python scripts/setup_services.py --clean      # Clean all environments
    python scripts/setup_services.py --verify     # Verify all environments
        """
    )

    parser.add_argument("--doc", action="store_true", help="Initialize doc service only")
    parser.add_argument("--ocr", action="store_true", help="Initialize OCR service only")
    parser.add_argument("--asr", action="store_true", help="Initialize ASR service only")
    parser.add_argument("--clean", action="store_true", help="Clean all environments and rebuild")
    parser.add_argument("--verify", action="store_true", help="Verify environments only")

    args = parser.parse_args()

    # Determine services to process
    if args.doc or args.ocr or args.asr:
        services_to_process = []
        if args.doc:
            services_to_process.append("doc")
        if args.ocr:
            services_to_process.append("ocr")
        if args.asr:
            services_to_process.append("asr")
    else:
        services_to_process = list(SERVICES.keys())

    print("=" * 60)
    print("Multimodal Service Environment Setup")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Multimodal dir: {MULTIMODAL_DIR}")
    print(f"Services to process: {', '.join(services_to_process)}")

    success_count = 0
    fail_count = 0

    for service_name in services_to_process:
        config = SERVICES[service_name]

        if args.clean:
            clean_service(service_name, config)

        if args.verify:
            if verify_service(service_name, config):
                success_count += 1
            else:
                fail_count += 1
        else:
            if setup_service(service_name, config):
                success_count += 1
            else:
                fail_count += 1

    print("\n" + "=" * 60)
    print("Result")
    print("=" * 60)
    print(f"Success: {success_count}")
    print(f"Failed: {fail_count}")

    if fail_count > 0:
        print("\n[WARN] Some services failed to initialize. Check error messages above.")
        sys.exit(1)
    else:
        print("\n[OK] All services initialized successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
