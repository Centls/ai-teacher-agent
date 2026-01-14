# Data Directory (数据目录)

## 简介
本目录用于统一存储系统的所有持久化数据，包括数据库、向量库和用户上传的文件。

## 目录结构

### 数据库文件
*   `checkpoints.sqlite`: LangGraph 检查点数据库，保存对话状态和历史 (AsyncSqliteSaver)。
*   `knowledge.db`: 知识库元数据数据库 (SQLite)，存储文档的上传记录、解析状态和类型标签。
*   `threads.db`: 线程管理数据库 (如有使用)。
*   `user_preferences.db`: 用户偏好与长期记忆数据库 (AsyncSQLiteStore)。

### 存储目录
*   `chroma_db/`: ChromaDB 向量数据库目录 (RAG 索引)，存储知识库的向量数据。
*   `uploads/`: 用户上传的原始文件存储目录 (PDF, Word, 图片, 音频等)。

## 维护说明
*   **备份**: 建议定期备份整个 `data/` 目录。
*   **迁移**: 如果需要迁移部署，请确保完整复制本目录。
*   **清理**: `uploads/` 目录中的文件是知识库的原始凭证，请勿随意删除，除非确认不再需要重建索引。

