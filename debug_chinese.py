import asyncio
import os
from dotenv import load_dotenv
from gpt_researcher import GPTResearcher

load_dotenv()

async def test_chinese_research():
    query = "你是谁"
    print(f"Testing query: {query} with language='chinese'")
    try:
        researcher = GPTResearcher(query=query, report_type="research_report", language="chinese")
        print("Conducting research...")
        await researcher.conduct_research()
        print("Writing report...")
        report = await researcher.write_report()
        print("Success!")
        print(report[:200])
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chinese_research())
