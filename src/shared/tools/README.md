# Shared Tools Library (共享工具库)

## 简介
本目录包含可供所有智能体复用的通用工具实现。

## 工具列表 (`lib/`)

### 1. Calculator (`calculator.py`)
*   **功能**: 基础数学计算。
*   **参数**: `expression` (数学表达式)。

### 2. Web Search (`web_search.py`)
*   **功能**: 简单的联网搜索封装。
*   **参数**: `query` (搜索关键词)。

### 3. DB Query (`db_query.py`)
*   **功能**: 数据库查询工具（受限只读）。
*   **参数**: `sql` (SQL查询语句)。

## 注册机制 (`registry.py`)
*   **ToolRegistry**: 提供工具注册和获取的统一接口。
*   **用法**:
    ```python
    from src.shared.tools.registry import registry
    
    tools = registry.get_tools(["calculator", "web_search"])
    ```
