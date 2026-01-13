# API Module

## 简介
本模块用于存放 FastAPI 的路由定义 (Routes) 和 API 相关逻辑。

## 目录结构
*   `routes/`: 存放具体的路由处理函数 (Router)。

## 当前状态
目前主要的 API 路由逻辑直接定义在 `src/server.py` 中。随着项目扩展，建议将路由拆分到本模块的 `routes/` 目录下，以保持代码整洁。
