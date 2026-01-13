# Prompts Module (提示词模块)

## 简介
本模块集中管理所有的 System Prompts 和 Template。

## 提示词列表

### 1. Marketing Prompts (`marketing/prompts.py`)
*   `MARKETING_SYSTEM_PROMPT`: 营销老师的基础人设。
*   `MARKETING_RAG_PROMPT`: 结合知识库上下文的问答模板。
*   `GRADE_DOCUMENTS_PROMPT`: 文档相关性评估。
*   `HALLUCINATION_CHECK_PROMPT`: 幻觉检测。
*   `ANSWER_QUALITY_PROMPT`: 回答质量评估。
*   `REFLECTION_PROMPT`: 自我反思与规则学习。

## 管理原则
*   **集中化**: 避免将 Prompt 硬编码在业务逻辑中。
*   **版本控制**: Prompt 的变更应被视为代码变更。
