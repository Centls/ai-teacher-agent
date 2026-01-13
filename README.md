# AI Teacher Nexus (AI 营销老师智能体)

## 简介
AI Teacher Nexus 是一个基于 **FastAPI + LangGraph + Next.js** 的生产级 AI Agent 应用。
核心功能是提供一位具备**长短期记忆**、**RAG 知识增强**、**联网搜索能力**和**自我反思机制**的 AI 营销老师。

## 核心特性
*   **Agentic Workflow**: 基于 LangGraph 的 CRAG (Corrective RAG) + Self-RAG 架构。
*   **Multimodal RAG**: 支持 PDF, DOCX, 图片 (OCR), 音频 (ASR) 等多模态数据解析与检索 (Powered by Docling)。
*   **Knowledge Base**: 支持文件上传、混合检索 (Vector + Keyword) 和持久化存储。
*   **Web Search**: 智能联网搜索 (DuckDuckGo/Tavily)，自动补充知识库缺失的信息。
*   **Human-in-the-Loop**: 关键步骤支持人工介入审核。
*   **Premium UI**: 基于 Next.js 15 + Tailwind CSS 的现代化聊天界面。

## 快速开始

### 1. 启动服务 (Startup)

#### 方式 A: 一键启动 (推荐)
使用辅助脚本同时启动后端 API 和文档解析服务：
```bash
python scripts/setup_services.py
```

#### 方式 B: 分步启动
1. **启动文档解析服务 (Docling Service)**
   ```bash
   python src/services/multimodal/docling/server.py
   ```
   *端口: 3140*

2. **启动后端 API (Backend)**
   ```bash
   python -m src.server
   ```
   *端口: 8001*

### 2. 前端启动 (Frontend)
```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```
*访问地址: http://localhost:3000*

## 目录结构

- `src/agents`: 智能体逻辑 (Marketing Teacher, Supervisor)
- `src/services/rag`: 知识库服务 (Multimodal RAG Pipeline)
- `src/services/multimodal`: 多模态解析服务 (Docling)
- `src/server.py`: 后端 API 入口 (FastAPI)
- `frontend`: Next.js 前端项目
- `data`: 数据存储 (SQLite, Uploads)
- `config`: 配置文件 (Settings, Prompts)

