# Data Directory (数据目录)

## 简介
本目录用于存储系统的持久化数据。

## 目录结构

*   `chroma_db/`: ChromaDB 向量数据库文件 (RAG 索引)。
*   `uploads/`: 用户上传的原始文件存储目录。
*   `knowledge.db`: SQLite 数据库，存储知识库文档的元数据。
*   `user_preferences.db`: SQLite 数据库，存储用户偏好和长期记忆。

## 注意事项
*   本目录下的数据应定期备份。
*   `.gitignore` 已配置忽略部分大文件，但保留了数据库结构。
