"""
测试 SQLiteStore 持久化功能

运行两次此脚本：
1. 第一次运行：写入数据
2. 第二次运行：读取数据，验证持久化成功
"""

import asyncio
from src.core.store import AsyncSQLiteStore


async def test_write():
    """写入用户偏好规则"""
    store = AsyncSQLiteStore(db_path="test_store.db")

    namespace = ("marketing_preferences",)
    key = "user_rules"

    # 写入测试规则
    test_rules = {
        "rules": "1. 用简洁的语言回答\n2. 提供具体案例\n3. 使用营销术语"
    }

    await store.aput(namespace, key, test_rules)
    print(f"[OK] 写入成功: {test_rules}")

    # 立即读取验证
    item = await store.aget(namespace, key)
    if item:
        print(f"[OK] 立即读取成功: {item.value}")
    else:
        print("[ERROR] 立即读取失败")


async def test_read():
    """读取已持久化的用户偏好规则"""
    store = AsyncSQLiteStore(db_path="test_store.db")

    namespace = ("marketing_preferences",)
    key = "user_rules"

    # 读取规则
    item = await store.aget(namespace, key)

    if item:
        print(f"[OK] 持久化成功！读取到的规则: {item.value}")
        print(f"   创建时间: {item.created_at}")
        print(f"   更新时间: {item.updated_at}")
    else:
        print("[ERROR] 未找到规则，请先运行 test_write()")


async def test_update():
    """更新规则并验证 updated_at 改变"""
    store = AsyncSQLiteStore(db_path="test_store.db")

    namespace = ("marketing_preferences",)
    key = "user_rules"

    # 更新规则
    updated_rules = {
        "rules": "1. 用简洁的语言回答\n2. 提供具体案例\n3. 使用营销术语\n4. 添加数据支撑"
    }

    await store.aput(namespace, key, updated_rules)
    print(f"[OK] 更新成功: {updated_rules}")

    # 读取验证
    item = await store.aget(namespace, key)
    if item:
        print(f"   创建时间: {item.created_at}")
        print(f"   更新时间: {item.updated_at}")


async def test_delete():
    """删除规则"""
    store = AsyncSQLiteStore(db_path="test_store.db")

    namespace = ("marketing_preferences",)
    key = "user_rules"

    await store.adelete(namespace, key)
    print(f"[OK] 删除成功")

    # 验证删除
    item = await store.aget(namespace, key)
    if item is None:
        print("[OK] 验证成功：规则已删除")
    else:
        print("[ERROR] 删除失败")


async def main():
    print("=== SQLiteStore 持久化测试 ===\n")

    print("【测试 1】写入规则")
    await test_write()
    print()

    print("【测试 2】读取规则（验证持久化）")
    await test_read()
    print()

    print("【测试 3】更新规则")
    await test_update()
    print()

    print("【测试 4】删除规则")
    await test_delete()
    print()

    print("=== 测试完成 ===")
    print("请重启 Python 进程后再次运行 test_read()，验证数据是否持久化")


if __name__ == "__main__":
    asyncio.run(main())
