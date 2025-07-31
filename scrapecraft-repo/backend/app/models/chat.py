from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ChatMessage(BaseModel):
    id: Optional[str] = None
    role: MessageRole
    content: str
    timestamp: datetime = datetime.utcnow()
    metadata: Optional[Dict] = None

class ChatResponse(BaseModel):
    message: ChatMessage
    pipeline_state: Optional[Dict] = None
    tools_used: Optional[List[str]] = None
    execution_time: Optional[float] = None

class ConversationHistory(BaseModel):
    pipeline_id: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict] = None