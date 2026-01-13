# Configuration Module (配置模块)

## 简介
本模块负责管理系统的所有配置项、Prompt 模板和静态资源定义。

## 核心文件

### 1. `settings.py`
*   **功能**: 系统配置的单一大地真理 (Single Source of Truth)。
*   **机制**: 自动加载 `.env` 环境变量，并提供强类型的配置访问接口 (e.g., `settings.OPENAI_API_KEY`)。

### 2. `prompts/`
*   存放各个智能体使用的 System Prompts 和模板文件。

### 3. `capability.yaml` & `services.yaml`
*   **功能**: 定义智能体的能力描述和服务注册信息，供 Supervisor 进行路由决策。

## 使用方式
在代码中引用配置：
```python
from config.settings import settings

print(settings.DEFAULT_MODEL)
```
