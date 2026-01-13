# Services Module (服务模块)

## 简介
本目录包含系统核心的后端服务。这些服务通常是无状态的或单例的，为上层的 Agents 提供通用能力支持。

## 服务列表

### 1. RAG Service (`rag/`)
*   **功能**: 检索增强生成服务。
*   **职责**: 管理向量数据库 (ChromaDB)、文档摄取、检索和重排序。

### 2. Multimodal Service (`multimodal/`)
*   **功能**: 多模态数据处理。
*   **职责**: 
    *   **Docling Service**: 解析 PDF, DOCX, 图片 (OCR), 音频 (ASR)。
    *   **Client**: 提供 Python 客户端供其他模块调用。

## 设计原则
*   **解耦**: 服务之间应尽量保持松耦合。
*   **接口化**: 通过清晰的 Python 类或 API 接口暴露能力。
