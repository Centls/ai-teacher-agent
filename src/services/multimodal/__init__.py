# -*- coding: utf-8 -*-
"""
多模态服务模块

提供文档解析、图片OCR、音频ASR等多模态处理能力。
采用微服务架构，各服务独立环境，通过HTTP通信。

依赖来源：
    - doc: MinerU (https://github.com/opendatalab/MinerU)
    - ocr: PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR)
    - asr: FunASR (https://github.com/modelscope/FunASR)
"""

from .manager import ServiceManager
from .client import MultimodalClient
from .sync_client import MultimodalSyncClient

__all__ = ["ServiceManager", "MultimodalClient", "MultimodalSyncClient"]
