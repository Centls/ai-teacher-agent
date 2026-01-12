# -*- coding: utf-8 -*-
"""
音频ASR服务 - 基于 FunASR

本服务直接复用 FunASR (https://github.com/modelscope/FunASR) 的全部能力。
仅编写最小必要的 FastAPI 服务层代码，不实现任何 ASR 逻辑。

FunASR 提供的核心能力（直接复用）：
    - 语音识别：Paraformer 模型，中文 CER 3%
    - 标点恢复：自动添加标点符号
    - 时间戳：字级别时间戳
    - 说话人分离：多人对话识别
    - 多语言：支持中英日韩等 31 种语言

依赖来源: https://github.com/modelscope/FunASR
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
# 外部依赖导入 - 直接复用 FunASR
# ============================================================
# FunASR 核心模块，提供完整的语音识别能力
# 不做任何封装或逻辑修改，直接调用原库 API
from funasr import AutoModel

# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="音频ASR服务",
    description="基于 FunASR 的语音转文字服务",
    version="1.0.0"
)

# 全局模型实例（避免重复加载）
_asr_model: Optional[AutoModel] = None
_punc_model: Optional[AutoModel] = None


def get_asr_model() -> AutoModel:
    """
    获取 FunASR 语音识别模型

    使用 FunASR 官方推荐的 Paraformer 模型，中文识别最佳。
    """
    global _asr_model
    if _asr_model is None:
        # ============================================================
        # 直接使用 FunASR 官方 API
        # 模型说明见: https://github.com/modelscope/FunASR
        # ============================================================
        _asr_model = AutoModel(
            model="paraformer-zh",  # Paraformer 中文模型
            vad_model="fsmn-vad",   # 语音活动检测
            punc_model="ct-punc",   # 标点恢复
            # 以下为可选配置
            # spk_model="cam++",    # 说话人分离（按需启用）
        )
    return _asr_model


class TranscribeRequest(BaseModel):
    """转写请求"""
    file_path: str
    metadata: Optional[Dict[str, Any]] = None
    # 可选参数
    language: Optional[str] = "zh"  # 语言：zh/en/ja/ko 等
    enable_timestamp: Optional[bool] = False  # 是否返回时间戳


class TranscribeResponse(BaseModel):
    """转写响应"""
    success: bool
    text: str
    metadata: Dict[str, Any]
    error: Optional[str] = None


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "asr"}


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(request: TranscribeRequest):
    """
    音频转写

    直接调用 FunASR 的 API 完成转写，本函数仅负责：
    1. 参数校验
    2. 调用 FunASR
    3. 格式化返回结果

    所有 ASR 逻辑由 FunASR 库完成。
    """
    file_path = Path(request.file_path)

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")

    supported_formats = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"}
    if file_path.suffix.lower() not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式: {file_path.suffix}，支持: {supported_formats}"
        )

    try:
        # ============================================================
        # 直接调用 FunASR API - 不做任何逻辑修改
        # ============================================================

        model = get_asr_model()

        # FunASR.generate() 返回完整的识别结果
        # 包含文本、时间戳、置信度等信息
        result = model.generate(
            input=str(file_path),
            batch_size_s=300,  # 批处理大小（秒）
            hotword="",        # 热词（可选）
        )

        # 提取文本
        # FunASR 返回的结构：[{"text": "...", "timestamp": [...]}]
        if result and len(result) > 0:
            full_text = result[0].get("text", "")
            timestamp = result[0].get("timestamp", [])
        else:
            full_text = ""
            timestamp = []

        # ============================================================

        # 构建元数据
        meta = {
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "source": "FunASR",
            "model": "paraformer-zh",
            **(request.metadata or {})
        }

        # 如果请求了时间戳，添加到元数据
        if request.enable_timestamp and timestamp:
            meta["timestamp"] = timestamp

        return TranscribeResponse(
            success=True,
            text=full_text,
            metadata=meta
        )

    except ImportError as e:
        logger.error(f"FunASR 导入失败: {e}")
        return TranscribeResponse(
            success=False,
            text="",
            metadata={},
            error=f"FunASR 未正确安装: {e}"
        )
    except Exception as e:
        logger.error(f"音频转写失败: {e}")
        return TranscribeResponse(
            success=False,
            text="",
            metadata={},
            error=str(e)
        )


@app.post("/transcribe/realtime")
async def transcribe_realtime(request: TranscribeRequest):
    """
    实时流式转写

    直接调用 FunASR 的流式识别能力。
    """
    # TODO: 调用 FunASR 流式识别
    raise HTTPException(status_code=501, detail="实时转写功能开发中")


if __name__ == "__main__":
    port = int(os.environ.get("SERVICE_PORT", 8012))
    logger.info(f"启动音频ASR服务，端口: {port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
