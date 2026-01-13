# -*- coding: utf-8 -*-
"""
Multimodal Service Async Client

Provides async interface for multimodal processing.
All processing is delegated to the Docling unified service (includes Whisper for audio).

External Dependencies:
    - Docling (https://github.com/DS4SD/docling) - Documents & Images
    - Whisper (https://github.com/openai/whisper) - Audio (via Docling Service)
"""

import logging
import httpx
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@dataclass
class ProcessResult:
    """Processing result"""
    success: bool
    text: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


class MultimodalClient:
    """
    Multimodal Service Async Client

    Unified async client for document/image/audio processing via Docling service.
    - Documents & Images -> Docling
    - Audio -> Whisper (via Docling Service)
    """

    # Supported Formats
    DOCLING_FORMATS = {
        # Documents
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
        ".html", ".htm", ".md", ".markdown",
        # Images (OCR)
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif",
    }

    AUDIO_FORMATS = {
        # Audio (Whisper)
        ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"
    }

    def __init__(self):
        self._shared_data_dir = PROJECT_ROOT / "data" / "multimodal"
        self._shared_data_dir.mkdir(parents=True, exist_ok=True)
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load service configuration"""
        config_path = PROJECT_ROOT / "config" / "services.yaml"
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
        return {}

    def _get_service_url(self) -> Optional[str]:
        """Get Docling service URL"""
        try:
            service_cfg = self._config.get("multimodal", {}).get("services", {}).get("docling", {})
            host = service_cfg.get("host", "127.0.0.1")
            port = service_cfg.get("port", 8010)
            return f"http://{host}:{port}"
        except Exception:
            return "http://127.0.0.1:8010"

    def _get_service_for_file(self, file_path: str) -> Optional[str]:
        """Get service name for file (always 'docling' for supported formats)"""
        ext = Path(file_path).suffix.lower()
        if ext in self.DOCLING_FORMATS or ext in self.AUDIO_FORMATS:
            return "docling"
        return None

    async def process_file(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """
        Process file using Docling service.

        Args:
            file_path: File path
            metadata: Additional metadata
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"File not found: {file_path}"
            )

        ext = file_path.suffix.lower()

        # Audio -> /transcribe endpoint
        if ext in self.AUDIO_FORMATS:
            return await self.transcribe_audio(str(file_path), metadata)

        # Docling -> /parse endpoint
        if ext in self.DOCLING_FORMATS:
            return await self._call_docling_parse(str(file_path), metadata)

        # Unsupported
        return ProcessResult(
            success=False,
            text="",
            metadata={},
            error=f"Unsupported format: {ext}"
        )

    async def _call_docling_parse(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """Call Docling service /parse endpoint"""
        return await self._call_endpoint("/parse", file_path, metadata, timeout=300)

    async def transcribe_audio(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """Call Docling service /transcribe endpoint"""
        # Audio processing might take longer
        return await self._call_endpoint("/transcribe", file_path, metadata, timeout=600)

    async def _call_endpoint(
        self,
        endpoint: str,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: int = 300
    ) -> ProcessResult:
        """Generic endpoint call"""
        url = self._get_service_url()

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{url}{endpoint}",
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
                        metadata=data.get("metadata", {}),
                        error=data.get("error")
                    )
                else:
                    return ProcessResult(
                        success=False,
                        text="",
                        metadata={},
                        error=f"Service error ({endpoint}): {response.status_code}"
                    )

        except httpx.ConnectError:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error="Service connection failed"
            )
        except Exception as e:
            return ProcessResult(
                success=False,
                text="",
                metadata={},
                error=f"Processing failed: {str(e)}"
            )

    # Backward compatibility aliases
    async def parse_document(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """Parse document (alias for process_file)"""
        return await self.process_file(file_path, metadata)

    async def ocr_image(
        self,
        file_path: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ProcessResult:
        """OCR image (alias for process_file)"""
        return await self.process_file(file_path, metadata)

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """Get supported file formats by category"""
        return {
            "document": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".html", ".htm", ".md", ".markdown"],
            "image": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif"],
            "audio": [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"]
        }
