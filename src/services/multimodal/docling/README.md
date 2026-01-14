# Docling Multimodal Service (文档解析服务)

## 简介
Docling Service 是一个独立的多模态文档处理微服务，基于 `docling` 库构建。它负责将各种非结构化文件（文档、图片、音频）转换为统一的 Markdown 文本格式，供 RAG 系统使用。

## 功能特性
*   **全格式支持**:
    *   **文档**: PDF, DOCX, PPTX, XLSX, HTML, Markdown
    *   **图片**: JPG, PNG, BMP, TIFF (集成 **RapidOCR**，基于 PaddleOCR，中文识别效果更佳)
    *   **音频**: MP3, WAV, M4A, FLAC (集成 OpenAI Whisper)
*   **高性能**: 针对 PDF 表格和复杂布局进行了优化。
*   **跨平台兼容**: 特别优化了 Windows 环境下的 PDF 解析 (自动切换至 pypdfium2 后端)。
*   **独立部署**: 作为一个 FastAPI 服务运行，与主应用解耦，便于扩展和维护。

## 架构
采用 Client-Server 架构：
*   **Server (`server.py`)**: 运行在独立进程/容器中，处理繁重的解析任务 (OCR, ASR)。
*   **Client (`sync_client.py`)**: 主应用通过 HTTP 接口调用服务。

## API 接口
*   `POST /parse`: 上传文件并返回解析结果 (Markdown 文本 + 元数据)。
*   `GET /health`: 健康检查。

## 依赖
*   `docling`: 核心文档解析库
*   `rapidocr-onnxruntime`: OCR 推理加速 (中文支持)
*   `openai-whisper`: 语音转写模型
*   `fastapi` / `uvicorn`: Web 服务框架

## 启动方式
推荐使用项目根目录下的 `scripts/setup_services.py` 一键启动。
也可以手动独立启动：

### 1. 安装依赖
```bash
cd src/services/multimodal/docling
pip install -r requirements.txt
```
*注意：建议使用 Python 3.11+，并根据硬件情况安装 PyTorch (CUDA/CPU)。*

### 2. 启动服务
```bash
python server.py
```
默认端口: `8010`
