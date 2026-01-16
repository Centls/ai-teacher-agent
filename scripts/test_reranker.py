#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Reranker 功能

验证：
1. CrossEncoder 模型加载
2. CPU/GPU 自动检测
3. 重排序功能
"""
import sys
import os
from pathlib import Path

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings, MODELS_DIR


def test_reranker_config():
    """测试配置"""
    print("=" * 60)
    print("1. 配置检查")
    print("=" * 60)
    print(f"   RERANKER_ENABLED: {settings.RERANKER_ENABLED}")
    print(f"   RERANKER_MODEL: {settings.RERANKER_MODEL}")
    print(f"   RERANKER_MAX_LENGTH: {settings.RERANKER_MAX_LENGTH}")
    print(f"   RERANKER_DEVICE: {settings.RERANKER_DEVICE}")
    print(f"   MODELS_DIR: {MODELS_DIR}")
    print(f"   HF_HOME: {MODELS_DIR / 'huggingface'}")
    print()


def test_device_detection():
    """测试设备检测"""
    print("=" * 60)
    print("2. 设备检测")
    print("=" * 60)

    import torch
    print(f"   PyTorch 版本: {torch.__version__}")
    print(f"   CUDA 可用: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   CUDA 设备: {torch.cuda.get_device_name(0)}")

    mps_available = hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()
    print(f"   MPS 可用 (Apple): {mps_available}")
    print()


def test_reranker_loading():
    """测试 Reranker 加载"""
    print("=" * 60)
    print("3. Reranker 模型加载")
    print("=" * 60)

    from src.services.rag.pipeline import RAGPipeline, _get_reranker_device

    device = _get_reranker_device()
    print(f"   检测到设备: {device}")

    # 创建 Pipeline 实例（懒加载，不会立即加载 Reranker）
    print("   正在初始化 RAGPipeline...")

    # 直接测试 CrossEncoder 加载
    print(f"   正在加载 Reranker: {settings.RERANKER_MODEL}")
    print("   (首次运行会下载模型，请耐心等待...)")

    from sentence_transformers import CrossEncoder

    reranker = CrossEncoder(
        settings.RERANKER_MODEL,
        max_length=settings.RERANKER_MAX_LENGTH,
        device=device,
        trust_remote_code=True
    )
    print(f"   ✅ Reranker 加载成功!")
    print()

    return reranker


def test_reranking(reranker):
    """测试重排序功能"""
    print("=" * 60)
    print("4. 重排序功能测试")
    print("=" * 60)

    query = "如何提高营销效果"
    documents = [
        "今天天气很好，适合出去散步。",
        "营销策略需要结合目标用户群体的特点来制定。",
        "Python 是一门流行的编程语言。",
        "提高营销效果的关键在于精准定位和内容优化。",
        "机器学习在推荐系统中有广泛应用。",
    ]

    print(f"   查询: {query}")
    print(f"   文档数: {len(documents)}")
    print()

    # 构建 query-document pairs
    pairs = [[query, doc] for doc in documents]

    # 计算相关性分数
    scores = reranker.predict(pairs)

    # 排序
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

    print("   排序结果:")
    for i, (doc, score) in enumerate(ranked, 1):
        print(f"   {i}. [分数: {score:.4f}] {doc[:50]}...")
    print()

    # 验证：营销相关文档应该排在前面
    top_doc = ranked[0][0]
    assert "营销" in top_doc, f"预期营销相关文档排在第一，实际: {top_doc}"
    print("   ✅ 重排序功能正常!")
    print()


def main():
    print()
    print("🚀 BGE-Reranker-v2-m3 功能测试")
    print("=" * 60)
    print()

    # 1. 配置检查
    test_reranker_config()

    # 2. 设备检测
    test_device_detection()

    # 3. 模型加载
    reranker = test_reranker_loading()

    # 4. 重排序测试
    test_reranking(reranker)

    print("=" * 60)
    print("✅ 所有测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()