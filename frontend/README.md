# AI Teacher Nexus Frontend

> **基于 Next.js 15 + Tailwind CSS 的 AI 营销老师智能体前端界面。**

## 简介
本项目是 AI Teacher Nexus 的前端部分，提供了一个现代化的聊天界面，用于与 AI 营销老师进行交互。
它支持流式响应 (SSE)、Markdown 渲染、知识库管理、文件上传和 Human-in-the-Loop (HITL) 审批流程。

## 核心特性

### 1. 现代化聊天界面
*   **流式响应**: 实时显示 AI 生成的内容，打字机效果。
*   **Markdown 支持**: 完美渲染代码块、表格、列表等格式。
*   **多模态附件**: 对话中支持发送临时文件（文档/图片/音频），并能在历史记录中完整回显。
*   **状态指示**: 清晰展示 AI 当前的思考状态（检索中、生成中、联网搜索中）。

### 2. 知识库管理 (Knowledge Base)
*   **多模态上传**: 支持上传文档 (PDF, DOCX, MD, HTML)、图片 (JPG, PNG - OCR) 和音频 (MP3, WAV - ASR)。
*   **文档列表**: 查看和管理已上传的知识库文档。
*   **标签管理**: (开发中) 支持为文档添加标签，实现精准检索。

### 3. 人机协同 (Human-in-the-Loop)
*   **审批流**: 当 AI 生成关键决策或内容时，会暂停并请求用户审批。
*   **反馈机制**: 用户可以拒绝并提供修改建议，AI 将根据反馈重新生成。

### 4. 联网搜索集成
*   **智能触发**: 支持手动开启或自动触发联网搜索。
*   **来源展示**: 在回答中清晰标注信息来源（知识库 vs 互联网）。

## 技术栈
*   **Framework**: Next.js 15 (App Router)
*   **Language**: TypeScript
*   **Styling**: Tailwind CSS + Shadcn UI
*   **Icons**: Lucide React
*   **State Management**: React Hooks
*   **HTTP Client**: Fetch API (Native)

## 快速开始

### 1. 安装依赖
```bash
pnpm install
```

### 2. 配置环境变量
复制 `.env.example` 到 `.env.local` 并配置后端地址：
```env
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### 3. 启动开发服务器
```bash
pnpm dev
```
访问 [http://localhost:3000](http://localhost:3000) 开始使用。

## 目录结构
```
src/
├── app/                 # Next.js App Router 页面
├── components/          # React 组件 (Chat, KnowledgeBase, etc.)
├── hooks/               # 自定义 Hooks (useChat, useStream)
├── lib/                 # 工具函数
└── types/               # TypeScript 类型定义
```
