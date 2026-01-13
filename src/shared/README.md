# Shared Utilities (共享工具库)

## 简介
本模块包含跨 Agent 和 Service 复用的通用工具和组件。

## 目录结构

### 1. Tools (`shared/tools`)
*   `registry.py`: 工具注册表，用于管理和分发工具。
*   `lib/`: 通用工具库实现。

## 设计目的
为了避免代码重复，将通用的逻辑（如工具注册、基础类定义）提取到 Shared 模块中，供不同的 Agent 复用。
