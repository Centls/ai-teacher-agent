# Supervisor 2.0 (Nexus Supervisor)

## 简介
Supervisor 2.0 是基于 `langgraph-supervisor` 实现的多智能体调度系统。它作为“总控大脑”，负责接收用户请求，并根据意图将其路由给最合适的子智能体（如营销老师、通用助手等）。

## 架构 (白盒复用)
本项目复用了 `agent-service-toolkit` 中的 Supervisor 模式：
*   **核心库**: `langgraph-supervisor`
*   **实现文件**: `src/agents/supervisor/graph.py`
*   **调度方式**: LLM 驱动的路由 (Router)，支持多轮对话和状态保持。

## 包含的智能体
1.  **MarketingTeacher**: 专业的营销文案生成老师 (基于 `src/agents/marketing`).
2.  **GeneralAssistant**: 通用聊天助手 (处理打招呼、闲聊等).

## 使用方式
### API 端点
`POST /chat/supervisor`

### 请求示例
```json
{
  "question": "如何优化 Facebook 广告投放？",
  "thread_id": "unique-thread-id"
}
```

### 响应
流式 SSE 响应，包含：
*   `token`: LLM 生成的内容
*   `status`: 当前活跃的节点 (e.g., `MarketingTeacher`, `supervisor`)

## 配置
确保 `.env` 中配置了正确的 LLM API Key (推荐 DeepSeek):
```env
DEEPSEEK_API_KEY=sk-...
LLM_MODEL=deepseek-chat
```
