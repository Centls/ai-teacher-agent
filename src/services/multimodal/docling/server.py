# -*- coding: utf-8 -*-
"""
Docling Multimodal Service

Unified document/image/audio processing service based on Docling and Whisper.
- Documents & Images: Processed by Docling
- Audio: Processed by OpenAI Whisper

External Dependencies:
    - docling (https://github.com/DS4SD/docling)
    - openai-whisper (https://github.com/openai/whisper)
"""

import asyncio
import logging
import os
import platform
from pathlib import Path
from typing import Optional, Dict, Any

# =============================================================================
# Environment Configuration (must be set before importing docling/huggingface)
# =============================================================================
DOCLING_DIR = Path(__file__).parent
MODELS_DIR = DOCLING_DIR / "models"

# HuggingFace cache directory
os.environ.setdefault("HF_HOME", str(MODELS_DIR / "huggingface"))
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # China mirror

# RapidOCR model directory (based on PaddleOCR, better Chinese recognition)
RAPIDOCR_MODELS_DIR = MODELS_DIR / "rapidocr"
RAPIDOCR_MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Add ffmpeg to PATH for Whisper audio processing
ffmpeg_bin = MODELS_DIR / "ffmpeg" / "bin"
if ffmpeg_bin.exists():
    os.environ["PATH"] = str(ffmpeg_bin) + os.pathsep + os.environ.get("PATH", "")

# Windows path fix for docling-parse
IS_WINDOWS = platform.system() == "Windows"

def fix_windows_path(file_path: str) -> str:
    """
    Fix Windows path for docling-parse compatibility.
    docling-parse has a bug with backslash path separators on Windows.
    Convert backslashes to forward slashes.
    """
    if IS_WINDOWS:
        return file_path.replace("\\", "/")
    return file_path

from fastapi import FastAPI
from pydantic import BaseModel

# =============================================================================
# External Dependencies
# =============================================================================
from docling.document_converter import DocumentConverter, PdfFormatOption, InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

# Try to import RapidOCR for better Chinese recognition
try:
    from docling.datamodel.pipeline_options import RapidOcrOptions
    RAPIDOCR_AVAILABLE = True
    logger_temp = logging.getLogger(__name__)
    logger_temp.info("RapidOCR available - will use for better Chinese OCR")
except ImportError:
    RAPIDOCR_AVAILABLE = False

# On Windows, use pypdfium2 backend due to docling-parse resource path bug
if IS_WINDOWS:
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

import whisper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Docling Multimodal Service", version="1.0.0")


class ParseRequest(BaseModel):
    """Document parse request"""
    file_path: str
    metadata: Optional[Dict[str, Any]] = None


class ParseResponse(BaseModel):
    """Document parse response"""
    success: bool
    text: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


# =============================================================================
# Global Instances (Lazy Loaded)
# =============================================================================
_converter: Optional[DocumentConverter] = None
_whisper_model = None


def get_converter() -> DocumentConverter:
    """Get or create Docling DocumentConverter instance"""
    global _converter
    if _converter is None:
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True  # Enable OCR for scanned documents

        # Use RapidOCR (based on PaddleOCR) for better Chinese recognition
        if RAPIDOCR_AVAILABLE:
            logger.info("Configuring RapidOCR for better Chinese recognition...")
            pipeline_options.ocr_options = RapidOcrOptions()
            ocr_engine = "RapidOCR"
        else:
            logger.warning("RapidOCR not available, using default EasyOCR")
            ocr_engine = "EasyOCR"

        if IS_WINDOWS:
            # Windows: use pypdfium2 backend due to docling-parse resource path bug
            logger.info(f"Initializing Docling DocumentConverter (pypdfium2 + {ocr_engine})...")
            _converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options,
                        backend=PyPdfiumDocumentBackend
                    )
                }
            )
            logger.info(f"Docling DocumentConverter initialized (pypdfium2 + {ocr_engine})")
        else:
            # Linux/macOS: use docling-parse (default) for better PDF parsing
            logger.info(f"Initializing Docling DocumentConverter (docling-parse + {ocr_engine})...")
            _converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(
                        pipeline_options=pipeline_options
                    )
                }
            )
            logger.info(f"Docling DocumentConverter initialized (docling-parse + {ocr_engine})")
    return _converter


def get_whisper_model(model_name: str = "small"):
    """
    Get or create Whisper model instance.
    Defaults to 'small' for better Chinese accuracy (requires ~2GB VRAM/RAM).
    Use 'large-v3-turbo' if you have a GPU with 6GB+ VRAM.
    """
    global _whisper_model
    if _whisper_model is None:
        logger.info(f"Loading Whisper model ({model_name})...")
        try:
            # Use custom download directory instead of ~/.cache/whisper
            whisper_cache = DOCLING_DIR / "models" / "whisper"
            whisper_cache.mkdir(parents=True, exist_ok=True)
            _whisper_model = whisper.load_model(model_name, download_root=str(whisper_cache))
            logger.info("Whisper model loaded")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise
    return _whisper_model


@app.on_event("startup")
async def startup():
    """Pre-initialize services on startup"""
    # Pre-load Docling (fast)
    get_converter()
    # Whisper model is lazy loaded to save startup time and memory if not used
    logger.info("Docling service started on port 8010")


@app.get("/health")
async def health():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "service": "docling-multimodal",
        "components": {
            "docling": _converter is not None,
            "whisper": _whisper_model is not None
        }
    }
    return status


# =============================================================================
# Synchronous Processing Functions (run in thread pool)
# =============================================================================

def _sync_parse_document(file_path: str, converter: DocumentConverter) -> tuple:
    """Synchronous document parsing to run in thread pool"""
    # Fix Windows path for docling-parse compatibility
    fixed_path = fix_windows_path(file_path)
    result = converter.convert(fixed_path)
    text = result.document.export_to_markdown()
    page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 1
    return text, page_count


def _sync_transcribe(file_path: str, model) -> dict:
    """Synchronous transcription function to run in thread pool"""
    return model.transcribe(file_path)


@app.post("/parse", response_model=ParseResponse)
async def parse_document(request: ParseRequest):
    """
    Parse document using Docling.
    Supports PDF, DOCX, PPTX, XLSX, HTML, Markdown, Images.
    Runs in background thread to avoid blocking other requests.
    """
    file_path = Path(request.file_path)

    if not file_path.exists():
        return ParseResponse(success=False, text="", metadata={}, error=f"File not found: {file_path}")

    try:
        converter = get_converter()
        logger.info(f"Parsing document: {file_path.name}")

        # Run CPU-intensive parsing in thread pool to avoid blocking
        text, page_count = await asyncio.to_thread(_sync_parse_document, str(file_path), converter)

        # Log parse result (show first 200 chars)
        preview = text[:200] + "..." if len(text) > 200 else text
        logger.info(f"Parse complete: {file_path.name}, {page_count} pages, {len(text)} chars")
        logger.info(f"Content preview: {preview}")

        return ParseResponse(
            success=True,
            text=text,
            metadata={
                "source": "docling",
                "file_name": file_path.name,
                "file_type": file_path.suffix.lower(),
                "page_count": page_count,
                **(request.metadata or {})
            }
        )
    except Exception as e:
        logger.error(f"Docling processing failed: {e}")
        return ParseResponse(success=False, text="", metadata={}, error=str(e))


@app.post("/ocr", response_model=ParseResponse)
async def ocr_image(request: ParseRequest):
    """OCR image using Docling (alias for /parse)"""
    return await parse_document(request)


@app.post("/transcribe", response_model=ParseResponse)
async def transcribe_audio(request: ParseRequest):
    """
    Transcribe audio using Whisper.
    Supports MP3, WAV, M4A, FLAC, OGG.
    Runs in background thread to avoid blocking other requests.
    """
    file_path = Path(request.file_path)

    if not file_path.exists():
        return ParseResponse(success=False, text="", metadata={}, error=f"File not found: {file_path}")

    try:
        # Load model (lazy) - using 'base' model for balance of speed/accuracy
        model = get_whisper_model("base")

        logger.info(f"Transcribing audio: {file_path.name}")

        # Run CPU-intensive transcription in thread pool to avoid blocking
        result = await asyncio.to_thread(_sync_transcribe, str(file_path), model)
        text = result["text"].strip()

        # Log transcription result (show first 200 chars)
        lang = result.get("language", "unknown")
        preview = text[:200] + "..." if len(text) > 200 else text
        logger.info(f"Transcription complete: lang={lang}, {len(text)} chars")
        logger.info(f"Content preview: {preview}")

        return ParseResponse(
            success=True,
            text=text,
            metadata={
                "source": "whisper",
                "file_name": file_path.name,
                "file_type": file_path.suffix.lower(),
                "language": result.get("language", "unknown"),
                **(request.metadata or {})
            }
        )
    except Exception as e:
        logger.error(f"Whisper transcription failed: {e}")
        return ParseResponse(success=False, text="", metadata={}, error=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
