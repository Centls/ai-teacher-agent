# Agent Tools (智能体工具)

## 简介
本目录包含供智能体调用的具体工具实现。这些工具通常被封装为 LangChain Tools，供 Agent 在执行过程中调用以完成特定任务。

## 工具列表

### 1. Publish Tool (`publish.py`)
*   **功能**: 发布营销内容到指定平台。
*   **参数**: `platform` (平台), `content` (内容)。

### 2. Refund Tool (`refund.py`)
*   **功能**: 处理客户退款请求。
*   **参数**: `user_id` (用户ID), `amount` (金额), `reason` (退款原因)。

## 使用方式
这些工具通常在 Agent 的 `nodes.py` 或 `graph.py` 中被绑定到 LLM。
