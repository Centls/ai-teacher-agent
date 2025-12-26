import pytest
from unittest.mock import MagicMock, patch
from src.agents.researcher.graph import Researcher
from src.agents.researcher.state import ResearcherState

@pytest.mark.asyncio
async def test_researcher_agent_integration():
    """
    Verifies that the Researcher agent graph correctly calls GPTResearcher.
    """
    # Patch GPTResearcher at the source (nodes.py)
    with patch("src.agents.researcher.nodes.GPTResearcher") as MockResearcher:
        # Setup Mock
        mock_instance = MockResearcher.return_value
        mock_instance.run = MagicMock(return_value="Mock Research Report Content")
        # Make run async-compatible if needed, but MagicMock isn't awaitable by default.
        # We need an AsyncMock or configure the return value to be a future.
        
        # Better way: use AsyncMock if available (Python 3.8+)
        from unittest.mock import AsyncMock
        mock_instance.run = AsyncMock(return_value="Mock Research Report Content")
        
        # Initialize Agent
        agent = Researcher()
        graph = agent.compile_graph()
        
        # Prepare State
        initial_state = {
            "messages": [{"role": "user", "content": "Research Quantum Computing"}],
            "research_plan": [],
            "search_results": [],
            "user_context": {}
        }
        
        # Execute Graph
        print("Invoking graph...")
        result = await graph.ainvoke(initial_state, config={"configurable": {"thread_id": "test_thread"}})
        
        # Assertions
        print("Graph execution finished.")
        
        # 1. Verify GPTResearcher initialization
        MockResearcher.assert_called_with(query="Research Quantum Computing", report_type="research_report")
        
        # 2. Verify run() was awaited
        mock_instance.run.assert_awaited_once()
        
        # 3. Verify Result in State
        last_message = result["messages"][-1]
        assert last_message["role"] == "assistant"
        assert "Mock Research Report Content" in last_message["content"]
        
        print("Verification Successful!")
