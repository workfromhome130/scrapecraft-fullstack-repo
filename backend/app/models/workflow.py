"""
Workflow models for state management.
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class WorkflowPhase(str, Enum):
    """Workflow phases for the scraping pipeline."""
    INITIAL = "initial"
    URL_COLLECTION = "url_collection"
    URL_VALIDATION = "url_validation"
    SCHEMA_DEFINITION = "schema_definition"
    SCHEMA_VALIDATION = "schema_validation"
    CODE_GENERATION = "code_generation"
    READY_TO_EXECUTE = "ready_to_execute"
    EXECUTING = "executing"
    COMPLETED = "completed"
    ERROR = "error"


class WorkflowTransition(BaseModel):
    """Represents a transition between workflow phases."""
    from_phase: WorkflowPhase
    to_phase: WorkflowPhase
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    reason: Optional[str] = None
    triggered_by: str = "system"  # system, user, or agent


class URLInfo(BaseModel):
    """Information about a URL in the pipeline."""
    url: str
    description: str = ""
    relevance: str = "medium"  # high, medium, low
    validated: bool = False
    validation_reason: Optional[str] = None
    added_at: datetime = Field(default_factory=datetime.utcnow)
    added_by: str = "agent"  # agent or user


class SchemaField(BaseModel):
    """Schema field definition."""
    name: str
    type: str
    description: str
    required: bool = True
    example: Optional[str] = None
    validation_rules: Optional[Dict[str, Any]] = None


class ApprovalRequest(BaseModel):
    """Request for user approval."""
    id: str
    phase: WorkflowPhase
    action: str  # e.g., "validate_urls", "approve_schema", "execute_code"
    data: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    status: str = "pending"  # pending, approved, rejected, expired


class WorkflowState(BaseModel):
    """Complete workflow state."""
    pipeline_id: str
    phase: WorkflowPhase = WorkflowPhase.INITIAL
    
    # URLs
    urls: List[URLInfo] = []
    urls_validated: bool = False
    
    # Schema
    schema_fields: List[SchemaField] = []
    schema_validated: bool = False
    
    # Code
    generated_code: str = ""
    code_validated: bool = False
    
    # Execution
    execution_results: List[Dict[str, Any]] = []
    execution_status: Optional[str] = None
    
    # Approval tracking
    pending_approvals: List[ApprovalRequest] = []
    approval_history: List[ApprovalRequest] = []
    
    # Workflow history
    phase_transitions: List[WorkflowTransition] = []
    
    # User modifications
    user_modifications: List[Dict[str, Any]] = []
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Metadata
    created_by: str = "system"
    last_modified_by: str = "system"
    version: int = 1
    
    def add_transition(self, to_phase: WorkflowPhase, reason: str = "", triggered_by: str = "system"):
        """Add a phase transition to history."""
        transition = WorkflowTransition(
            from_phase=self.phase,
            to_phase=to_phase,
            reason=reason,
            triggered_by=triggered_by
        )
        self.phase_transitions.append(transition)
        self.phase = to_phase
        self.updated_at = datetime.utcnow()
        self.last_modified_by = triggered_by
        
    def add_user_modification(self, field: str, old_value: Any, new_value: Any, user: str = "user"):
        """Track user modifications."""
        modification = {
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "timestamp": datetime.utcnow(),
            "user": user
        }
        self.user_modifications.append(modification)
        self.updated_at = datetime.utcnow()
        self.last_modified_by = user
        self.version += 1
    
    def create_approval_request(self, action: str, data: Dict[str, Any]) -> ApprovalRequest:
        """Create an approval request."""
        import uuid
        approval = ApprovalRequest(
            id=str(uuid.uuid4()),
            phase=self.phase,
            action=action,
            data=data
        )
        self.pending_approvals.append(approval)
        return approval
    
    def process_approval(self, approval_id: str, status: str, user: str = "user"):
        """Process an approval request."""
        for approval in self.pending_approvals:
            if approval.id == approval_id:
                approval.status = status
                self.pending_approvals.remove(approval)
                self.approval_history.append(approval)
                self.last_modified_by = user
                break
    
    def get_phase_progress(self) -> float:
        """Get progress percentage based on current phase."""
        phase_weights = {
            WorkflowPhase.INITIAL: 0.0,
            WorkflowPhase.URL_COLLECTION: 0.15,
            WorkflowPhase.URL_VALIDATION: 0.25,
            WorkflowPhase.SCHEMA_DEFINITION: 0.40,
            WorkflowPhase.SCHEMA_VALIDATION: 0.50,
            WorkflowPhase.CODE_GENERATION: 0.70,
            WorkflowPhase.READY_TO_EXECUTE: 0.85,
            WorkflowPhase.EXECUTING: 0.90,
            WorkflowPhase.COMPLETED: 1.0,
            WorkflowPhase.ERROR: -1.0
        }
        return phase_weights.get(self.phase, 0.0)
    
    def can_transition_to(self, target_phase: WorkflowPhase) -> bool:
        """Check if transition to target phase is allowed."""
        allowed_transitions = {
            WorkflowPhase.INITIAL: [WorkflowPhase.URL_COLLECTION],
            WorkflowPhase.URL_COLLECTION: [WorkflowPhase.URL_VALIDATION, WorkflowPhase.ERROR],
            WorkflowPhase.URL_VALIDATION: [WorkflowPhase.SCHEMA_DEFINITION, WorkflowPhase.URL_COLLECTION, WorkflowPhase.ERROR],
            WorkflowPhase.SCHEMA_DEFINITION: [WorkflowPhase.SCHEMA_VALIDATION, WorkflowPhase.ERROR],
            WorkflowPhase.SCHEMA_VALIDATION: [WorkflowPhase.CODE_GENERATION, WorkflowPhase.SCHEMA_DEFINITION, WorkflowPhase.ERROR],
            WorkflowPhase.CODE_GENERATION: [WorkflowPhase.READY_TO_EXECUTE, WorkflowPhase.ERROR],
            WorkflowPhase.READY_TO_EXECUTE: [WorkflowPhase.EXECUTING, WorkflowPhase.CODE_GENERATION, WorkflowPhase.ERROR],
            WorkflowPhase.EXECUTING: [WorkflowPhase.COMPLETED, WorkflowPhase.ERROR],
            WorkflowPhase.COMPLETED: [WorkflowPhase.INITIAL],  # Can restart
            WorkflowPhase.ERROR: [WorkflowPhase.INITIAL]  # Can restart
        }
        
        return target_phase in allowed_transitions.get(self.phase, [])
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }