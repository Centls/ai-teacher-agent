# -*- coding: utf-8 -*-
"""
文档解析服务 - 基于 MinerU

本服务直接复用 MinerU (https://github.com/opendatalab/MinerU) 的全部能力。
仅编写最小必要的 FastAPI 服务层代码，不实现任何文档解析逻辑。

MinerU 提供的核心能力（直接复用）：
    - PDF 解析：文本、表格、公式、图片提取
    - 多格式支持：PDF/Word/Excel/PPT
    - 中文优化：109 种语言 OCR
    - 输出格式：Markdown/JSON

依赖来源: https://github.com/opendatalab/MinerU
"""

import os
import sys
import logging
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ============================================================
# 外部依赖导入 - 直接复用 MinerU
# ============================================================
# MinerU 核心模块，提供完整的文档解析能力
# 不做任何封装或逻辑修改，直接调用原库 API
from magic_pdf.data.data_reader_writer import FileBasedDataReader, FileBasedDataWriter
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="文档解析服务",
    description="基于 MinerU 的文档解析服务，支持 PDF/Word/Excel/PPT",
    version="1.0.0"
)


class ParseRequest(BaseModel):
    """解析请求"""
    file_path: str
    metadata: Optional[Dict[str, Any]] = None


class ParseResponse(BaseModel):
    """解析响应"""
    success: bool
    text: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "doc"}


@app.post("/parse", response_model=ParseResponse)
async def parse_document(request: ParseRequest):
    """
    解析文档

    直接调用 MinerU 的 API 完成解析，本函数仅负责：
    1. 参数校验
    2. 调用 MinerU
    3. 格式化返回结果

    所有解析逻辑由 MinerU 库完成。
    """
    file_path = Path(request.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

    supported_formats = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}
    if file_path.suffix.lower() not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式: {file_path.suffix}，支持: {supported_formats}"
        )

    try:
        # ============================================================
        # 直接调用 MinerU API - 不做任何逻辑修改
        # ============================================================

        # 读取文件
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(str(file_path))

        # 创建数据集
        dataset = PymuDocDataset(pdf_bytes)

        # 文档分析（使用 MinerU 内置模型）
        # MinerU 会自动处理：OCR、表格识别、公式提取等
        infer_result = doc_analyze(
            dataset,
            ocr=True,  # 启用 OCR
            show_log=False,
        )

        # 使用临时目录存储输出
        with tempfile.TemporaryDirectory() as temp_dir:
            writer = FileBasedDataWriter(temp_dir)

            # 获取解析结果
            # MinerU 返回完整的文档结构，包含文本、表格、图片等
            if dataset.classify() == "ocr":
                # OCR 模式（扫描件 PDF）
                pipe_result = infer_result.pipe_ocr_mode(writer)
            else:
                # 文本模式（普通 PDF）
                pipe_result = infer_result.pipe_txt_mode(writer)

            # 获取 Markdown 格式文本
            markdown_text = pipe_result.get_markdown()

            # 获取元数据
            content_list = pipe_result.get_content_list()

        # ============================================================

        return ParseResponse(
            success=True,
            text=markdown_text,
            metadata={
                "file_name": file_path.name,
                "file_size": file_path.stat().st_size,
                "page_count": len(content_list) if content_list else 0,
                "parse_mode": dataset.classify(),
                "source": "MinerU",
                **(request.metadata or {})
            }
        )

    except ImportError as e:
        logger.error(f"MinerU 导入失败: {e}")
        return ParseResponse(
            success=False,
            text="",
            metadata={},
            error=f"MinerU 未正确安装: {e}"
        )
    except Exception as e:
        logger.error(f"文档解析失败: {e}")
        return ParseResponse(
            success=False,
            text="",
            metadata={},
            error=str(e)
        )


if __name__ == "__main__":
    port = int(os.environ.get("SERVICE_PORT", 8010))
    logger.info(f"启动文档解析服务，端口: {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
