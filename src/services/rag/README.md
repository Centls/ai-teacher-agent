# RAG Service (检索增强生成服务)

## 简介
RAG 服务层负责管理所有的知识库交互，包括文档摄取、向量化、存储和检索。它为上层的 Teacher Agents 提供统一的知识获取接口。

## 核心组件
1.  **RAGPipeline**: 核心流水线，封装了所有 RAG 逻辑。
    *   **Vector Store**: 使用 `ChromaDB` 存储文档向量。
    *   **Embedding**: 使用 `OpenAIEmbeddings` (兼容 DeepSeek/Aliyun)。
    *   **Hybrid Search**: 结合向量检索 (Vector Search) 和关键词检索 (BM25)。
    *   **Reranking**: 使用 `BM25Plus` 对检索结果进行重排序。

2.  **Metadata Store**: 使用 `SQLite` (`data/knowledge.db`) 存储文档元数据（文件名、上传时间、标签等）。

## 数据流
1.  **Ingestion (摄取)**: 
    `File -> Text Splitter (Markdown/Recursive) -> Embedding Model -> ChromaDB`
2.  **Retrieval (检索)**: 
    `Query -> Embedding Model -> Vector Search -> BM25 Rerank -> Top-K Documents`
3.  **Deletion (删除)**:
    `Doc ID -> Fetch Chroma IDs -> Delete from Chroma -> Delete from Disk -> Delete from SQLite`

## 目录结构
*   `pipeline.py`: RAG 核心实现 (Standalone)。
*   `retriever.py`: (可选) 辅助检索工具。

## 依赖
*   `chromadb`: 向量数据库
*   `langchain-chroma`: LangChain 适配器
*   `langchain-openai`: Embedding 模型接口
*   `rank_bm25`: 重排序算法
