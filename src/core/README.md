# Core Infrastructure (核心基础设施)

## 简介
Core 模块提供了整个 AI Teacher Nexus 系统的底层支撑，包括生命周期管理、工厂模式、配置管理和审计日志。

## 关键组件

### 1. Factory (`factory.py`)
*   **GraphFactory**: 负责动态编译 LangGraph 图。它将节点的定义组装成可执行的工作流。
*   **Node Wrapper**: 提供统一的错误处理和日志记录装饰器。

### 2. Lifecycle (`lifecycle.py`)
*   **LifecycleManager**: 管理用户会话 (Session) 的生命周期。
*   **State Management**: 处理状态的初始化、更新和持久化。

### 3. Config (`config_mgr.py`)
*   负责加载和管理系统配置及 Prompt 模板。
*   支持热加载配置。

### 4. Audit (`audit.py`)
*   记录系统运行时的关键事件、Token 消耗和延迟。
*   为后续的分析和优化提供数据支持。

## 设计原则
*   **Singleton**: 核心管理器通常作为单例运行。
*   **Dependency Injection**: 尽量通过参数注入依赖，便于测试。
