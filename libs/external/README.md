# External Libraries (外部依赖库)

## 简介
本目录存放通过 **Strong Dependency Reuse (强依赖复用)** 策略引入的外部开源项目。我们直接克隆或子模块化这些项目，以复用其成熟的逻辑，而不是重新造轮子。

## 包含项目

### 1. `fullstack-nextjs`
*   **来源**: [IBJunior/fullstack-langgraph-nextjs-agent](https://github.com/IBJunior/fullstack-langgraph-nextjs-agent)
*   **用途**: 提供完整的前端 UI，支持流式对话、工具调用展示和会话管理。
*   **集成方式**: 作为 `frontend` 目录的基础。

### 2. `Agentic-RAG-Ollama`
*   **来源**: [laxmimerit/Agentic-RAG-with-LangGraph-and-Ollama](https://github.com/laxmimerit/Agentic-RAG-with-LangGraph-and-Ollama)
*   **用途**: 提供 CRAG (Corrective RAG) 的核心工作流逻辑和节点实现。
*   **集成方式**: 参考其 `nodes.py` 和 `graph.py` 实现我们的 Marketing Agent。

## 管理规则
*   **不要直接修改**: 尽量避免直接修改 `external` 目录下的代码，以便将来可以拉取上游更新。
*   **适配层**: 在 `src/` 目录下编写适配代码（Adapter）来调用这些库。
