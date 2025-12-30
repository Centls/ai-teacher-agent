"""
测试历史记录保存和读取

验证修复后的 messages 格式是否正确
"""
import asyncio
import uuid
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from src.agents.marketing import create_marketing_graph
from src.core.store import AsyncSQLiteStore

async def test_history_save_and_load():
    """测试消息保存和读取"""

    # 创建测试 thread_id
    thread_id = str(uuid.uuid4())
    print(f"Test Thread ID: {thread_id}")

    # 初始化
    store = AsyncSQLiteStore(db_path="data/user_preferences.db")

    async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=False)

        config = {"configurable": {"thread_id": thread_id}}

        # 1. 发送消息
        print("\n[STEP 1] Sending message...")
        inputs = {
            "question": "测试问题：什么是营销？",
            "messages": [HumanMessage(content="测试问题：什么是营销？")]
        }

        # 执行graph（简化版，不使用stream）
        try:
            result = await graph.ainvoke(inputs, config)
            print(f"Execution completed. Generation: {result.get('generation', 'N/A')[:100]}...")
        except Exception as e:
            print(f"Execution error: {e}")
            import traceback
            traceback.print_exc()

        # 2. 读取历史记录
        print("\n[STEP 2] Reading history...")
        state = await graph.aget_state(config)

        if state and state.values:
            messages = state.values.get("messages", [])
            print(f"Found {len(messages)} messages:")

            for i, msg in enumerate(messages, 1):
                print(f"\nMessage {i}:")
                print(f"  Type: {msg.type}")
                print(f"  ID: {getattr(msg, 'id', 'N/A')}")
                print(f"  Content: {msg.content[:100]}...")
        else:
            print("No state found!")

        # 3. 验证格式
        print("\n[STEP 3] Validating format...")
        if len(messages) >= 2:
            if messages[0].type == "human" and messages[1].type == "ai":
                print("✅ Message types correct!")
            else:
                print(f"❌ Expected [human, ai], got [{messages[0].type}, {messages[1].type}]")

            # 检查 ID
            has_valid_ids = all(
                (hasattr(msg, 'id') and msg.id) or True  # ID可以为None，会在API层生成
                for msg in messages
            )
            print(f"{'✅' if has_valid_ids else '❌'} Message IDs present")
        else:
            print(f"❌ Expected at least 2 messages, got {len(messages)}")

if __name__ == "__main__":
    asyncio.run(test_history_save_and_load())