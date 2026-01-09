# Skill: LangGraph 工作流

当用户说 "工作流问题"、"Graph 调试"、"节点问题"、"状态管理" 时激活此 Skill。

## 核心能力

1. **LangGraph 状态管理**
2. **节点调试与优化**
3. **HITL (Human-in-the-Loop) 流程**
4. **Checkpoint 状态恢复**

## 项目 Graph 架构

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  retrieve   │ ← 知识库检索
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │    grade    │ ← 文档评分
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        grade=yes    grade=partial   grade=no
              │            │            │
              ▼            ▼            ▼
         ┌────────┐  ┌──────────┐  ┌──────────┐
         │generate│  │web_search│  │web_search│
         └────────┘  │(hybrid)  │  │(pure)    │
                     └────┬─────┘  └────┬─────┘
                          │             │
                     ┌────▼─────┐       │
                     │ hitl_gate│◄──────┘
                     └────┬─────┘
                          │
                    ┌─────▼─────┐
                    │  generate │
                    └─────┬─────┘
                          │
                    ┌─────▼─────┐
                    │    END    │
                    └───────────┘
```

## 关键文件

| 文件 | 用途 |
|------|------|
| `src/agents/marketing/graph.py` | Graph 定义 |
| `src/agents/marketing/nodes.py` | 节点实现 |
| `src/agents/marketing/state.py` | 状态定义 |
| `src/server.py` | Graph 调用 |

## 状态定义

```python
class MarketingState(TypedDict):
    question: str                    # 用户问题
    context: Annotated[str, ...]    # 检索上下文
    grade: str                       # yes/partial/no
    force_web_search: bool          # 强制 Web 搜索
    kb_docs: list                   # 知识库文档
    web_results: list               # Web 搜索结果
    hitl_approved: bool             # HITL 审批状态
    answer: str                     # 最终答案
```

## 调试流程

### Step 1: 检查状态传递
关键日志标记：
```python
print(f"[RETRIEVE] 检索到 {len(docs)} 个文档")
print(f"[GRADE] 评分结果: {grade}")
print(f"[WEB_SEARCH] 模式: {'混合' if kb_docs else '纯搜索'}")
```

### Step 2: Checkpoint 问题排查

常见问题：
1. **Graph 结构不一致** - with_hitl 参数必须保持一致
2. **状态 reducer 冲突** - 使用 `keep_latest` reducer
3. **Thread ID 重复** - 使用唯一 thread_id

### Step 3: HITL 审批流程

```python
# 正确的审批处理
marketing_graph = create_marketing_graph(
    checkpointer=checkpointer,
    store=store,
    with_hitl=True  # 始终保持 True
)

# 恢复执行
result = await marketing_graph.ainvoke(
    Command(resume={"approved": approved}),
    config={"configurable": {"thread_id": thread_id}}
)
```

## 常见问题

### 1. 审批后报错

**原因**: Graph 结构不一致
**解决**: 始终使用 `with_hitl=True`

### 2. 混合模式未触发

**检查点**:
- `grade_documents_node` 返回值
- `kb_docs` 是否正确传递
- `force_web_search` 状态

### 3. 状态丢失

**原因**: Checkpoint 加载失败
**解决**: 检查 `checkpoints.sqlite` 文件

## 输出格式

调试报告格式：
```
## 工作流诊断

**当前节点**: [节点名]
**状态快照**:
- question: [值]
- grade: [值]
- force_web_search: [值]

## 问题定位

**问题节点**: [节点]
**根本原因**: [原因]

## 修复方案

[代码修改]
```