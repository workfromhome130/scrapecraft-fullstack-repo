"""
Workflow API endpoints for managing pipeline workflows.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from app.services.workflow_manager import get_workflow_manager, WorkflowManager
from app.services.websocket import ConnectionManager
from app.models.workflow import WorkflowPhase


router = APIRouter()


class URLUpdate(BaseModel):
    """URL update request."""
    url: str
    description: Optional[str] = ""
    relevance: Optional[str] = "medium"
    validated: Optional[bool] = False


class SchemaFieldUpdate(BaseModel):
    """Schema field update request."""
    name: str
    type: str
    description: Optional[str] = ""
    required: Optional[bool] = True
    example: Optional[str] = None


class ApprovalRequest(BaseModel):
    """Approval request."""
    approval_id: str
    approved: bool
    reason: Optional[str] = None


def get_manager(connection_manager: ConnectionManager = Depends(lambda: ConnectionManager())) -> WorkflowManager:
    """Dependency to get workflow manager."""
    return get_workflow_manager(connection_manager)


@router.get("/workflow/{pipeline_id}")
async def get_workflow(pipeline_id: str, manager: WorkflowManager = Depends(get_manager)):
    """Get current workflow state."""
    workflow = manager.get_workflow(pipeline_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return workflow.dict()


@router.get("/workflow/{pipeline_id}/summary")
async def get_workflow_summary(pipeline_id: str, manager: WorkflowManager = Depends(get_manager)):
    """Get workflow summary."""
    return manager.get_workflow_summary(pipeline_id)


@router.post("/workflow/{pipeline_id}/urls")
async def update_urls(
    pipeline_id: str,
    urls: List[URLUpdate],
    manager: WorkflowManager = Depends(get_manager)
):
    """Manually update URLs in the workflow."""
    try:
        workflow = await manager.update_urls(
            pipeline_id,
            [url.dict() for url in urls],
            user="user"
        )
        return {
            "success": True,
            "workflow": workflow.dict(),
            "message": f"Updated {len(urls)} URLs"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/{pipeline_id}/schema")
async def update_schema(
    pipeline_id: str,
    schema_fields: List[SchemaFieldUpdate],
    manager: WorkflowManager = Depends(get_manager)
):
    """Manually update schema in the workflow."""
    try:
        workflow = await manager.update_schema(
            pipeline_id,
            [field.dict() for field in schema_fields],
            user="user"
        )
        return {
            "success": True,
            "workflow": workflow.dict(),
            "message": f"Updated schema with {len(schema_fields)} fields"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/{pipeline_id}/approve")
async def approve_action(
    pipeline_id: str,
    request: ApprovalRequest,
    manager: WorkflowManager = Depends(get_manager)
):
    """Approve or reject a workflow action."""
    try:
        workflow = await manager.approve_action(
            pipeline_id,
            request.approval_id,
            request.approved,
            user="user"
        )
        return {
            "success": True,
            "workflow": workflow.dict(),
            "message": f"Action {'approved' if request.approved else 'rejected'}"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workflow/{pipeline_id}/transition")
async def manual_transition(
    pipeline_id: str,
    target_phase: WorkflowPhase,
    reason: Optional[str] = None,
    manager: WorkflowManager = Depends(get_manager)
):
    """Manually transition to a different phase."""
    workflow = manager.get_workflow(pipeline_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    if not workflow.can_transition_to(target_phase):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {workflow.phase} to {target_phase}"
        )
    
    workflow.add_transition(
        target_phase,
        reason or "Manual transition",
        "user"
    )
    
    # Broadcast update
    await manager._broadcast_workflow_update(workflow)
    
    return {
        "success": True,
        "workflow": workflow.dict(),
        "message": f"Transitioned to {target_phase}"
    }


@router.get("/workflow/{pipeline_id}/history")
async def get_workflow_history(
    pipeline_id: str,
    manager: WorkflowManager = Depends(get_manager)
):
    """Get workflow transition history."""
    workflow = manager.get_workflow(pipeline_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    return {
        "transitions": [t.dict() for t in workflow.phase_transitions],
        "modifications": workflow.user_modifications,
        "approvals": [a.dict() for a in workflow.approval_history]
    }


@router.get("/workflow/{pipeline_id}/phase-options")
async def get_phase_options(
    pipeline_id: str,
    manager: WorkflowManager = Depends(get_manager)
):
    """Get available phase transition options."""
    workflow = manager.get_workflow(pipeline_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Get all possible phases
    all_phases = list(WorkflowPhase)
    
    # Filter to allowed transitions
    allowed_phases = [
        phase for phase in all_phases 
        if workflow.can_transition_to(phase)
    ]
    
    return {
        "current_phase": workflow.phase,
        "allowed_transitions": allowed_phases,
        "all_phases": all_phases
    }