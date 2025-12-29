# Researcher Agent (研究员)

## 简介
研究员智能体负责执行深度网络搜索和信息整合任务。它利用 `gpt-researcher` 库来生成详尽的研究报告。

## 核心功能
*   **Deep Research**: 对给定主题进行多源网络搜索。
*   **Report Generation**: 汇总搜索结果，生成结构化的研究报告。
*   **Source Tracking**: 自动记录引用来源。

## 集成方式
目前 Researcher 通过 `GPTResearcher` 库直接调用，未来计划封装为 LangGraph 节点以支持更复杂的协作流程。

### 调用示例
```python
from gpt_researcher import GPTResearcher

researcher = GPTResearcher(query="最新的 AI 营销趋势", report_type="research_report")
await researcher.conduct_research()
report = await researcher.write_report()
```

## 关键文件
*   `graph.py`: (待实现) 计划中的 LangGraph 封装。
*   `tools.py`: 搜索工具配置。

## 依赖
*   `gpt-researcher`: 核心研究引擎
*   `tavily-python`: 搜索引擎 API (通常配合使用)
