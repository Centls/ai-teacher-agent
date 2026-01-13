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

### 3. Config (`config_mgr.py` & `config.py`)
*   负责加载和管理系统配置及 Prompt 模板。
*   支持从 `.env` 和 `config/` 目录加载配置。

### 4. Audit (`audit.py`)
*   记录系统运行时的关键事件、Token 消耗和延迟。
*   日志存储在 `logs/audit.jsonl`。

## 设计原则
*   **Singleton**: 核心管理器通常作为单例运行。
*   **Dependency Injection**: 尽量通过参数注入依赖，便于测试。
