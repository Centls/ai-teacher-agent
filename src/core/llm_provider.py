from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from config.settings import settings
from .audit import audit_logger

class LLMProvider(ABC):
    @abstractmethod
    def invoke(self, template: str, context: Dict[str, Any], output_parser=None) -> Any:
        pass

class RealLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.llm = ChatOpenAI(api_key=api_key, model=model, temperature=0.7)

    def invoke(self, template: str, context: Dict[str, Any], output_parser=None) -> Any:
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm
        if output_parser:
            chain = chain | output_parser
        return chain.invoke(context)

class MockLLMProvider(LLMProvider):
    def invoke(self, template: str, context: Dict[str, Any], output_parser=None) -> Any:
        # Simple heuristic to determine what to return based on context keys or template content
        # In a real system, this could be more sophisticated or load from a mock data file.
        
        # Simple heuristic to determine what to return based on context keys or template content
        # In a real system, this could be more sophisticated or load from a mock data file.
        
        print(f"[MockLLM] Invoked with context keys: {list(context.keys())}")
        
        # Marketing Plan Mock
        if "Strategic Marketing Planner" in template:
             # Check for B2B constraints
             constraints = context.get("prd_constraints", {})
             # Handle both dict (YAML) and parsed markdown (dict of lists)
             if isinstance(constraints, dict):
                 tone = constraints.get("constraints", {}).get("tone", "")
                 # Also check markdown structure just in case
                 if not tone and "1._product_definition" in constraints:
                     tone = str(constraints.get("1._product_definition", []))
             else:
                 tone = str(constraints)
                 
             is_b2b = "ROI-Focused" in tone or "Professional" in tone
             
             # Medical/Compliance Check (Mock)
             user_request = context.get("user_request", "").lower()
             if "cure" in user_request or "hypertension" in user_request or "diabetes" in user_request or "medical" in user_request:
                 return {
                    "target_audience": "REFUSE_ME",
                    "product_description": "Medical Claim Detected",
                    "marketing_goal": "REFUSE_ME"
                 }

             if is_b2b:
                 return {
                    "target_audience": "CTOs and CIOs (Mock B2B)",
                    "product_description": "Enterprise AI Platform (Mock B2B)",
                    "marketing_goal": "Lead Generation"
                 }
             elif "TCM" in tone or "ZenPulse" in tone or "Wellness" in tone:
                 return {
                    "target_audience": "Health-conscious Elderly & Punk Health Youth (Mock TCM)",
                    "product_description": "ZenPulse Smartwatch (Mock TCM)",
                    "marketing_goal": "Community Building"
                 }
             else:
                 return {
                    "target_audience": "Young urban professionals (Mock)",
                    "product_description": "Premium Coffee (Mock)",
                    "marketing_goal": "Brand Awareness"
                 }
        
        # Support Mock
        if "You are a support agent" in template:
            return {
                "answer": "Yes, we support refunds within 30 days. (Mock Answer)",
                "issue_category": "Refund Policy",
                "solution": "Check our terms of service."
            }

        # Marketing Execute Mock
        if "channel_strategy" in template or "core_positioning" in template:
             # Check for B2B constraints in context
             constraints = context.get("prd_constraints", {})
             # Debug print to see what constraints look like
             print(f"[DEBUG] PRD Constraints: {constraints}")
             
             # More robust check: Check for specific tone or target audience
             tone = constraints.get("constraints", {}).get("tone", "")
             # Also check markdown structure just in case
             if not tone and "1._product_definition" in constraints:
                 tone = str(constraints.get("1._product_definition", []))
             elif not tone and isinstance(constraints, str):
                 tone = constraints

             is_b2b = "ROI-Focused" in tone or "Professional" in tone
             is_tcm = "TCM" in tone or "ZenPulse" in tone or "Wellness" in tone
             
             if is_b2b:
                 return {
                    "core_positioning": "Enterprise AI Governance (Mock B2B)",
                    "channel_strategy": {
                        "LinkedIn": "Thought Leadership Articles (Mock)",
                        "Email": "Drip Campaign for CTOs (Mock)",
                        "Webinars": "Quarterly Tech Talks (Mock)"
                    },
                    "content_plan": [
                        {"channel": "LinkedIn", "content": "Maximizing ROI with AI Governance. #EnterpriseTech (PRD Compliant)"},
                        {"channel": "Email", "content": "Subject: Reducing Compliance Risk in 2025 (PRD Compliant)"}
                    ]
                 }
             elif is_tcm:
                 return {
                    "core_positioning": "Traditional Wisdom, Modern Monitoring (Mock TCM)",
                    "channel_strategy": {
                        "WeChat": "Family Health Tips (Mock)",
                        "RedNote": "New Chinese Style Aesthetics (Mock)",
                        "Community": "Morning Tai Chi Groups (Mock)"
                    },
                    "content_plan": [
                        {"channel": "WeChat", "content": "🌿 Solar Term Alert: Eat these 3 foods today! #ZenPulse (PRD Compliant)"},
                        {"channel": "RedNote", "content": "⌚ My Pulse says I need more sleep... #PunkHealth (PRD Compliant)"}
                    ]
                 }
             else:
                 return {
                    "core_positioning": "Fuel your ambition (Mock)",
                    "channel_strategy": {
                        "WeChat": "Daily stories (Mock)",
                        "RedNote": "Aesthetic photos (Mock)",
                        "TikTok": "Making-of videos (Mock)",
                        "LiveStream": "Q&A (Mock)"
                    },
                    "content_plan": [
                        {"channel": "RedNote", "content": "✨ Morning Vibes! ☕ #CoffeeLover (PRD Compliant)"},
                        {"channel": "TikTok", "content": "[Sound: Jazz] Pouring latte art... (PRD Compliant)"}
                    ]
                }
            
        # Marketing Review Mock
        if "quality_score" in template:
             # Simulate Low Quality / Refusal based on context
             # For demo, if marketing plan contains "REFUSE_ME", return low score
             # Note: context["marketing_plan"] is a JSON string in the real node
             marketing_plan = context.get("marketing_plan", "")
             
             # Also check user request if available in context, or just rely on plan content
             # In review_node, we only pass marketing_plan and prd_constraints
             
             if "REFUSE_ME" in marketing_plan or "REFUSE_ME" in str(context):
                 return {
                    "quality_score": 40,
                    "feedback": "Violates safety guidelines (Mock Refusal).",
                    "status": "REFUSED"
                 }
             elif "PARTIAL_ME" in marketing_plan or "PARTIAL_ME" in str(context):
                 return {
                    "quality_score": 70,
                    "feedback": "Missing key details (Mock Partial).",
                    "status": "PARTIAL_SUCCESS"
                 }
                 
             return {
                "quality_score": 95,
                "feedback": "Perfect compliance with PRD standards. (Mock)",
                "status": "SUCCESS"
            }
            
        return {}

def get_llm_provider() -> LLMProvider:
    api_key = settings.OPENAI_API_KEY
    # Simple check: if key is placeholder or empty, use Mock
    if not api_key or "placeholder" in api_key or api_key.strip() == "":
        print(">>> Using MockLLMProvider (No valid API Key detected) <<<")
        return MockLLMProvider()
    
    return RealLLMProvider(api_key, settings.DEFAULT_MODEL)
