# Skill: 部署运维

当用户说 "部署"、"启动服务"、"环境配置"、"生产环境" 时激活此 Skill。

## 核心能力

1. **开发环境配置**
2. **服务启动与管理**
3. **端口与进程管理**
4. **环境变量配置**

## 项目结构

```
ai-teacher-nexus/
├── .venv/                    # Python 虚拟环境
├── frontend/                 # Next.js 前端
├── src/                      # Python 后端
│   ├── server.py            # FastAPI 服务器
│   └── agents/              # LangGraph Agents
├── .env                      # 环境配置
├── checkpoints.sqlite        # LangGraph 状态存储
├── threads.db               # 会话存储
└── chroma_db/               # 向量数据库
```

## 服务启动

### 后端服务 (端口 8001)

```bash
# 激活虚拟环境并启动
.venv/Scripts/python.exe -m src.server
```

### 前端服务 (端口 3000)

```bash
cd frontend && npm run dev
```

### 一键启动（推荐）

```bash
# 终端 1: 后端
.venv/Scripts/python.exe -m src.server

# 终端 2: 前端
cd frontend && npm run dev
```

## 环境变量配置

`.env` 文件配置说明：

```env
# ========== 模型配置 ==========
LLM_MODEL=qwen-turbo              # 默认模型
FAST_LLM=openai:qwen-flash        # 快速模型
SMART_LLM=openai:qwen-plus-latest # 智能模型
STRATEGIC_LLM=openai:qwen-max     # 高级模型

# ========== API 配置 ==========
OPENAI_API_KEY=sk-xxx             # 阿里云百炼 API Key
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# ========== 服务配置 ==========
HOST=0.0.0.0
PORT=8001
```

## 端口管理

### 检查端口占用

```bash
netstat -ano | findstr :8001
netstat -ano | findstr :3000
```

### 杀掉占用进程

```bash
# 根据 PID 杀进程
taskkill /F /PID [PID]

# 杀掉所有 Python 进程
taskkill /F /IM python.exe
```

## 健康检查

### 后端健康检查

```bash
curl -X GET "http://localhost:8001/health" -s
```

预期返回：
```json
{"status": "healthy", "version": "1.0.0"}
```

### 前端访问

浏览器打开: http://localhost:3000

## 常见问题

### 1. 端口被占用 (Errno 10048)

```bash
# 查找占用进程
netstat -ano | findstr :8001

# 杀掉进程
taskkill /F /PID [找到的PID]
```

### 2. 模型 API 欠费

检查控制台: https://home.console.aliyun.com/

### 3. 数据库文件锁定

```bash
# 关闭所有 Python 进程后重试
taskkill /F /IM python.exe
```

## 日志查看

后端日志关键标记：
- `INFO` - 正常信息
- `WARNING` - 警告
- `ERROR` - 错误
- `[RETRIEVE]` - 检索操作
- `[GRADE]` - 评分操作
- `[WEB_SEARCH]` - Web 搜索
- `[HITL]` - 人工审批

## 输出格式

运维报告格式：
```
## 服务状态

**后端**: [运行中/停止] (端口 8001)
**前端**: [运行中/停止] (端口 3000)

## 问题诊断

[问题描述]

## 解决方案

[操作步骤]
```