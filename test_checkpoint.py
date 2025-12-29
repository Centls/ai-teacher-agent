import asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

async def test():
    try:
        async with AsyncSqliteSaver.from_conn_string("test_checkpoint.sqlite") as saver:
            print("Checkpointer created successfully")
            print(f"Type: {type(saver)}")
            print("SUCCESS!")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
