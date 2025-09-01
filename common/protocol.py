from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class MCPPacket(BaseModel):
    """
    Defines the standard message format for communication between agents.
    """
    source_agent: str
    payload_type: str
    data: Dict[str, Any]

    session_id: Optional[str] = None
    trace_id: Optional[str] = None