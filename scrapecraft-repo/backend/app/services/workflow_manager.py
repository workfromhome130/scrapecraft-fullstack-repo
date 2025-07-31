"""
Workflow manager service for coordinating agent states and frontend interactions.
"""
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime, timedelta
import json

from app.models.workflow import (
    WorkflowState, WorkflowPhase, URLInfo, SchemaField, 
    ApprovalRequest, WorkflowTransition
)
from app.agents.langgraph_agent import ScrapeCraftAgent
from app.services.websocket import ConnectionManager


class WorkflowManager:
    """Manages workflow states and coordinates between agent and frontend."""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.workflows: Dict[str, WorkflowState] = {}
        self.agent = ScrapeCraftAgent()
        self.connection_manager = connection_manager
        self.approval_callbacks: Dict[str, asyncio.Event] = {}
        
    def get_workflow(self, pipeline_id: str) -> Optional[WorkflowState]:
        """Get workflow state for a pipeline."""
        return self.workflows.get(pipeline_id)
    
    def create_workflow(self, pipeline_id: str, user: str = "system") -> WorkflowState:
        """Create a new workflow state."""
        workflow = WorkflowState(
            pipeline_id=pipeline_id,
            created_by=user
        )
        self.workflows[pipeline_id] = workflow
        return workflow
    
    async def process_message(
        self, 
        pipeline_id: str, 
        message: str, 
        user: str = "user"
    ) -> Dict[str, Any]:
        """Process a message through the workflow."""
        # Get or create workflow
        workflow = self.get_workflow(pipeline_id) or self.create_workflow(pipeline_id, user)
        
        # Process through agent
        result = await self.agent.process_message(message, pipeline_id)
        
        # Update workflow state based on result
        await self._update_workflow_from_result(workflow, result)
        
        # Broadcast state update
        await self._broadcast_workflow_update(workflow)
        
        return {
            "response": result["response"],
            "workflow_state": workflow.model_dump(mode='json'),
            "requires_action": len(workflow.pending_approvals) > 0
        }
    
    async def update_urls(
        self, 
        pipeline_id: str, 
        urls: List[Dict[str, Any]], 
        user: str = "user"
    ) -> WorkflowState:
        """Manually update URLs in the workflow."""
        workflow = self.get_workflow(pipeline_id)
        if not workflow:
            raise ValueError(f"Workflow not found for pipeline {pipeline_id}")
        
        # Track modification
        old_urls = [url.dict() for url in workflow.urls]
        
        # Update URLs
        workflow.urls = []
        for url_data in urls:
            url_info = URLInfo(
                url=url_data["url"],
                description=url_data.get("description", ""),
                relevance=url_data.get("relevance", "medium"),
                validated=url_data.get("validated", False),
                added_by=user
            )
            workflow.urls.append(url_info)
        
        workflow.add_user_modification("urls", old_urls, urls, user)
        
        # Update phase if needed
        if workflow.phase == WorkflowPhase.URL_COLLECTION:
            workflow.add_transition(
                WorkflowPhase.URL_VALIDATION,
                "URLs manually updated",
                user
            )
        
        await self._broadcast_workflow_update(workflow)
        return workflow
    
    async def update_schema(
        self, 
        pipeline_id: str, 
        schema_fields: List[Dict[str, Any]], 
        user: str = "user"
    ) -> WorkflowState:
        """Manually update schema in the workflow."""
        workflow = self.get_workflow(pipeline_id)
        if not workflow:
            raise ValueError(f"Workflow not found for pipeline {pipeline_id}")
        
        # Track modification
        old_schema = [field.dict() for field in workflow.schema_fields]
        
        # Update schema
        workflow.schema_fields = []
        for field_data in schema_fields:
            schema_field = SchemaField(
                name=field_data["name"],
                type=field_data["type"],
                description=field_data.get("description", ""),
                required=field_data.get("required", True),
                example=field_data.get("example")
            )
            workflow.schema_fields.append(schema_field)
        
        workflow.add_user_modification("schema_fields", old_schema, schema_fields, user)
        
        # Update phase if needed
        if workflow.phase in [WorkflowPhase.SCHEMA_DEFINITION, WorkflowPhase.SCHEMA_VALIDATION]:
            workflow.schema_validated = True
            workflow.add_transition(
                WorkflowPhase.CODE_GENERATION,
                "Schema manually updated",
                user
            )
        
        await self._broadcast_workflow_update(workflow)
        return workflow
    
    async def approve_action(
        self, 
        pipeline_id: str, 
        approval_id: str, 
        approved: bool, 
        user: str = "user"
    ) -> WorkflowState:
        """Process an approval request."""
        workflow = self.get_workflow(pipeline_id)
        if not workflow:
            raise ValueError(f"Workflow not found for pipeline {pipeline_id}")
        
        # Process approval
        status = "approved" if approved else "rejected"
        workflow.process_approval(approval_id, status, user)
        
        # Trigger approval callback if waiting
        callback_key = f"{pipeline_id}:{approval_id}"
        if callback_key in self.approval_callbacks:
            self.approval_callbacks[callback_key].set()
        
        # Update workflow based on approval
        if approved:
            # Continue to next phase
            next_phase = self._get_next_phase(workflow.phase)
            if next_phase:
                workflow.add_transition(
                    next_phase,
                    f"Approved by {user}",
                    user
                )
        else:
            # May need to go back or handle rejection
            if workflow.phase == WorkflowPhase.URL_VALIDATION:
                workflow.add_transition(
                    WorkflowPhase.URL_COLLECTION,
                    f"Rejected by {user}, collecting new URLs",
                    user
                )
        
        await self._broadcast_workflow_update(workflow)
        return workflow
    
    async def request_approval(
        self, 
        workflow: WorkflowState, 
        action: str, 
        data: Dict[str, Any],
        timeout: int = 300  # 5 minutes default
    ) -> bool:
        """Request user approval and wait for response."""
        approval = workflow.create_approval_request(action, data)
        
        # Set up callback
        callback_key = f"{workflow.pipeline_id}:{approval.id}"
        self.approval_callbacks[callback_key] = asyncio.Event()
        
        # Broadcast approval request
        await self.connection_manager.broadcast({
            "type": "approval_request",
            "approval": approval.model_dump(mode='json'),
            "workflow_phase": workflow.phase.value
        }, workflow.pipeline_id)
        
        try:
            # Wait for approval with timeout
            await asyncio.wait_for(
                self.approval_callbacks[callback_key].wait(),
                timeout=timeout
            )
            
            # Check approval status
            for approval_record in workflow.approval_history:
                if approval_record.id == approval.id:
                    return approval_record.status == "approved"
                    
        except asyncio.TimeoutError:
            # Mark as expired
            workflow.process_approval(approval.id, "expired", "system")
            
        finally:
            # Clean up callback
            del self.approval_callbacks[callback_key]
            
        return False
    
    def _get_next_phase(self, current_phase: WorkflowPhase) -> Optional[WorkflowPhase]:
        """Get the next logical phase in the workflow."""
        next_phases = {
            WorkflowPhase.INITIAL: WorkflowPhase.URL_COLLECTION,
            WorkflowPhase.URL_COLLECTION: WorkflowPhase.URL_VALIDATION,
            WorkflowPhase.URL_VALIDATION: WorkflowPhase.SCHEMA_DEFINITION,
            WorkflowPhase.SCHEMA_DEFINITION: WorkflowPhase.SCHEMA_VALIDATION,
            WorkflowPhase.SCHEMA_VALIDATION: WorkflowPhase.CODE_GENERATION,
            WorkflowPhase.CODE_GENERATION: WorkflowPhase.READY_TO_EXECUTE,
            WorkflowPhase.READY_TO_EXECUTE: WorkflowPhase.EXECUTING,
            WorkflowPhase.EXECUTING: WorkflowPhase.COMPLETED
        }
        return next_phases.get(current_phase)
    
    async def _update_workflow_from_result(
        self, 
        workflow: WorkflowState, 
        result: Dict[str, Any]
    ):
        """Update workflow state from agent result."""
        # Update phase
        new_phase = WorkflowPhase(result["phase"])
        if new_phase != workflow.phase:
            workflow.add_transition(
                new_phase,
                "Agent processing",
                "agent"
            )
        
        # Update URLs
        if result.get("urls"):
            workflow.urls = []
            for url_data in result["urls"]:
                workflow.urls.append(URLInfo(**url_data))
            workflow.urls_validated = all(url.validated for url in workflow.urls)
        
        # Update schema
        if result.get("schema"):
            workflow.schema_fields = []
            for field_name, field_type in result["schema"].items():
                workflow.schema_fields.append(SchemaField(
                    name=field_name,
                    type=field_type,
                    description=f"Field for {field_name}"
                ))
            workflow.schema_validated = len(workflow.schema_fields) > 0
        
        # Update code
        if result.get("code"):
            workflow.generated_code = result["code"]
            workflow.code_validated = False  # Requires approval
        
        # Update results
        if result.get("results"):
            workflow.execution_results = result["results"]
        
        # Handle errors
        if result.get("errors"):
            for error in result["errors"]:
                workflow.phase_transitions.append(WorkflowTransition(
                    from_phase=workflow.phase,
                    to_phase=workflow.phase,
                    reason=f"Error: {error}",
                    triggered_by="agent"
                ))
    
    async def _broadcast_workflow_update(self, workflow: WorkflowState):
        """Broadcast workflow state update to connected clients."""
        await self.connection_manager.broadcast({
            "type": "workflow_update",
            "workflow": workflow.model_dump(mode='json'),
            "progress": workflow.get_phase_progress()
        }, workflow.pipeline_id)
    
    def get_workflow_summary(self, pipeline_id: str) -> Dict[str, Any]:
        """Get a summary of the workflow state."""
        workflow = self.get_workflow(pipeline_id)
        if not workflow:
            return {"error": "Workflow not found"}
        
        return {
            "pipeline_id": pipeline_id,
            "current_phase": workflow.phase.value,
            "progress": workflow.get_phase_progress(),
            "urls_count": len(workflow.urls),
            "schema_fields_count": len(workflow.schema_fields),
            "has_code": bool(workflow.generated_code),
            "pending_approvals": len(workflow.pending_approvals),
            "last_updated": workflow.updated_at.isoformat(),
            "can_execute": workflow.phase == WorkflowPhase.READY_TO_EXECUTE
        }


# Singleton instance
workflow_manager = None

def get_workflow_manager(connection_manager: ConnectionManager) -> WorkflowManager:
    """Get or create workflow manager instance."""
    global workflow_manager
    if workflow_manager is None:
        workflow_manager = WorkflowManager(connection_manager)
    return workflow_manager