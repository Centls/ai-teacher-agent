# Marketing Teacher Agent (营销老师)

## 简介
营销老师是 AI Teacher Nexus 中的核心智能体之一，专门负责生成高质量的营销策划、文案和品牌策略建议。

## 核心架构
采用了 **CRAG (Corrective RAG)** 模式，结合 **HITL (Human-in-the-Loop)** 人机协同机制。

### 工作流 (Workflow)
1.  **Retrieve (检索)**: 从知识库中检索与用户问题相关的文档。
2.  **Grade (评估)**: 评估检索到的文档是否与问题相关。
    *   如果相关 -> 进入生成阶段。
    *   如果不相关 -> 结束或尝试网络搜索（目前逻辑是结束）。
3.  **Generate (生成)**: 基于相关文档和营销 Prompt 生成回答。
4.  **Check Hallucination (幻觉检测)**: 检查生成的回答是否基于事实（文档）。
    *   有幻觉 -> 自动重试（最多 2 次）。
    *   无幻觉 -> 进入人工审核。
5.  **Human Review (人工审核)**: **[中断点]** 等待用户在前端确认。
    *   批准 -> 返回最终结果。
    *   拒绝 -> 结束或要求重写。

## 关键文件
*   `graph.py`: 定义 LangGraph 状态图和 HITL 中断逻辑。
*   `nodes.py`: 实现各个节点的具体逻辑（检索、评估、生成）。
*   `prompts.py`: 存储营销专用的 System Prompts。
*   `llm.py`: 配置 DeepSeek LLM 实例。

## 依赖
*   `langgraph`: 编排引擎
*   `langchain-openai`: 调用 DeepSeek API
*   `src.services.rag`: 提供检索能力
