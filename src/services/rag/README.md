# RAG Service (检索增强生成服务)

## 简介
RAG 服务层负责管理所有的知识库交互，包括文档摄取、向量化、存储和检索。它为上层的 Teacher Agents 提供统一的知识获取接口。

## 核心组件
1.  **ChromaKnowledgeProvider**: 基于 ChromaDB 的知识库实现。
    *   **Vector Store**: 存储文档的 Embedding 向量。
    *   **Metadata Store**: (SQLite) 存储文档的元数据（文件名、上传时间等）。
2.  **RAGPipeline**: 封装了检索的高级逻辑。
    *   **Hybrid Search**: (计划中) 结合向量检索和关键词检索。
    *   **Reranking**: (计划中) 对检索结果进行重排序。

## 数据流
1.  **Ingestion (摄取)**: 
    `File -> Text Splitter -> Embedding Model -> ChromaDB`
2.  **Retrieval (检索)**: 
    `Query -> Embedding Model -> Vector Search -> Rerank -> Documents`

## 目录结构
*   `chroma_service.py`: ChromaDB 的具体实现。
*   `pipeline.py`: RAG 流程控制。
*   `vector.py`: 向量化相关工具。

## 依赖
*   `chromadb`: 向量数据库
*   `langchain-chroma`: LangChain 适配器
*   `langchain-openai`: Embedding 模型接口
