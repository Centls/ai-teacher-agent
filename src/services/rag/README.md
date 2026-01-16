# RAG Service (检索增强生成服务)

## 简介
RAG 服务层负责管理所有的知识库交互，包括文档摄取、向量化、存储和检索。它为上层的 Teacher Agents 提供统一的知识获取接口。

## 核心组件
1.  **MultimodalRAGPipeline**: 核心流水线，继承自 `RAGPipeline`，增加了多模态处理能力。
    *   **Vector Store**: 使用 `ChromaDB` 存储文档向量（或子块向量）。
    *   **Parent-Child Index**: (新) 使用 `ParentDocumentRetriever`。
        *   **Child Chunks**: 小块 (400 chars) 存入向量库，用于精确检索。
        *   **Parent Chunks**: 大块 (2000 chars) 存入 `LocalFileStore`，用于 LLM 上下文生成。
    *   **Embedding**: 使用 `OpenAIEmbeddings` (兼容 DeepSeek/Aliyun) 或本地 HF 模型。
    *   **Hybrid Search**:
        *   **Dense**: 向量检索 (Top-N)
        *   **Sparse**: BM25 关键词检索 (Top-N)
    *   **RRF Fusion**: 使用倒数排名融合 (Reciprocal Rank Fusion) 合并双路召回结果。
    *   **Reranking**: 使用 `CrossEncoder` (BGE-Reranker-v2-m3) 对融合结果进行语义精排。

2.  **Metadata Store**: 使用 `SQLite` (`data/knowledge.db`) 存储文档元数据（文件名、上传时间、标签等）。

## 多模态能力 (Multimodal)
RAG 服务现在支持多种非结构化数据格式，通过 `src/services/multimodal/docling` 服务进行统一解析：
*   **文档**: PDF, DOCX, PPTX, XLSX, HTML, Markdown (DocLayNet 布局分析 + TableFormer 表格识别)
*   **图片**: JPG, PNG, BMP (集成 **RapidOCR**，基于 PaddleOCR，中文识别效果更佳)
*   **音频**: MP3, WAV, M4A, FLAC (集成 OpenAI **Whisper** 语音转写)

## 数据流
1.  **Ingestion (摄取)**:
    *   **传统模式**: `File -> Docling -> Splitter -> Embedding -> ChromaDB`
    *   **父子索引模式**: `File -> Docling -> Parent Splitter (2k) -> Child Splitter (400) -> Embedding -> ChromaDB (Child) + FileStore (Parent)`

2.  **Retrieval (检索)**:
    `Query -> (Dense Search + BM25 Search) -> RRF Fusion -> CrossEncoder Rerank -> Top-K Parent Documents`

3.  **Deletion (删除)**:
    `Doc ID -> Fetch Chroma IDs -> Delete from Chroma -> Delete from Disk -> Delete from SQLite`

## 目录结构
*   `pipeline.py`: RAG 基础流水线 (实现父子索引、RRF、重排序的核心逻辑)。
*   `multimodal_pipeline.py`: 多模态 RAG 流水线 (继承 Pipeline，集成 Docling)。
*   `retriever.py`: (可选) 辅助检索工具。

## 依赖
*   `chromadb`: 向量数据库
*   `langchain-chroma`: LangChain 适配器
*   `langchain-classic`: **Parent-Child Index** 核心实现
*   `sentence-transformers`: **CrossEncoder** 核心实现
*   `rank_bm25`: **BM25** 算法实现
*   `docling`: 文档解析服务 (独立部署)
