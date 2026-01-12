# -*- coding: utf-8 -*-
"""
多模态服务同步客户端

提供同步版本的多模态处理接口，用于与现有 RAGPipeline 集成。

依赖来源：
    - doc: MinerU (https://github.com/opendatalab/MinerU)
    - ocr: PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR)
    - asr: FunASR (https://github.com/modelscope/FunASR)
"""

import logging
import httpx
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from .manager import ServiceManager

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@dataclass
class ProcessResult:
    """处理结果"""
    success: bool
    text: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


class MultimodalSyncClient:
    """
    多模态服务同步客户端

    与 MultimodalClient 功能相同，但提供同步接口，
    用于与现有同步代码（如 RAGPipeline）集成。
    """

    # 文件格式到服务的映射
    FORMAT_SERVICE_MAP = {
        # 图片格式 -> ocr 服务
        ".jpg": "ocr",
        ".jpeg": "ocr",
        ".png": "ocr",
        ".bmp": "ocr",
        ".gif": "ocr",
        ".tiff": "ocr",
        # 音频格式 -> asr 服务
        ".mp3": "asr",
        ".wav": "asr",
        ".m4a": "asr",
        ".flac": "asr",
        ".ogg": "asr",
        ".wma": "asr",
    }

    def __init__(self):
        self._manager = ServiceManager()

    def _get_service_url(self, service_name: str) -> Optional[str]:
        """获取服务 URL"""
        return self._manager.get_service_url(service_name)

    def is_multimodal_file(self, file_path: str) -> bool:
        """判断是否是多模态文件（图片/音频）"""
        ext = Path(file_path).suffix.lower()
        return ext in self.FORMAT_SERVICE_MAP

    def get_service_for_file(self, file_path: str) -> Optional[str]:
        """根据文件扩展名确定使用的服务"""
        ext = Path(file_path).suffix.lower()
        return self.FORMAT_SERVICE_MAP.get(ext)

    def process_file(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: int = 300
    ) -> ProcessResult:
        """
        同步处理文件

        Args:
            file_path: 文件路径
            metadata: 附加元数据
            timeout: 超时时间（秒）

        Returns:
            ProcessResult: 处理结果
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"文件不存在: {file_path}"
            )

        service_name = self.get_service_for_file(str(file_path))
        if not service_name:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"不支持的文件格式: {file_path.suffix}"
            )

        if service_name == "ocr":
            return self.ocr_image(str(file_path), metadata, timeout)
        elif service_name == "asr":
            return self.transcribe_audio(str(file_path), metadata, timeout)
        else:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"未知服务: {service_name}"
            )

    def ocr_image(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: int = 60
    ) -> ProcessResult:
        """
        同步 OCR 识别

        底层调用 PaddleOCR 库完成实际识别工作。
        """
        url = self._get_service_url("ocr")
        if not url:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="OCR 服务未启动，请先运行 python scripts/setup_services.py --ocr"
            )

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{url}/ocr",
                    json={
                        "file_path": str(Path(file_path).absolute()),
                        "metadata": metadata or {}
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return ProcessResult(
                        success=data.get("success", True),
                        text=data.get("text", ""),
                        metadata=data.get("metadata", {})
                    )
                else:
                    return ProcessResult(
                        success=False,
                        text="",
                        metadata={},
                        error=f"OCR 服务返回错误: {response.status_code}"
                    )

        except httpx.ConnectError:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="OCR 服务连接失败，请检查服务是否启动"
            )
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"OCR 识别失败: {str(e)}"
            )

    def transcribe_audio(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: int = 600
    ) -> ProcessResult:
        """
        同步音频转写

        底层调用 FunASR 库完成实际转写工作。
        """
        url = self._get_service_url("asr")
        if not url:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="ASR 服务未启动，请先运行 python scripts/setup_services.py --asr"
            )

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{url}/transcribe",
                    json={
                        "file_path": str(Path(file_path).absolute()),
                        "metadata": metadata or {}
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return ProcessResult(
                        success=data.get("success", True),
                        text=data.get("text", ""),
                        metadata=data.get("metadata", {})
                    )
                else:
                    return ProcessResult(
                        success=False,
                        text="",
                        metadata={},
                        error=f"ASR 服务返回错误: {response.status_code}"
                    )

        except httpx.ConnectError:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="ASR 服务连接失败，请检查服务是否启动"
            )
        except Exception as e:
            logger.error(f"音频转写失败: {e}")
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"音频转写失败: {str(e)}"
            )

    def get_supported_formats(self) -> List[str]:
        """获取支持的文件格式"""
        return list(self.FORMAT_SERVICE_MAP.keys())
