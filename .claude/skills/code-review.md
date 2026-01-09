# Skill: 代码审查

当用户说 "代码审查"、"review"、"检查代码"、"最佳实践" 时激活此 Skill。

## 核心能力

1. **代码质量检查**
2. **安全漏洞识别**
3. **性能问题发现**
4. **最佳实践建议**

## 审查清单

### Python 后端

- [ ] 类型注解完整
- [ ] 异常处理得当
- [ ] 日志记录规范
- [ ] 无硬编码敏感信息
- [ ] 异步代码正确使用 await
- [ ] 资源正确释放（连接、文件等）

### TypeScript 前端

- [ ] 类型定义完整（无 any）
- [ ] useEffect 依赖正确
- [ ] 事件监听正确清理
- [ ] 错误边界处理
- [ ] 无内存泄漏风险

### LangGraph 工作流

- [ ] 状态定义清晰
- [ ] 节点职责单一
- [ ] 条件路由正确
- [ ] Checkpoint 正确配置
- [ ] HITL 流程完整

## 安全检查

### OWASP Top 10 相关

| 风险类型 | 检查点 |
|----------|--------|
| 注入攻击 | SQL 参数化、命令转义 |
| 认证失效 | Token 验证、会话管理 |
| 敏感数据 | API Key 不硬编码 |
| XSS | 用户输入转义 |
| SSRF | URL 验证 |

### 敏感信息检查

```bash
# 检查是否有硬编码的 API Key
grep -r "sk-" --include="*.py" --include="*.ts"
grep -r "api_key" --include="*.py" --include="*.ts"
```

## 性能检查

### Python

- [ ] 避免 N+1 查询
- [ ] 大数据使用生成器
- [ ] 缓存重复计算
- [ ] 异步 I/O 充分利用

### React/Next.js

- [ ] 组件正确 memo
- [ ] 列表使用唯一 key
- [ ] 避免不必要重渲染
- [ ] 图片优化加载

## 审查流程

### Step 1: 快速扫描
```bash
# Python 格式检查
ruff check src/

# TypeScript 类型检查
cd frontend && npm run typecheck
```

### Step 2: 深度审查

重点关注：
1. 新增/修改的函数
2. API 端点变更
3. 状态管理逻辑
4. 错误处理路径

### Step 3: 安全审计

```bash
# 检查敏感文件变更
git diff --name-only | grep -E "(\.env|config|secret)"
```

## 输出格式

审查报告格式：
```
## 代码审查报告

**文件**: [文件路径]
**审查范围**: [函数/类/模块]

### 问题发现

#### 严重 (Critical)
- [ ] [问题描述] - [文件:行号]

#### 警告 (Warning)
- [ ] [问题描述] - [文件:行号]

#### 建议 (Suggestion)
- [ ] [改进建议]

### 修复建议

[具体代码修改]
```

## 常见问题模式

### 1. 未处理的 Promise 拒绝

```typescript
// Bad
fetchData().then(handleData);

// Good
fetchData().then(handleData).catch(handleError);
```

### 2. 资源未释放

```python
# Bad
conn = get_connection()
# 使用 conn...

# Good
async with get_connection() as conn:
    # 使用 conn...
```

### 3. 敏感信息泄露

```python
# Bad
print(f"API Key: {api_key}")

# Good
print(f"API Key: {api_key[:8]}...")
```