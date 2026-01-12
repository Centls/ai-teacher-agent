# -*- coding: utf-8 -*-
"""
多模态子服务管理器

职责：
    - 自动拉起子服务进程
    - 健康检查
    - 优雅关闭

本模块仅负责进程管理，不实现任何多模态处理逻辑。
所有处理逻辑由各子服务通过复用外部库完成。
"""

import os
import sys
import subprocess
import atexit
import time
import signal
import logging
import httpx
import yaml
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@dataclass
class ServiceInfo:
    """服务信息"""
    name: str
    port: int
    host: str
    venv: Path
    script: Path
    enabled: bool
    auto_start: bool  # 是否随主服务自动启动
    timeout: int
    process: Optional[subprocess.Popen] = None


class ServiceManager:
    """
    多模态子服务管理器

    单例模式，主服务启动时自动拉起所有子服务，
    主服务退出时自动关闭所有子服务。

    使用示例：
        manager = ServiceManager()
        manager.start_services()  # 启动所有子服务
        # ... 业务逻辑 ...
        manager.stop_services()   # 停止所有子服务（或自动在进程退出时停止）
    """

    _instance: Optional["ServiceManager"] = None

    def __new__(cls) -> "ServiceManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._services: Dict[str, ServiceInfo] = {}
        self._config: dict = {}
        self._load_config()

        # 注册退出时自动关闭
        atexit.register(self.stop_services)
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理器，优雅关闭"""
        logger.info(f"收到信号 {signum}，正在关闭子服务...")
        self.stop_services()
        sys.exit(0)

    def _load_config(self):
        """加载服务配置"""
        config_path = PROJECT_ROOT / "config" / "services.yaml"

        if not config_path.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            return

        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        multimodal_config = self._config.get("multimodal", {})
        services_config = multimodal_config.get("services", {})

        for service_name, service_cfg in services_config.items():
            if not service_cfg.get("enabled", True):
                continue

            venv_path = PROJECT_ROOT / service_cfg["venv"]
            script_path = PROJECT_ROOT / service_cfg["script"]

            self._services[service_name] = ServiceInfo(
                name=service_cfg["name"],
                port=service_cfg["port"],
                host=service_cfg.get("host", "127.0.0.1"),
                venv=venv_path,
                script=script_path,
                enabled=service_cfg.get("enabled", True),
                auto_start=service_cfg.get("auto_start", False),  # 默认不自动启动
                timeout=service_cfg.get("timeout", 60),
            )

    def _get_python_executable(self, venv_path: Path) -> Path:
        """获取虚拟环境中的 Python 路径"""
        if sys.platform == "win32":
            return venv_path / "Scripts" / "python.exe"
        return venv_path / "bin" / "python"

    def _check_service_health(self, service_name: str) -> bool:
        """检查服务健康状态"""
        service = self._services.get(service_name)
        if not service:
            return False

        try:
            url = f"http://{service.host}:{service.port}/health"
            response = httpx.get(url, timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def _wait_for_service(self, service_name: str, max_wait: int = 30) -> bool:
        """等待服务就绪"""
        for _ in range(max_wait):
            if self._check_service_health(service_name):
                return True
            time.sleep(1)
        return False

    def start_service(self, service_name: str) -> bool:
        """启动单个子服务"""
        service = self._services.get(service_name)
        if not service:
            logger.error(f"服务不存在: {service_name}")
            return False

        if service.process and service.process.poll() is None:
            logger.info(f"服务已在运行: {service_name}")
            return True

        python = self._get_python_executable(service.venv)
        if not python.exists():
            logger.error(f"Python 不存在，请先运行 setup_services.py: {python}")
            return False

        if not service.script.exists():
            logger.error(f"服务脚本不存在: {service.script}")
            return False

        logger.info(f"启动服务: {service.name} (端口 {service.port})")

        try:
            # 启动子进程
            process = subprocess.Popen(
                [str(python), str(service.script)],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**os.environ, "SERVICE_PORT": str(service.port)},
            )
            service.process = process

            # 等待服务就绪
            if self._wait_for_service(service_name, max_wait=30):
                logger.info(f"✅ {service.name} 启动成功 (PID: {process.pid})")
                return True
            else:
                logger.warning(f"⚠️ {service.name} 健康检查超时，但进程已启动")
                return True

        except Exception as e:
            logger.error(f"启动服务失败 {service_name}: {e}")
            return False

    def stop_service(self, service_name: str) -> bool:
        """停止单个子服务"""
        service = self._services.get(service_name)
        if not service:
            return False

        if not service.process:
            return True

        if service.process.poll() is not None:
            # 进程已经退出
            service.process = None
            return True

        logger.info(f"停止服务: {service.name}")

        try:
            service.process.terminate()
            service.process.wait(timeout=10)
            logger.info(f"✅ {service.name} 已停止")
        except subprocess.TimeoutExpired:
            logger.warning(f"服务 {service.name} 未响应，强制终止")
            service.process.kill()
        except Exception as e:
            logger.error(f"停止服务失败 {service_name}: {e}")
            return False

        service.process = None
        return True

    def start_services(self) -> bool:
        """启动所有配置为自动启动的子服务"""
        if not self._config.get("multimodal", {}).get("enabled", True):
            logger.info("多模态服务已禁用")
            return True

        if not self._config.get("multimodal", {}).get("auto_start", True):
            logger.info("多模态服务自动启动已禁用")
            return True

        logger.info("=" * 50)
        logger.info("启动多模态子服务")
        logger.info("=" * 50)

        # 只启动配置为 auto_start=true 的服务
        auto_start_services = [
            name for name, info in self._services.items()
            if info.auto_start
        ]

        if not auto_start_services:
            logger.info("没有配置自动启动的服务")
            return True

        success_count = 0
        for service_name in auto_start_services:
            if self.start_service(service_name):
                success_count += 1

        # 提示手动启动的服务
        manual_services = [
            name for name, info in self._services.items()
            if not info.auto_start and info.enabled
        ]
        if manual_services:
            logger.info(f"以下服务需手动启动: {', '.join(manual_services)}")

        logger.info(f"自动启动完成: {success_count}/{len(auto_start_services)} 个服务")
        return success_count == len(auto_start_services)

    def stop_services(self):
        """停止所有子服务"""
        logger.info("停止所有多模态子服务")
        for service_name in self._services:
            self.stop_service(service_name)

    def get_service_status(self) -> Dict[str, dict]:
        """获取所有服务状态"""
        status = {}
        for service_name, service in self._services.items():
            is_running = service.process and service.process.poll() is None
            is_healthy = self._check_service_health(service_name) if is_running else False

            status[service_name] = {
                "name": service.name,
                "port": service.port,
                "running": is_running,
                "healthy": is_healthy,
                "pid": service.process.pid if service.process else None,
            }
        return status

    def get_service_url(self, service_name: str) -> Optional[str]:
        """获取服务 URL"""
        service = self._services.get(service_name)
        if not service:
            return None
        return f"http://{service.host}:{service.port}"
