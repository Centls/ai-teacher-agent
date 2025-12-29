from typing import List, Dict, Any
from langchain_core.messages import HumanMessage, BaseMessage
from src.agents.marketing.llm import llm
from src.agents.marketing.prompts import REFLECTION_PROMPT

def _prep_conversation(messages: List[BaseMessage]) -> str:
    convo = []
    for m in messages:
        if isinstance(m, HumanMessage):
            convo.append(f"User: {m.content}")
        else:
            convo.append(f"Assistant: {m.content}")
    return "\n".join(convo)

async def reflect_on_feedback(messages: List[BaseMessage], current_rules: str = "*no rules yet*") -> str:
    """
    Analyzes the conversation and feedback to update user preference rules.
    """
    conversation_str = _prep_conversation(messages)
    
    formatted_prompt = REFLECTION_PROMPT.format(
        userRules=current_rules,
        conversation=conversation_str
    )
    
    # Use the configured LLM (DeepSeek/OpenAI)
    response = await llm.ainvoke([{"role": "user", "content": formatted_prompt}])
    
    return response.content
