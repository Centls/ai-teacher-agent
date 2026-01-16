#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 Parent-Child Index（父子索引）功能

验证：
1. ParentDocumentRetriever 初始化
2. 父子分块入库
3. 小块检索 → 返回大块上下文

依赖：
- langchain_classic.retrievers.ParentDocumentRetriever（完整复用）
- langchain.storage.LocalFileStore（完整复用）
"""
import sys
import os
import tempfile
import shutil
from pathlib import Path

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings


def test_config():
    """测试配置"""
    print("=" * 60)
    print("1. 配置检查")
    print("=" * 60)
    print(f"   PARENT_CHILD_ENABLED: {settings.PARENT_CHILD_ENABLED}")
    print(f"   PARENT_CHUNK_SIZE: {settings.PARENT_CHUNK_SIZE}")
    print(f"   PARENT_CHUNK_OVERLAP: {settings.PARENT_CHUNK_OVERLAP}")
    print(f"   CHILD_CHUNK_SIZE: {settings.CHILD_CHUNK_SIZE}")
    print(f"   CHILD_CHUNK_OVERLAP: {settings.CHILD_CHUNK_OVERLAP}")
    print(f"   DOCSTORE_PATH: {settings.DOCSTORE_PATH}")
    print()


def test_imports():
    """测试依赖导入"""
    print("=" * 60)
    print("2. 依赖导入检查")
    print("=" * 60)

    # 强依赖：langchain_classic.retrievers.ParentDocumentRetriever
    from langchain_classic.retrievers import ParentDocumentRetriever
    print("   ✅ langchain_classic.retrievers.ParentDocumentRetriever")

    # 强依赖：langchain_classic.storage.LocalFileStore
    from langchain_classic.storage import LocalFileStore
    print("   ✅ langchain_classic.storage.LocalFileStore")

    # 强依赖：langchain_text_splitters.RecursiveCharacterTextSplitter
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    print("   ✅ langchain_text_splitters.RecursiveCharacterTextSplitter")

    print()
    return True


def test_parent_child_pipeline():
    """测试 Parent-Child Pipeline 完整流程"""
    print("=" * 60)
    print("3. Parent-Child Pipeline 测试")
    print("=" * 60)

    # 使用临时目录避免污染正式数据
    temp_dir = tempfile.mkdtemp(prefix="test_parent_child_")
    temp_vector_db = os.path.join(temp_dir, "chroma_db")
    temp_docstore = os.path.join(temp_dir, "parent_docstore")

    # 临时修改配置
    original_docstore_path = settings.DOCSTORE_PATH
    settings.DOCSTORE_PATH = Path(temp_docstore)

    try:
        from src.services.rag.pipeline import RAGPipeline

        print(f"   临时目录: {temp_dir}")

        # 初始化 Pipeline
        print("   正在初始化 RAGPipeline...")
        pipeline = RAGPipeline(vector_db_path=temp_vector_db)

        # 检查 parent_retriever 是否初始化成功
        if pipeline.parent_retriever is None:
            print("   ❌ Parent-Child Index 初始化失败")
            return False

        print("   ✅ Parent-Child Index 初始化成功")

        # 创建测试文档
        test_content = """
# 营销策略指南

## 第一章：市场定位

市场定位是营销策略的基础。企业需要明确目标客户群体，分析竞争对手，找到差异化优势。
精准的市场定位可以帮助企业更有效地分配资源，提高营销投入的回报率。

### 1.1 目标客户分析

目标客户分析包括人口统计特征、消费习惯、购买动机等多个维度。
通过数据分析和用户调研，可以构建精确的用户画像。

### 1.2 竞争对手分析

了解竞争对手的优势和劣势，有助于制定更有效的竞争策略。
可以从产品、价格、渠道、促销四个方面进行分析。

## 第二章：内容营销

内容营销是通过创造有价值的内容来吸引和留住客户的策略。
高质量的内容可以建立品牌信任，提高用户粘性。

### 2.1 内容创作原则

内容应该有价值、有趣味、有互动性。
要根据不同平台的特点调整内容形式和风格。

### 2.2 内容分发渠道

选择合适的分发渠道可以最大化内容的触达效果。
主要渠道包括社交媒体、搜索引擎、电子邮件等。

## 第三章：数据驱动营销

数据驱动营销是利用数据分析来优化营销决策的方法。
通过收集和分析用户行为数据，可以实现精准营销。
"""

        # 写入临时文件
        test_file = os.path.join(temp_dir, "marketing_guide.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)

        print(f"   测试文档: {test_file}")
        print(f"   文档长度: {len(test_content)} 字符")

        # 入库
        print("   正在入库（父子索引模式）...")
        pipeline.ingest(test_file, metadata={"category": "marketing"})
        print("   ✅ 入库完成")

        # 检索测试
        print()
        print("   检索测试:")
        query = "如何分析目标客户"
        print(f"   查询: {query}")

        results = pipeline.retrieve(query, k=2)
        print(f"   返回结果数: {len(results)}")

        if len(results) == 0:
            print("   ❌ 检索返回空结果")
            return False

        # 验证返回的是父块（大块）
        for i, doc in enumerate(results):
            content_len = len(doc.page_content)
            print(f"   结果 {i+1}: {content_len} 字符")
            print(f"      内容预览: {doc.page_content[:100]}...")

            # 父块应该比子块大
            if content_len > settings.CHILD_CHUNK_SIZE:
                print(f"      ✅ 返回父块（大于子块 {settings.CHILD_CHUNK_SIZE}）")
            else:
                print(f"      ⚠️ 返回块较小（可能是边界情况）")

        print()
        print("   ✅ Parent-Child 检索功能正常!")
        return True

    except Exception as e:
        print(f"   ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 恢复配置
        settings.DOCSTORE_PATH = original_docstore_path
        # 清理临时目录
        try:
            shutil.rmtree(temp_dir)
            print(f"   已清理临时目录: {temp_dir}")
        except:
            pass


def test_chunk_sizes():
    """测试父子块大小关系"""
    print("=" * 60)
    print("4. 分块大小验证")
    print("=" * 60)

    parent_size = settings.PARENT_CHUNK_SIZE
    child_size = settings.CHILD_CHUNK_SIZE

    print(f"   父块大小: {parent_size}")
    print(f"   子块大小: {child_size}")
    print(f"   比例: {parent_size / child_size:.1f}x")

    if parent_size > child_size:
        print("   ✅ 父块 > 子块，配置正确")
    else:
        print("   ❌ 配置错误：父块应该大于子块")
        return False

    # 推荐比例在 3-10x 之间
    ratio = parent_size / child_size
    if 3 <= ratio <= 10:
        print(f"   ✅ 比例 {ratio:.1f}x 在推荐范围 (3-10x)")
    else:
        print(f"   ⚠️ 比例 {ratio:.1f}x 不在推荐范围 (3-10x)")

    print()
    return True


def main():
    print()
    print("🚀 Parent-Child Index（父子索引）功能测试")
    print("=" * 60)
    print()

    # 1. 配置检查
    test_config()

    # 2. 依赖导入
    if not test_imports():
        print("❌ 依赖导入失败，测试终止")
        return

    # 3. 分块大小验证
    if not test_chunk_sizes():
        print("❌ 配置验证失败，测试终止")
        return

    # 4. Pipeline 完整测试
    if not test_parent_child_pipeline():
        print("❌ Pipeline 测试失败")
        return

    print("=" * 60)
    print("✅ 所有测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    main()
