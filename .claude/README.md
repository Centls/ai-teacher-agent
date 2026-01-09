# AI Teacher Nexus - Skills 配置

本项目为 Claude 配置了专用的 Skills，用于提升 AI 辅助开发效率。

## 可用 Skills

| Skill | 文件 | 触发关键词 |
|-------|------|-----------|
| 后端调试 | `skills/debug-backend.md` | "调试后端"、"后端报错"、"服务器问题" |
| 前端开发 | `skills/frontend-dev.md` | "前端问题"、"UI 修改"、"组件开发" |
| LangGraph 工作流 | `skills/langgraph-workflow.md` | "工作流问题"、"Graph 调试"、"节点问题" |
| 部署运维 | `skills/deploy-ops.md` | "部署"、"启动服务"、"环境配置" |
| 代码审查 | `skills/code-review.md` | "代码审查"、"review"、"检查代码" |
| 功能开发 | `skills/feature-dev.md` | "新功能"、"添加功能"、"实现xxx" |

## 专家 Agents

| Agent | 文件 | 用途 |
|-------|------|------|
| RAG 专家 | `agents/rag-expert.md` | RAG/知识库问题诊断 |

## 使用方式

### 方式 1: 自然语言触发

直接描述问题，Claude 会自动匹配合适的 Skill：

```
"后端报错 500，帮我看看"
→ 自动使用 debug-backend skill

"前端样式有问题"
→ 自动使用 frontend-dev skill
```

### 方式 2: 明确指定

```
"使用后端调试 skill 帮我排查这个问题"
"参考 langgraph-workflow skill 检查工作流"
```

### 方式 3: 组合使用

```
"用 RAG 专家 + LangGraph 工作流 skill 帮我调试混合模式"
```

## 自定义命令

查看 `commands.json` 获取可用的快捷命令。

## 目录结构

```
.claude/
├── README.md              # 本文件
├── commands.json          # 自定义命令
├── settings.local.json    # 本地设置
├── agents/
│   └── rag-expert.md     # RAG 专家配置
├── hooks/
│   └── pre-commit.sh     # 预提交钩子
└── skills/
    ├── debug-backend.md      # 后端调试
    ├── frontend-dev.md       # 前端开发
    ├── langgraph-workflow.md # LangGraph 工作流
    ├── deploy-ops.md         # 部署运维
    ├── code-review.md        # 代码审查
    └── feature-dev.md        # 功能开发
```