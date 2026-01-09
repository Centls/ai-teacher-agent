# Skill: 后端调试

当用户说 "调试后端"、"后端报错"、"服务器问题" 时激活此 Skill。

## 核心能力

1. **服务器启动问题诊断**
2. **API 接口调试**
3. **模型 API 错误排查**
4. **数据库连接问题**

## 关键文件

| 文件 | 用途 |
|------|------|
| `src/server.py` | FastAPI 主服务器 |
| `src/agents/marketing/graph.py` | LangGraph 工作流 |
| `src/agents/marketing/nodes.py` | 节点实现 |
| `.env` | 环境配置 |

## 调试流程

### Step 1: 检查服务器状态
```bash
curl -X GET "http://localhost:8001/health" -s
```

### Step 2: 查看日志标记
重要日志标记：
- `[RETRIEVE]` - 知识库检索
- `[GRADE]` - 文档评分
- `[WEB_SEARCH]` - Web 搜索
- `[ERROR]` - 错误信息

### Step 3: 错误分类

| 错误类型 | 标识 | 解决方案 |
|----------|------|----------|
| `llm_bad_request` | 400 错误 | 检查模型名称/账户余额 |
| `llm_auth_error` | 401/403 | 检查 API Key |
| `llm_rate_limit` | 429 | 等待或切换模型 |
| `llm_timeout` | 超时 | 检查网络连接 |
| `graph_error` | Graph 异常 | 检查 checkpoint 状态 |

### Step 4: 常用修复命令

```bash
# 重启服务器
taskkill /F /IM python.exe && .venv/Scripts/python.exe -m src.server

# 检查端口占用
netstat -ano | findstr :8001

# 测试 API
curl -X POST "http://localhost:8001/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"question": "测试", "thread_id": "test-1"}' -s
```

## 模型配置参考

```env
# 阿里云百炼可用模型
LLM_MODEL=qwen-turbo          # 默认模型
FAST_LLM=openai:qwen-flash    # 快速模型
SMART_LLM=openai:qwen-plus-latest  # 智能模型
STRATEGIC_LLM=openai:qwen-max # 高级模型
```

## 输出格式

诊断结果格式：
```
## 问题诊断

**错误类型**: [类型]
**根本原因**: [原因]
**影响范围**: [范围]

## 修复方案

1. [步骤1]
2. [步骤2]

## 验证命令
[命令]
```