# Source Code (源码目录)

## 简介
本目录 (`src/`) 包含 AI Teacher Nexus 的所有后端源代码。

## 模块概览

### 1. Agents (`agents/`)
*   包含具体的智能体实现（如 `marketing`, `supervisor`）。
*   每个智能体通常包含 `graph.py` (状态图), `nodes.py` (节点逻辑), `prompts.py` (提示词)。

### 2. Services (`services/`)
*   包含核心后端服务（如 `rag`, `multimodal`）。
*   提供通用的能力支持，供 Agents 调用。

### 3. Core (`core/`)
*   包含系统基础设施（配置、状态管理、工厂模式、审计日志）。
*   是整个系统的底层框架。

### 4. Shared (`shared/`)
*   包含跨模块复用的通用工具和组件。

### 5. Tools (`tools/`)
*   包含具体的 LangChain Tools 实现（如 `publish`, `refund`）。

### 6. API (`api/`)
*   (规划中) 存放 FastAPI 路由定义。目前主要路由在 `server.py`。

## 入口文件
*   `server.py`: FastAPI 应用入口，负责启动 HTTP 服务和 WebSocket/SSE 端点。
*   `server_error_patch.py`: 针对 Windows 环境下 `ProactorEventLoop` 的补丁，解决关闭服务时的 `RuntimeError`。
