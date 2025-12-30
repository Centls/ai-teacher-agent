# 历史对话记录修复报告

## 🐛 问题描述
切换会话（Thread）后，无法查看历史对话内容，前端始终显示空白。

## 🔍 根本原因

### 1. Messages 格式错误
**位置**: `src/server.py` (第 107, 167 行)

**错误代码**:
```python
# ❌ 错误：使用元组格式
inputs = {"messages": [("user", question)]}
```

**问题**:
- `MarketingState` 定义中 `messages` 类型是 `List[BaseMessage]`
- 传入元组 `("user", question)` 会导致类型不匹配
- LangGraph Checkpointer 无法正确序列化/反序列化 messages
- 导致历史记录无法正确保存到 SQLite

**修复**:
```python
# ✅ 正确：使用 HumanMessage 对象
from langchain_core.messages import HumanMessage
inputs = {"messages": [HumanMessage(content=question)]}
```

### 2. History 接口返回格式不匹配
**位置**: `src/server.py` (第 347-381 行)

**错误代码**:
```python
# ❌ 错误格式
formatted_messages.append({
    "id": str(uuid.uuid4()),
    "role": role,  # "user" or "assistant"
    "content": msg.content,
    "createdAt": datetime.now().isoformat()
})
```

**问题**:
- 前端期望的是 `MessageResponse` 格式
- 实际返回的是简化的对象格式
- 缺少 `type` 和 `data` 嵌套结构

**修复**:
```python
# ✅ 正确格式 (MessageResponse)
formatted_messages.append({
    "type": "human",  # or "ai", "tool"
    "data": {
        "id": msg.id,
        "content": msg.content,
        # AI messages 需要额外字段
        "tool_calls": getattr(msg, 'tool_calls', []),
        "additional_kwargs": getattr(msg, 'additional_kwargs', {}),
        "response_metadata": getattr(msg, 'response_metadata', {})
    }
})
```

## ✅ 修复内容

### 1. 修复 `/chat/stream` 接口 (Marketing)
**文件**: [src/server.py](src/server.py#L106-L111)

```python
# 初始输入 - 使用 HumanMessage 对象而不是元组
from langchain_core.messages import HumanMessage
inputs = {
    "question": question,
    "messages": [HumanMessage(content=question)]
}
```

### 2. 修复 `/chat/supervisor` 接口
**文件**: [src/server.py](src/server.py#L168-L170)

```python
# 使用 HumanMessage 对象
from langchain_core.messages import HumanMessage
inputs = {"messages": [HumanMessage(content=question)]}
```

### 3. 修复 `/history/{thread_id}` 接口
**文件**: [src/server.py](src/server.py#L354-L416)

**核心改进**:
- 返回标准 `MessageResponse` 格式
- 支持 `human`, `ai`, `tool` 三种消息类型
- 正确映射 LangChain 消息属性到前端期望字段

```python
# Map LangChain message types to frontend types
if msg_type == "human":
    formatted_messages.append({
        "type": "human",
        "data": {
            "id": msg.id if hasattr(msg, 'id') else str(uuid.uuid4()),
            "content": msg.content
        }
    })
elif msg_type == "ai":
    formatted_messages.append({
        "type": "ai",
        "data": {
            "id": msg.id if hasattr(msg, 'id') else str(uuid.uuid4()),
            "content": msg.content,
            "tool_calls": getattr(msg, 'tool_calls', []),
            "additional_kwargs": getattr(msg, 'additional_kwargs', {}),
            "response_metadata": getattr(msg, 'response_metadata', {})
        }
    })
```

## 🎯 影响范围

| 接口 | 修复前 | 修复后 |
|-----|-------|--------|
| **POST /chat/stream** | ❌ Messages 格式错误，无法保存 | ✅ 正确保存到 checkpoint |
| **POST /chat/supervisor** | ❌ Messages 格式错误，无法保存 | ✅ 正确保存到 checkpoint |
| **GET /history/{thread_id}** | ❌ 返回格式不匹配 | ✅ 返回 MessageResponse 格式 |
| **前端历史记录** | ❌ 无法加载 | ✅ 正常显示 |

## 🧪 测试验证

### 测试步骤
1. 启动后端服务器
2. 发送消息创建对话
3. 切换到其他 Thread
4. 再次切换回原 Thread
5. 检查历史记录是否正确显示

### 预期结果
- ✅ 历史消息按顺序显示
- ✅ 用户消息和 AI 回复正确区分
- ✅ 消息内容完整显示
- ✅ Tool 调用（如有）正确显示

## 📊 数据流

```
前端 Thread 切换
    ↓
调用 /api/agent/history/{threadId}
    ↓
Next.js API 路由转发到后端
    ↓
GET /history/{thread_id}
    ↓
从 AsyncSqliteSaver 读取 checkpoint
    ↓
获取 state.values.messages (List[BaseMessage])
    ↓
转换为 MessageResponse[] 格式
    ↓
返回前端
    ↓
前端渲染历史消息
```

## 🔧 关键技术点

### 1. LangChain Message Types
```python
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# 用户消息
HumanMessage(content="问题内容")

# AI 回复
AIMessage(content="回答内容", tool_calls=[...])

# Tool 调用结果
ToolMessage(content="结果", tool_call_id="...")
```

### 2. LangGraph State 持久化
- 使用 `AsyncSqliteSaver` 作为 Checkpointer
- State 自动序列化到 `checkpoints.sqlite`
- 通过 `thread_id` 隔离不同对话

### 3. 前端 MessageResponse 格式
```typescript
interface MessageResponse {
  type: "human" | "ai" | "tool" | "error";
  data: BasicMessageData | AIMessageData | ToolMessageData;
}
```

## ⚠️ 注意事项

1. **旧数据兼容性**: 修复前创建的对话可能仍然无法正确加载（messages 格式错误）
2. **建议清理**: 删除 `checkpoints.sqlite` 后重新测试
3. **类型安全**: 始终使用 `BaseMessage` 子类，避免使用元组

## 🚀 后续优化建议

1. **数据迁移**: 编写脚本修复旧 checkpoint 中的 messages 格式
2. **错误处理**: 增强 /history 接口的容错能力
3. **性能优化**: 对大量历史消息进行分页加载
4. **单元测试**: 添加 messages 序列化/反序列化测试

---

**修复日期**: 2025-12-30
**影响版本**: ≥ 2.0.0
