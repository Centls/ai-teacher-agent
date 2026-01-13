# Core Infrastructure (核心基础设施)

## 简介
Core 模块提供了整个 AI Teacher Nexus 系统的底层支撑，包括图工厂、配置管理、状态管理和审计日志。

## 关键组件

### 1. Factory (`factory.py`)
*   **GraphFactory**: 负责动态编译 LangGraph 图。它将节点的定义组装成可执行的工作流。
*   **Node Wrapper**: 提供统一的错误处理和日志记录装饰器。

### 2. State Management (`state_mgr.py` & `store`)
*   **NexusState**: 定义了 LangGraph 的全局状态结构 (Messages, User Context, Tasks)。
*   **AsyncSqliteSaver**: (LangGraph Built-in) 用于 Checkpoint 持久化 (`checkpoints.sqlite`)。
*   **AsyncSQLiteStore**: 用于长期记忆存储 (`data/user_preferences.db`)。

### 3. Config (`config/settings.py`)
*   **Single Source of Truth**: `config/settings.py` 是系统配置的唯一入口。
*   **Environment Variables**: 自动加载 `.env` 文件，并提供类型安全的配置访问（如 `settings.DEFAULT_MODEL`, `settings.OPENAI_API_KEY`）。
*   **Path Management**: 统一管理项目路径（`BASE_DIR`, `LOGS_DIR`, `DATA_DIR`）。

### 4. Audit (`audit.py`)
*   记录系统运行时的关键事件、Token 消耗和延迟。
*   日志存储在 `logs/audit.jsonl`。

### 5. Lifecycle (`lifecycle.py`)
*   **SessionManager**: 管理用户会话的生命周期（创建、检索、关闭）。
*   维护全局会话状态 `_sessions`。

### 6. Memory (`memory.py`)
*   **MemoryManager**: 管理不同层级的记忆（Session, Global, Tool）。
*   提供上下文获取和更新接口。

### 7. Prompt (`prompt_mgr.py`)
*   **PromptManager**: 负责加载和缓存 YAML 格式的 Prompt 模板。
*   支持从 `config/prompts/` 目录动态加载。

### 8. LLM Provider (`llm_provider.py`)
*   **LLMProvider**: 统一的 LLM 接口封装。
*   支持 `RealLLMProvider` (调用真实 API) 和 `MockLLMProvider` (用于测试)。

### 9. PRD Manager (`prd_mgr.py`)
*   **PRDManager**: 管理产品需求文档 (PRD) 约束。
*   用于在生成过程中检查内容是否符合预定义的业务规则。

### 10. HITL (`hitl.py`)
*   **HumanInTheLoop**: 提供人机协同的辅助函数。
*   管理审批状态和中断逻辑。

## 设计原则
*   **Singleton**: 核心管理器通常作为单例运行。
*   **Dependency Injection**: 尽量通过参数注入依赖，便于测试。
