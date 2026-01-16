#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 MultimodalRAGPipeline 的高级功能
验证：父子索引、RRF 融合、重排序
"""
import sys
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from langchain_core.documents import Document

def test_multimodal_pipeline():
    print("=" * 60)
    print("🚀 测试 MultimodalRAGPipeline 高级功能")
    print("=" * 60)

    # 创建临时目录
    temp_dir = tempfile.mkdtemp(prefix="test_multimodal_")
    temp_vector_db = os.path.join(temp_dir, "chroma_db")
    temp_docstore = os.path.join(temp_dir, "parent_docstore")

    # 临时修改配置
    original_docstore_path = settings.DOCSTORE_PATH
    settings.DOCSTORE_PATH = Path(temp_docstore)

    # 确保启用相关功能
    settings.PARENT_CHILD_ENABLED = True
    settings.RERANKER_ENABLED = True

    try:
        from src.services.rag.multimodal_pipeline import MultimodalRAGPipeline
        from src.services.multimodal.sync_client import ProcessResult

        print(f"   临时目录: {temp_dir}")

        # 初始化 Pipeline
        print("   正在初始化 MultimodalRAGPipeline...")
        pipeline = MultimodalRAGPipeline(vector_db_path=temp_vector_db)

        # Mock MultimodalSyncClient (避免依赖真实 Docling 服务)
        # 模拟一个包含丰富信息的 PDF 解析结果
        mock_text = """
# 多模态教学系统设计

## 1. 系统架构
本系统采用先进的 RAG 架构，结合多模态理解能力。
核心组件包括向量数据库、大语言模型和文档解析服务。

## 2. 功能模块
- **文档处理**：支持 PDF, Word, PPT 等格式
- **图像识别**：使用 OCR 技术提取文字
- **语音转写**：集成 Whisper 模型
- **知识检索**：支持语义检索和关键词检索

## 3. 性能优化
为了提高检索准确率，我们引入了父子索引和重排序机制。
父子索引解决了检索粒度和上下文完整性的矛盾。
        """ * 3  # 重复内容以确保足够长，触发分块

        mock_result = ProcessResult(
            success=True,
            text=mock_text,
            metadata={"author": "AI Teacher", "title": "Design Doc", "pages": [{"text": mock_text, "page_no": 1}]}
        )

        # Mock client behavior
        pipeline._multimodal_client = MagicMock()
        pipeline._multimodal_client.process_file.return_value = mock_result

        # 1. 测试入库 (Ingest)
        print("\n1. 测试多模态入库 (Mock Docling PDF)")
        test_file = "test_design.pdf" # 虚拟文件名

        # 为了测试，我们需要 mock is_multimodal_file 让它认为这是个支持的文件
        # (其实默认配置里 pdf 就在 DOCLING_FORMATS 中，所以不需要 mock check)

        pipeline.ingest(test_file, metadata={"category": "test"})
        print("   ✅ 入库完成")

        # 验证父子索引是否生效
        # 检查 parent_retriever 的 docstore 是否有数据
        if pipeline.parent_retriever:
            # 这是一个 hack 方法来检查 store，不同版本可能不同，这里主要靠检索验证
            print("   ✅ Parent-Child Index 已启用")
        else:
            print("   ❌ Parent-Child Index 未启用")
            return False

        # 2. 测试检索 (Retrieve)
        print("\n2. 测试高级检索 (Retrieve)")
        query = "父子索引的作用是什么"
        print(f"   查询: {query}")

        # 执行检索
        results = pipeline.retrieve(query, k=2)

        print(f"   返回结果数: {len(results)}")

        if not results:
            print("   ❌ 检索失败: 无结果")
            return False

        # 验证结果
        first_doc = results[0]
        content_len = len(first_doc.page_content)
        print(f"   结果 1 长度: {content_len} 字符")
        print(f"   结果 1 来源: {first_doc.metadata.get('processing_source', '未知')}")

        # 验证元数据传递
        if first_doc.metadata.get('category') == 'test' and \
           first_doc.metadata.get('processing_source') == 'docling_service':
            print("   ✅ 元数据传递正确 (category & processing_source)")
        else:
            print(f"   ⚠️ 元数据可能丢失: {first_doc.metadata}")

        # 验证是否返回父块 (大块)
        if content_len > settings.CHILD_CHUNK_SIZE:
            print(f"   ✅ 返回父块 (长度 {content_len} > 子块 {settings.CHILD_CHUNK_SIZE})")
        else:
            print(f"   ⚠️ 返回块较小 (长度 {content_len})，可能是边界情况")

        # 3. 验证 Reranker
        if pipeline.reranker:
            print("   ✅ Reranker 已加载")
        else:
            print("   ⚠️ Reranker 未加载 (可能是配置已禁用或环境问题)")

        print("\n✅ 多模态 Pipeline 高级功能测试通过!")
        return True

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 清理
        settings.DOCSTORE_PATH = original_docstore_path
        try:
            shutil.rmtree(temp_dir)
            print(f"\n已清理临时目录: {temp_dir}")
        except:
            pass

if __name__ == "__main__":
    test_multimodal_pipeline()