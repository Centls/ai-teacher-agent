# -*- coding: utf-8 -*-
"""
多模态服务统一客户端

职责：
    - 提供统一的多模态处理接口
    - 封装 HTTP 调用逻辑
    - 处理重试和降级

本模块仅负责 HTTP 调用编排，不实现任何多模态处理逻辑。
所有处理逻辑由各子服务通过复用外部库完成。

依赖来源：
    - doc: MinerU (https://github.com/opendatalab/MinerU)
    - ocr: PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR)
    - asr: FunASR (https://github.com/modelscope/FunASR)
"""

import os
import logging
import httpx
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
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


class MultimodalClient:
    """
    多模态服务统一客户端

    提供统一接口调用各多模态子服务，自动选择合适的服务处理文件。

    使用示例：
        client = MultimodalClient()

        # 处理 PDF 文档
        result = await client.process_file("data/example.pdf")

        # 处理图片 OCR
        result = await client.process_file("data/image.png")

        # 处理音频转写
        result = await client.process_file("data/audio.mp3")

        # 或直接调用特定服务
        result = await client.ocr_image("data/image.png")
    """

    # 文件格式到服务的映射
    FORMAT_SERVICE_MAP = {
        # 文档格式 -> doc 服务
        ".pdf": "doc",
        ".docx": "doc",
        ".doc": "doc",
        ".xlsx": "doc",
        ".xls": "doc",
        ".pptx": "doc",
        ".ppt": "doc",
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
        self._shared_data_dir = PROJECT_ROOT / "data" / "multimodal"
        self._shared_data_dir.mkdir(parents=True, exist_ok=True)

    def _get_service_url(self, service_name: str) -> Optional[str]:
        """获取服务 URL"""
        return self._manager.get_service_url(service_name)

    def _get_service_for_file(self, file_path: str) -> Optional[str]:
        """根据文件扩展名确定使用的服务"""
        ext = Path(file_path).suffix.lower()
        return self.FORMAT_SERVICE_MAP.get(ext)

    async def process_file(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """
        处理文件（自动选择服务）

        Args:
            file_path: 文件路径
            metadata: 附加元数据

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

        service_name = self._get_service_for_file(str(file_path))
        if not service_name:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"不支持的文件格式: {file_path.suffix}"
            )

        # 根据服务类型调用对应方法
        if service_name == "doc":
            return await self.parse_document(str(file_path), metadata)
        elif service_name == "ocr":
            return await self.ocr_image(str(file_path), metadata)
        elif service_name == "asr":
            return await self.transcribe_audio(str(file_path), metadata)
        else:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"未知服务: {service_name}"
            )

    async def parse_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """
        解析文档（PDF/Word/Excel/PPT）

        底层调用 MinerU 库完成实际解析工作。
        本方法仅负责 HTTP 调用编排。

        Args:
            file_path: 文档路径
            metadata: 附加元数据

        Returns:
            ProcessResult: 解析结果，包含提取的文本和元数据
        """
        url = self._get_service_url("doc")
        if not url:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="文档解析服务未启动"
            )

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(
                    f"{url}/parse",
                    json={
                        "file_path": str(Path(file_path).absolute()),
                        "metadata": metadata or {}
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return ProcessResult(
                        success=True,
                        text=data.get("text", ""),
                        metadata=data.get("metadata", {})
                    )
                else:
                    return ProcessResult(
                        success=False,
                        text="",
                        metadata={},
                        error=f"服务返回错误: {response.status_code}"
                    )

        except httpx.ConnectError:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="文档解析服务连接失败"
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"文档解析失败: {str(e)}"
            )

    async def ocr_image(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """
        图片 OCR 识别

        底层调用 PaddleOCR 库完成实际识别工作。
        本方法仅负责 HTTP 调用编排。

        Args:
            file_path: 图片路径
            metadata: 附加元数据

        Returns:
            ProcessResult: 识别结果，包含提取的文本
        """
        url = self._get_service_url("ocr")
        if not url:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="OCR 服务未启动"
            )

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{url}/ocr",
                    json={
                        "file_path": str(Path(file_path).absolute()),
                        "metadata": metadata or {}
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return ProcessResult(
                        success=True,
                        text=data.get("text", ""),
                        metadata=data.get("metadata", {})
                    )
                else:
                    return ProcessResult(
                        success=False,
                        text="",
                        metadata={},
                        error=f"服务返回错误: {response.status_code}"
                    )

        except httpx.ConnectError:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="OCR 服务连接失败"
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"OCR 识别失败: {str(e)}"
            )

    async def transcribe_audio(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """
        音频转写

        底层调用 FunASR 库完成实际转写工作。
        本方法仅负责 HTTP 调用编排。

        Args:
            file_path: 音频路径
            metadata: 附加元数据

        Returns:
            ProcessResult: 转写结果，包含转写文本
        """
        url = self._get_service_url("asr")
        if not url:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="ASR 服务未启动"
            )

        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    f"{url}/transcribe",
                    json={
                        "file_path": str(Path(file_path).absolute()),
                        "metadata": metadata or {}
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return ProcessResult(
                        success=True,
                        text=data.get("text", ""),
                        metadata=data.get("metadata", {})
                    )
                else:
                    return ProcessResult(
                        success=False,
                        text="",
                        metadata={},
                        error=f"服务返回错误: {response.status_code}"
                    )

        except httpx.ConnectError:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="ASR 服务连接失败"
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"音频转写失败: {str(e)}"
            )

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """获取支持的文件格式"""
        formats = {"doc": [], "ocr": [], "asr": []}
        for ext, service in self.FORMAT_SERVICE_MAP.items():
            formats[service].append(ext)
        return formats

    def get_services_status(self) -> Dict[str, dict]:
        """获取所有服务状态"""
        return self._manager.get_service_status()
