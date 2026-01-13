# -*- coding: utf-8 -*-
"""
Multimodal Service Module

Provides document parsing, OCR, and audio transcription via Docling unified service.

Architecture:
    - Unified Service (Docling + Whisper)
    - Manual startup required (no auto-start)
    - HTTP-based communication

Dependencies:
    - Docling: https://github.com/DS4SD/docling
    - Whisper: https://github.com/openai/whisper
"""

from .client import MultimodalClient
from .sync_client import MultimodalSyncClient

__all__ = ["MultimodalClient", "MultimodalSyncClient"]
