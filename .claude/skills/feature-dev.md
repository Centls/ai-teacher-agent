# Skill: 功能开发

当用户说 "新功能"、"添加功能"、"实现xxx" 时激活此 Skill。

## 核心能力

1. **需求分析与拆解**
2. **技术方案设计**
3. **代码实现与测试**
4. **集成与验证**

## 开发流程

### Phase 1: 需求分析

1. 明确功能目标
2. 确定输入输出
3. 识别依赖关系
4. 评估影响范围

### Phase 2: 技术设计

1. 确定实现位置
2. 设计数据流
3. 定义接口契约
4. 考虑边界情况

### Phase 3: 实现

1. 编写核心代码
2. 添加必要日志
3. 处理错误情况
4. 编写单元测试

### Phase 4: 验证

1. 本地功能测试
2. 集成测试
3. 边界测试
4. 用户验收

## 项目分层

```
┌─────────────────────────────────────────┐
│            Frontend (Next.js)            │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │Components│ │  Hooks  │ │  Services │  │
│  └─────────┘ └─────────┘ └───────────┘  │
└─────────────────────────────────────────┘
                    │
                    ▼ HTTP/SSE
┌─────────────────────────────────────────┐
│            Backend (FastAPI)             │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │  Routes │ │ Agents  │ │  Services │  │
│  └─────────┘ └─────────┘ └───────────┘  │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│           Data Layer                     │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐  │
│  │ ChromaDB│ │ SQLite  │ │  External │  │
│  │ (Vector)│ │ (State) │ │   APIs    │  │
│  └─────────┘ └─────────┘ └───────────┘  │
└─────────────────────────────────────────┘
```

## 功能类型模板

### 类型 A: 新增 API 端点

```python
# src/server.py

@app.post("/api/new-feature")
async def new_feature(request: NewFeatureRequest):
    """
    新功能端点

    Args:
        request: 请求参数

    Returns:
        响应结果
    """
    try:
        result = await process_feature(request)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"[NEW_FEATURE] 错误: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )
```

### 类型 B: 新增 LangGraph 节点

```python
# src/agents/marketing/nodes.py

async def new_node(state: MarketingState) -> dict:
    """
    新节点

    处理逻辑:
    1. 读取状态
    2. 执行操作
    3. 返回更新
    """
    print(f"[NEW_NODE] 开始处理")

    # 业务逻辑
    result = await process_something(state["input"])

    print(f"[NEW_NODE] 处理完成")
    return {"output": result}
```

### 类型 C: 新增前端组件

```typescript
// frontend/src/components/NewComponent.tsx

interface NewComponentProps {
  data: DataType;
  onAction: (id: string) => void;
}

export function NewComponent({ data, onAction }: NewComponentProps) {
  const [state, setState] = useState<StateType>(initialState);

  useEffect(() => {
    // 初始化逻辑
    return () => {
      // 清理逻辑
    };
  }, []);

  return (
    <div className="new-component">
      {/* 组件内容 */}
    </div>
  );
}
```

## 检查清单

开发完成前确认：

- [ ] 代码符合项目规范
- [ ] 添加了必要的类型定义
- [ ] 错误处理完善
- [ ] 添加了调试日志
- [ ] 本地测试通过
- [ ] 无硬编码配置

## 输出格式

开发报告格式：
```
## 功能开发报告

**功能名称**: [名称]
**影响范围**: [前端/后端/全栈]

### 修改文件

1. [文件路径] - [修改说明]
2. [文件路径] - [修改说明]

### 新增接口

**端点**: [URL]
**方法**: [GET/POST]
**参数**: [参数说明]

### 测试方式

[测试命令或步骤]
```