#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知识库重建脚本 (Re-ingest Knowledge Base)

功能：
1. 清空现有的 ChromaDB 和 DocStore（彻底清理旧数据）
2. 扫描 data/ 目录下的所有支持文件
3. 使用最新的 MultimodalRAGPipeline 重新摄取数据
   - 自动应用父子索引 (Parent-Child Index)
   - 自动进行 RRF 融合准备
   - 自动清洗元数据

警告：此操作不可逆，会删除所有向量数据！
"""
import sys
import os
import shutil
from pathlib import Path
import logging

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from src.services.rag.multimodal_pipeline import MultimodalRAGPipeline

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def clear_data():
    """清空向量库和文档存储"""
    print("\n🧹 正在清理旧数据...")

    # 1. 清理 ChromaDB
    chroma_path = Path("./data/chroma_db")
    if chroma_path.exists():
        try:
            shutil.rmtree(chroma_path)
            logger.info(f"已删除: {chroma_path}")
        except Exception as e:
            logger.error(f"删除 ChromaDB 失败: {e}")

    # 2. 清理 Parent DocStore
    docstore_path = settings.DOCSTORE_PATH
    if docstore_path.exists():
        try:
            shutil.rmtree(docstore_path)
            logger.info(f"已删除: {docstore_path}")
        except Exception as e:
            logger.error(f"删除 DocStore 失败: {e}")

    print("✅ 数据清理完成")

def reingest_all():
    """重新摄取所有文档"""
    print("\n🚀 开始重新摄取 (使用父子索引模式)...")

    # 强制启用父子索引
    settings.PARENT_CHILD_ENABLED = True

    # 初始化 Pipeline
    pipeline = MultimodalRAGPipeline()

    # 获取支持的格式
    supported_formats = pipeline.DOCLING_FORMATS | pipeline.TEXT_FORMATS

    data_dir = Path("./data")
    if not data_dir.exists():
        logger.error("data/ 目录不存在！")
        return

    # 扫描文件
    files_to_ingest = []
    for ext in supported_formats:
        files_to_ingest.extend(data_dir.rglob(f"*{ext}"))
        # 兼容大写后缀
        files_to_ingest.extend(data_dir.rglob(f"*{ext.upper()}"))

    # 去重并排序
    files_to_ingest = sorted(list(set(files_to_ingest)))

    # 过滤掉系统生成的文件（如 .db, .sqlite 等不在 supported_formats 中的文件自然会被过滤）
    # 但要小心不要把自己生成的 knowledge.db 误删，不过这里只读文件

    total_files = len(files_to_ingest)
    print(f"📄 发现 {total_files} 个文件待处理")

    for i, file_path in enumerate(files_to_ingest, 1):
        try:
            print(f"[{i}/{total_files}] 处理: {file_path.name} ...")

            # 确定知识类型 (根据目录或默认)
            # 简单的启发式：如果文件在 data/products 下，标记为 product_raw
            category = "general"
            if "products" in str(file_path):
                category = "product_raw"
            elif "sales" in str(file_path):
                category = "sales_raw"
            elif "materials" in str(file_path):
                category = "material"

            pipeline.ingest(str(file_path), metadata={"category": category})

        except Exception as e:
            logger.error(f"❌ 处理失败 {file_path.name}: {e}")

    print("\n🎉 重建完成！现在 MarketingTeacher 可以使用高级检索功能了。")

if __name__ == "__main__":
    print("=" * 60)
    print("⚠️  警告：此操作将清空所有现有的向量库数据！")
    print("=" * 60)

    confirm = input("确认继续吗？(y/n): ")
    if confirm.lower() == 'y':
        clear_data()
        reingest_all()
    else:
        print("操作已取消")
