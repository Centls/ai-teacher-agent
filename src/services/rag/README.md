# RAG Service (检索增强生成服务)

## 简介
RAG 服务层负责管理所有的知识库交互，包括文档摄取、向量化、存储和检索。它为上层的 Teacher Agents 提供统一的知识获取接口。

## 核心组件
1.  **MultimodalRAGPipeline**: 核心流水线，继承自 `RAGPipeline`，增加了多模态处理能力。
    *   **Vector Store**: 使用 `ChromaDB` 存储文档向量。
    *   **Embedding**: 使用 `OpenAIEmbeddings` (兼容 DeepSeek/Aliyun)。
    *   **Docling Integration**: 集成 Docling 服务处理 PDF、DOCX、图片和音频。
    *   **Hybrid Search**: 结合向量检索 (Vector Search) 和关键词检索 (BM25)。
    *   **Reranking**: 使用 `BM25Plus` 对检索结果进行重排序。

2.  **Metadata Store**: 使用 `SQLite` (`data/knowledge.db`) 存储文档元数据（文件名、上传时间、标签等）。

## 多模态能力 (Multimodal)
RAG 服务现在支持多种非结构化数据格式，通过 `src/services/multimodal/docling` 服务进行统一解析：
*   **文档**: PDF, DOCX, PPTX, XLSX, HTML, Markdown (DocLayNet 布局分析 + TableFormer 表格识别)
*   **图片**: JPG, PNG, BMP (集成 **RapidOCR**，基于 PaddleOCR，中文识别效果更佳)
*   **音频**: MP3, WAV, M4A, FLAC (集成 OpenAI **Whisper** 语音转写)

## 数据流
1.  **Ingestion (摄取)**: 
    `File -> Docling Service (Parse/OCR/ASR) -> Text Splitter -> Embedding Model -> ChromaDB`
2.  **Retrieval (检索)**: 
    `Query -> Embedding Model -> Vector Search -> BM25 Rerank -> Top-K Documents`
3.  **Deletion (删除)**:
    `Doc ID -> Fetch Chroma IDs -> Delete from Chroma -> Delete from Disk -> Delete from SQLite`

## 目录结构
*   `pipeline.py`: RAG 基础流水线。
*   `multimodal_pipeline.py`: 多模态 RAG 流水线 (Docling 集成)。
*   `retriever.py`: (可选) 辅助检索工具。

## 依赖
*   `chromadb`: 向量数据库
*   `langchain-chroma`: LangChain 适配器
*   `langchain-openai`: Embedding 模型接口
*   `rank_bm25`: 重排序算法
*   `docling`: 文档解析服务 (独立部署)
