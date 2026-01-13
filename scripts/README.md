# Utility Scripts (实用脚本)

## 简介
本目录包含用于系统初始化、测试和维护的辅助脚本。

## 脚本列表

### 1. `setup_services.py`
*   **功能**: 一键启动所有服务（后端 API + Docling 服务）。
*   **用法**: `python scripts/setup_services.py`

### 2. `init_knowledge_db.py`
*   **功能**: 初始化知识库数据库 (`data/knowledge.db`)。
*   **用法**: `python scripts/init_knowledge_db.py`

### 3. `rag_manager.py`
*   **功能**: 命令行工具，用于管理 RAG 知识库（上传、列出、搜索）。
*   **用法**: 
    *   上传: `python scripts/rag_manager.py upload <file_path>`
    *   搜索: `python scripts/rag_manager.py search "query"`

### 4. `test_transcribe.py`
*   **功能**: 测试 Docling 服务的音频转写功能。
*   **用法**: `python scripts/test_transcribe.py`
