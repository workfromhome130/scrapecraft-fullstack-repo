from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime

from app.agents.openrouter_agent import openrouter_agent
from app.models.chat import ChatMessage, ChatResponse
from app.services.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

class MessageRequest(BaseModel):
    message: str
    pipeline_id: str
    context: Optional[Dict] = None

class MessageResponse(BaseModel):
    response: str
    urls: List[str]
    schema: Dict
    code: Optional[str]
    results: List[Dict]
    status: str
    timestamp: datetime

@router.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """Send a message to the scraping agent and get a response."""
    try:
        result = await openrouter_agent.process_message(
            message=request.message,
            pipeline_id=request.pipeline_id,
            context=request.context
        )
        
        return MessageResponse(
            response=result["response"],
            urls=result["urls"],
            schema=result["schema"],
            code=result.get("code"),
            results=result.get("results", []),
            status=result["status"],
            timestamp=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{pipeline_id}")
async def get_chat_history(pipeline_id: str, limit: int = 50):
    """Get chat history for a specific pipeline."""
    # TODO: Implement database query
    return {
        "pipeline_id": pipeline_id,
        "messages": [],
        "total": 0
    }

@router.delete("/history/{pipeline_id}")
async def clear_chat_history(pipeline_id: str):
    """Clear chat history for a specific pipeline."""
    # TODO: Implement database deletion
    return {"message": "Chat history cleared successfully"}

@router.post("/feedback")
async def submit_feedback(
    pipeline_id: str,
    message_id: str,
    feedback: str,
    rating: Optional[int] = None
):
    """Submit feedback for a specific message."""
    # TODO: Store feedback in database
    return {"message": "Feedback submitted successfully"}