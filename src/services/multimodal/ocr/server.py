# -*- coding: utf-8 -*-
"""
图片OCR服务 - 基于 PaddleOCR

本服务直接复用 PaddleOCR (https://github.com/PaddlePaddle/PaddleOCR) 的全部能力。
仅编写最小必要的 FastAPI 服务层代码，不实现任何 OCR 逻辑。

PaddleOCR 提供的核心能力（直接复用）：
    - 文字检测：支持倾斜、弯曲文本
    - 文字识别：中英文 95%+ 精度
    - 方向分类：自动校正图片方向
    - 表格识别：结构化表格提取
    - 公式识别：LaTeX 公式输出

依赖来源: https://github.com/PaddlePaddle/PaddleOCR
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ============================================================
# 外部依赖导入 - 直接复用 PaddleOCR
# ============================================================
# PaddleOCR 核心模块，提供完整的 OCR 能力
# 不做任何封装或逻辑修改，直接调用原库 API
from paddleocr import PaddleOCR

# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="图片OCR服务",
    description="基于 PaddleOCR 的图片文字识别服务",
    version="1.0.0"
)

# 全局 OCR 实例（避免重复加载模型）
# 直接使用 PaddleOCR 默认配置，中英文混合识别
_ocr_instance: Optional[PaddleOCR] = None


def get_ocr() -> PaddleOCR:
    """
    获取 PaddleOCR 实例

    使用 PaddleOCR 官方推荐配置，不做任何修改。
    """
    global _ocr_instance
    if _ocr_instance is None:
        # ============================================================
        # 直接使用 PaddleOCR 官方 API
        # 参数说明见: https://github.com/PaddlePaddle/PaddleOCR
        # ============================================================
        # 设置模型缓存目录（避免中文路径问题）
        import tempfile
        cache_dir = os.path.join(tempfile.gettempdir(), "paddleocr_models")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["PADDLEX_HOME"] = cache_dir
        os.environ["HF_HOME"] = cache_dir

        # 新版 PaddleOCR API（移除废弃参数）
        _ocr_instance = PaddleOCR(lang="ch")
    return _ocr_instance


class OCRRequest(BaseModel):
    """OCR 请求"""
    file_path: str
    metadata: Optional[Dict[str, Any]] = None


class OCRResponse(BaseModel):
    """OCR 响应"""
    success: bool
    text: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "ocr"}


@app.post("/ocr", response_model=OCRResponse)
async def ocr_image(request: OCRRequest):
    """
    图片 OCR 识别

    直接调用 PaddleOCR 的 API 完成识别，本函数仅负责：
    1. 参数校验
    2. 调用 PaddleOCR
    3. 格式化返回结果

    所有 OCR 逻辑由 PaddleOCR 库完成。
    """
    file_path = Path(request.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

    supported_formats = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"}
    if file_path.suffix.lower() not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式: {file_path.suffix}，支持: {supported_formats}"
        )

    try:
        # ============================================================
        # 直接调用 PaddleOCR API - 不做任何逻辑修改
        # ============================================================

        ocr = get_ocr()

        # PaddleOCR.ocr() 返回完整的识别结果
        # 格式: [[[box], (text, confidence)], ...]
        result = ocr.ocr(str(file_path), cls=True)

        # 提取文本
        # PaddleOCR 返回的结构：result[0] 是第一页（图片只有一页）
        # 每个元素是 [box, (text, confidence)]
        texts = []
        boxes = []
        confidences = []

        if result and result[0]:
            for line in result[0]:
                box = line[0]       # 文字框坐标
                text = line[1][0]   # 识别文本
                conf = line[1][1]   # 置信度

                texts.append(text)
                boxes.append(box)
                confidences.append(conf)

        # 合并为完整文本
        full_text = "\n".join(texts)

        # ============================================================

        return OCRResponse(
            success=True,
            text=full_text,
            metadata={
                "file_name": file_path.name,
                "file_size": file_path.stat().st_size,
                "line_count": len(texts),
                "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
                "source": "PaddleOCR",
                **(request.metadata or {})
            }
        )

    except ImportError as e:
        logger.error(f"PaddleOCR 导入失败: {e}")
        return OCRResponse(
            success=False,
            text="",
            metadata={},
            error=f"PaddleOCR 未正确安装: {e}"
        )
    except Exception as e:
        logger.error(f"OCR 识别失败: {e}")
        return OCRResponse(
            success=False,
            text="",
            metadata={},
            error=str(e)
        )


@app.post("/ocr/table")
async def ocr_table(request: OCRRequest):
    """
    表格 OCR 识别

    直接调用 PaddleOCR 的表格识别能力。
    """
    # TODO: 调用 PPStructure 表格识别
    # from paddleocr import PPStructure
    raise HTTPException(status_code=501, detail="表格识别功能开发中")


if __name__ == "__main__":
    port = int(os.environ.get("SERVICE_PORT", 8011))
    logger.info(f"启动图片OCR服务，端口: {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
