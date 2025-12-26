from typing import TypedDict, List, Optional

class CapabilitySchema(TypedDict):
    """
    Structured declaration of a Teacher's capabilities.
    """
    name: str
    description: str
    supported_tasks: List[str]
    required_inputs: List[str]
    forbidden_outputs: List[str]
    supports_multimodal: bool
    degradation_modes: List[str]
    input_schema: Optional[dict]
    output_schema: Optional[dict]
