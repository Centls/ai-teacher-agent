# Skill: 前端开发

当用户说 "前端问题"、"UI 修改"、"组件开发"、"样式调整" 时激活此 Skill。

## 核心能力

1. **React/Next.js 组件开发**
2. **TypeScript 类型问题修复**
3. **Tailwind CSS 样式调整**
4. **SSE 流式传输调试**

## 项目技术栈

- **框架**: Next.js 14 (App Router)
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **状态**: React Hooks
- **API**: SSE (Server-Sent Events)

## 关键文件

| 文件 | 用途 |
|------|------|
| `frontend/src/app/page.tsx` | 主页面 |
| `frontend/src/components/Thread.tsx` | 对话线程组件 |
| `frontend/src/components/MessageInput.tsx` | 消息输入组件 |
| `frontend/src/hooks/useChatThread.ts` | 聊天状态管理 |
| `frontend/src/services/chatService.ts` | API 调用服务 |
| `frontend/src/app/api/agent/stream/route.ts` | SSE 路由 |

## 开发流程

### Step 1: 启动开发服务器
```bash
cd frontend && npm run dev
```

### Step 2: 类型检查
```bash
cd frontend && npm run typecheck
```

### Step 3: Lint 检查
```bash
cd frontend && npm run lint
```

## 常见问题

### 1. SSE 流式传输问题

检查点：
- `route.ts` 中的 `TextEncoder` 是否正确使用
- 后端是否返回 `text/event-stream` 类型
- 前端 `EventSource` 是否正确连接

### 2. TypeScript 类型错误

```typescript
// 消息类型定义
interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  metadata?: MessageMetadata;
}
```

### 3. 样式不生效

检查：
- Tailwind 类名是否正确
- `tailwind.config.js` 内容路径配置
- 组件是否正确导入

## 调试技巧

### 控制台日志
```typescript
console.log("[SSE] 接收数据:", data);
console.log("[STATE] 当前状态:", state);
```

### 网络请求检查
1. 打开浏览器开发者工具 (F12)
2. 切换到 Network 标签
3. 筛选 XHR/Fetch 请求
4. 检查 EventStream 类型请求

## 输出格式

修复报告格式：
```
## 问题分析

**文件**: [文件路径]
**行号**: [行号]
**问题**: [问题描述]

## 修复方案

[代码修改]

## 验证方式
[如何验证修复成功]
```