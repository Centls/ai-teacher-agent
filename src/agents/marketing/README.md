# Marketing Teacher Agent (营销老师)

## 简介
营销老师是 AI Teacher Nexus 中的核心智能体之一，专门负责生成高质量的营销策划、文案和品牌策略建议。
它具备**CRAG (Corrective RAG)**、**Self-RAG** 和 **Web Search** 能力，能够智能地利用知识库和互联网信息。

## 核心架构
采用了 **Agentic RAG** 模式，结合 **HITL (Human-in-the-Loop)** 人机协同机制。

### 工作流 (Workflow)
1.  **Retrieve (检索)**:
    *   优先检索内部知识库。
    *   支持前端开关强制开启联网搜索。
    *   智能意图检测（如"最新新闻"自动触发联网）。
    *   **闲聊检测**：识别到闲聊意图时跳过 RAG 流程，直接生成回答。
2.  **Grade (评估)**: 评估检索到的文档相关性。
    *   **Yes**: 相关 -> 进入生成。
    *   **Partial**: 部分相关 -> 触发 **Web Search (Hybrid Mode)** 补充信息。
    *   **No**: 不相关 -> 触发 **Web Search (Fallback Mode)**。
3.  **Web Search (联网搜索)**:
    *   调用 DuckDuckGo/Tavily API 获取实时信息。
    *   支持与知识库内容合并 (Hybrid)。
4.  **Generate (生成)**: 基于综合信息生成回答。
5.  **Check Hallucination (幻觉检测)**: 检查生成的回答是否基于事实。
    *   有幻觉 -> 自动重试。
    *   无幻觉 -> 进入人工审核。
6.  **Human Review (人工审核)**: **[中断点]**
    *   展示数据来源（知识库/Web/混合）。
    *   用户批准 -> 返回结果；拒绝 -> 重写。

## 关键文件
*   `graph.py`: 定义 LangGraph 状态图，集成 `web_search` 节点。
*   `nodes.py`: 实现各个节点的具体逻辑（检索、评估、生成、联网搜索）。
*   `prompts.py`: 存储营销专用的 System Prompts。
*   `llm.py`: 配置 DeepSeek LLM 实例 (通过 `config/settings.py` 统一管理)。

## 依赖
*   `langgraph`: 编排引擎
*   `langchain-community`: Web Search Tools
*   `duckduckgo-search` / `ddgs`: 联网搜索支持
*   `src.services.rag`: 内部多模态知识库服务 (Multimodal RAG)
