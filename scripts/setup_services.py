#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Multimodal Service Environment Initialization Script

Initializes the unified Docling service environment.

Usage:
    python scripts/setup_services.py              # Initialize Docling service
    python scripts/setup_services.py --clean      # Clean environment and rebuild
    python scripts/setup_services.py --verify     # Verify environment

Dependencies:
    - Docling: https://github.com/DS4SD/docling
    - Whisper: https://github.com/openai/whisper
"""

import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path
from typing import List, Optional

# Project Root
PROJECT_ROOT = Path(__file__).parent.parent
MULTIMODAL_DIR = PROJECT_ROOT / "src" / "services" / "multimodal"

# Service Configuration
SERVICES = {
    "docling": {
        "name": "docling-service",
        "description": "Unified Docling Service (Document + OCR + Audio)",
        "port": 8010,
        "venv_dir": MULTIMODAL_DIR / "docling" / ".venv",
        "requirements": MULTIMODAL_DIR / "docling" / "requirements.txt",
    }
}


def get_base_python() -> str:
    """
    Get base Python executable for creating venvs.
    Prioritizes Python 3.11 from specific path if available.
    """
    # Specific path for this project's requirements
    specific_python = Path(r"D:\Python311\python.exe")
    if specific_python.exists():
        return str(specific_python)

    # Fallback
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
    python = get_base_python()
    print(f"  Using base python: {python}")
    return run_command([python, "-m", "venv", str(venv_dir)])


def get_utf8_env() -> dict:
    """Get environment with UTF-8 encoding"""
    env = os.environ.copy()
    if sys.platform == "win32":
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["CFLAGS"] = env.get("CFLAGS", "") + " /utf-8"
        env["CXXFLAGS"] = env.get("CXXFLAGS", "") + " /utf-8"
    return env


def install_requirements(venv_dir: Path, requirements: Path) -> bool:
    """Install dependencies"""
    if not requirements.exists():
        print(f"  requirements.txt not found: {requirements}")
        return False

    pip = get_venv_pip(venv_dir)
    if not pip.exists():
        print(f"  pip not found: {pip}")
        return False

    print(f"  Installing dependencies: {requirements}")

    env = get_utf8_env()

    # Upgrade pip
    python = get_venv_python(venv_dir)
    run_command([str(python), "-m", "pip", "install", "--upgrade", "pip"], env=env)

    # Install dependencies
    # Using specific PyTorch index URL for CPU version to save space if needed
    # But let requirements.txt handle it usually.
    # Here we just run pip install -r
    return run_command(
        [str(pip), "install", "-r", str(requirements), "--extra-index-url", "https://download.pytorch.org/whl/cpu"],
        env=env
    )


def verify_service(service_name: str, config: dict) -> bool:
    """Verify service environment is correct"""
    venv_dir = config["venv_dir"]
    python = get_venv_python(venv_dir)

    if not python.exists():
        print(f"  [FAIL] Python not found: {python}")
        return False

    # Verify Docling and Whisper
    script = """
import sys
try:
    from docling.document_converter import DocumentConverter
    print('Docling: OK')
except ImportError as e:
    print(f'Docling: FAIL ({e})')
    sys.exit(1)

try:
    import whisper
    print('Whisper: OK')
except ImportError as e:
    print(f'Whisper: FAIL ({e})')
    sys.exit(1)
"""

    result = subprocess.run(
        [str(python), "-c", script],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print(f"  [OK] {config['name']} verified")
        print(result.stdout.strip())
        return True
    else:
        print(f"  [FAIL] {config['name']} verification failed")
        print(result.stderr)
        return False


def setup_service(service_name: str, config: dict) -> bool:
    """Initialize single service"""
    print(f"\n{'='*60}")
    print(f"Initializing {config['name']}")
    print(f"Description: {config['description']}")
    print(f"Path: {config['venv_dir']}")
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
        description="Docling service environment setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/setup_services.py              # Initialize Docling service
    python scripts/setup_services.py --clean      # Clean environment and rebuild
    python scripts/setup_services.py --verify     # Verify environment
        """
    )

    parser.add_argument("--clean", action="store_true", help="Clean environment and rebuild")
    parser.add_argument("--verify", action="store_true", help="Verify environment only")

    args = parser.parse_args()

    # Only one service now
    service_name = "docling"
    config = SERVICES[service_name]

    print("=" * 60)
    print("Multimodal Service Setup (Docling Unified)")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")

    if args.clean:
        clean_service(service_name, config)

    success = False
    if args.verify:
        success = verify_service(service_name, config)
    else:
        success = setup_service(service_name, config)

    print("\n" + "=" * 60)
    print("Result")
    print("=" * 60)

    if success:
        print("\n[OK] Service setup completed successfully")
        sys.exit(0)
    else:
        print("\n[FAIL] Service setup failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
