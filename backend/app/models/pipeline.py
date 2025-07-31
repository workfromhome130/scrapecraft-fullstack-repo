from pydantic import BaseModel, HttpUrl
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class PipelineStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Pipeline(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    urls: List[str] = []
    schema: Dict[str, Any] = {}
    code: str = ""
    status: PipelineStatus = PipelineStatus.IDLE
    created_at: datetime
    updated_at: datetime
    user_id: Optional[str] = None
    results_count: int = 0
    last_run: Optional[datetime] = None

class PipelineCreate(BaseModel):
    name: str
    description: Optional[str] = None
    urls: Optional[List[HttpUrl]] = None
    schema: Optional[Dict[str, Any]] = None

class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    urls: Optional[List[str]] = None
    schema: Optional[Dict[str, Any]] = None
    code: Optional[str] = None

class PipelineExecution(BaseModel):
    id: str
    pipeline_id: str
    status: PipelineStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_urls: int
    successful_urls: int = 0
    failed_urls: int = 0
    error_message: Optional[str] = None