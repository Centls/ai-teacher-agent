# Multimodal Service Client (多模态客户端)

## 简介
本模块提供了与 Docling Service 进行交互的 Python 客户端。它封装了 HTTP 请求细节，提供了同步 (`MultimodalSyncClient`) 和异步 (`MultimodalClient`) 两种调用方式。

## 核心组件

### 1. MultimodalSyncClient (`sync_client.py`)
*   **用途**: 用于同步上下文（如普通 Python 脚本或同步 API）。
*   **功能**: 
    *   `process_file(file_path)`: 上传并解析文件。
    *   `health_check()`: 检查 Docling 服务健康状态。
    *   自动重试机制 (Tenacity)。

### 2. MultimodalClient (`client.py`)
*   **用途**: 用于异步上下文（如 FastAPI `async def`）。
*   **功能**: 
    *   基于 `httpx.AsyncClient` 实现。
    *   支持高并发文件处理。

## 使用示例

### 同步调用
```python
from src.services.multimodal.sync_client import MultimodalSyncClient

client = MultimodalSyncClient()
result = client.process_file("path/to/document.pdf")

if result.success:
    print(result.text)
    print(result.metadata)
```

### 异步调用
```python
from src.services.multimodal.client import MultimodalClient

async def main():
    client = MultimodalClient()
    result = await client.process_file("path/to/image.png")
    print(result.text)

# 在 async 环境中运行
```

## 配置
客户端默认连接到 `http://localhost:3140`。可以通过环境变量覆盖：
*   `DOCLING_SERVICE_URL`: Docling 服务地址
