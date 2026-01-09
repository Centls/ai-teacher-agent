# 错误处理增强说明

## ✅ 完成的改进

### 1. 后端错误分类（src/server.py）

现在后端能够自动检测并分类以下错误类型：

#### LLM/模型 API 错误
- **llm_bad_request** - 模型请求错误
  - **账户欠费**: 检测到 "Arrearage" 关键词
    ```
    ⚠️ 阿里云账户欠费，请充值后重试
    详细信息: 阿里云百炼账户余额不足或欠费，请访问 https://home.console.aliyun.com/ 充值
    ```

  - **模型名称错误**: 检测到 "model not found"
    ```
    ❌ 模型名称错误，请检查 .env 配置
    详细信息: 指定的模型不存在或无权访问
    ```

  - **API Key 错误**: 检测到 "api key" 或 "auth"
    ```
    🔑 API Key 无效，请检查 .env 配置
    详细信息: 阿里云 API Key 无效或已过期
    ```

- **llm_auth_error** - 认证失败
  ```
  🔑 API Key 认证失败，请检查 .env 中的 OPENAI_API_KEY
  ```

- **llm_rate_limit** - 请求频率超限
  ```
  ⏱️ API 调用频率超限，请稍后重试
  ```

- **llm_connection_error** - 网络连接失败
  ```
  🌐 无法连接到模型 API，请检查网络
  ```

#### 其他错误类型
- **vector_db_error** - 知识库/ChromaDB 错误
  ```
  📚 知识库错误，请检查向量数据库
  ```

- **web_search_error** - Web 搜索失败
  ```
  🔍 Web 搜索失败，将使用知识库回答
  ```

- **backend_error** - 通用后端错误
  ```
  ⚙️ 后端处理错误，请查看日志
  ```

### 2. 前端错误展示增强（frontend/src/app/api/agent/stream/route.ts）

前端现在能够：

1. **显示清晰的错误分类**
   - 使用表情符号图标区分错误类型
   - 显示用户友好的错误消息

2. **提供解决方案**
   - 针对常见错误（欠费、API Key 错误、网络问题）给出具体的修复步骤

3. **技术细节可折叠**
   - 普通用户看到简洁的错误说明
   - 开发者可以展开查看完整的技术堆栈

### 3. 错误信息结构

后端返回的错误数据结构：
```json
{
  "type": "error",
  "error_type": "llm_bad_request",
  "message": "⚠️ 阿里云账户欠费，请充值后重试",
  "detail": "阿里云百炼账户余额不足或欠费，请访问 https://home.console.aliyun.com/ 充值",
  "technical_info": "Error code: 400 - {'error': {'message': '...', 'type': 'Arrearage', ...}}"
}
```

前端展示效果：
```markdown
❌ **错误**

⚠️ **阿里云账户欠费，请充值后重试**

**详细信息:**
阿里云百炼账户余额不足或欠费，请访问 https://home.console.aliyun.com/ 充值

**解决方案:**
1. 访问阿里云控制台充值: https://home.console.aliyun.com/
2. 或切换到其他模型（修改 .env 文件）

<details>
<summary>技术细节（点击展开）</summary>

```
Error code: 400 - {'error': {'message': 'Access denied, please make sure your account is in good standing', 'type': 'Arrearage', ...}}
```
</details>
```

## 📊 改进前后对比

### 改进前
```
❌ 500 Internal Server Error
```
- 用户无法判断是后端问题还是模型 API 问题
- 没有解决方案提示
- 需要查看后端日志才能定位问题

### 改进后
```
❌ 错误

⚠️ 阿里云账户欠费，请充值后重试

详细信息:
阿里云百炼账户余额不足或欠费，请访问 https://home.console.aliyun.com/ 充值

解决方案:
1. 访问阿里云控制台充值: https://home.console.aliyun.com/
2. 或切换到其他模型（修改 .env 文件）
```
- 清楚显示错误原因（账户欠费）
- 提供具体的解决步骤
- 区分了后端错误和模型 API 错误

## 🧪 测试建议

1. **测试账户欠费场景**
   - 使用欠费的阿里云账户
   - 发送消息
   - 应该看到清晰的欠费提示和充值链接

2. **测试模型名称错误**
   - 在 .env 中设置一个不存在的模型名
   - 应该看到模型名称错误的提示

3. **测试 API Key 错误**
   - 使用无效的 API Key
   - 应该看到 API Key 无效的提示

4. **测试网络错误**
   - 断开网络或使用错误的 API 地址
   - 应该看到网络连接失败的提示

## 📝 后续可能的改进

1. **错误重试机制**: 对于网络错误和频率限制，自动重试
2. **错误统计**: 记录错误类型和频率，方便调试
3. **用户引导**: 对于常见错误，提供一键修复按钮
4. **多语言支持**: 错误消息支持中英文切换
