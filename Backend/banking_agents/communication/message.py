from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from banking_agents.communication.intent import Intent

class UserQuery(BaseModel):
    query: str
    session_id: str

class AgentContext(BaseModel):
    session_id: str
    history: List[Dict[str, str]] = Field(default_factory=list)
    extracted_entities: Dict[str, Any] = Field(default_factory=dict)
    current_intent: Optional[Intent] = None

class AgentResponse(BaseModel):
    response: str
    context: AgentContext
