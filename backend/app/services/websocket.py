from fastapi import WebSocket
from typing import Dict, List, Any
import json
import asyncio
from datetime import datetime

class ConnectionManager:
    """Manages WebSocket connections for real-time communication."""
    
    def __init__(self):
        # Store active connections by pipeline_id
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Store pipeline states
        self.pipeline_states: Dict[str, Dict] = {}
    
    async def connect(self, websocket: WebSocket, pipeline_id: str):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        
        if pipeline_id not in self.active_connections:
            self.active_connections[pipeline_id] = []
            self.pipeline_states[pipeline_id] = {
                "urls": [],
                "schema": {},
                "generated_code": "",
                "status": "connected"
            }
        
        self.active_connections[pipeline_id].append(websocket)
        
        # Send initial state
        await self.send_personal_message({
            "type": "connection",
            "message": "Connected to pipeline",
            "pipeline_id": pipeline_id,
            "state": self.pipeline_states[pipeline_id]
        }, websocket)
    
    def disconnect(self, websocket: WebSocket, pipeline_id: str):
        """Remove a WebSocket connection."""
        if pipeline_id in self.active_connections:
            self.active_connections[pipeline_id].remove(websocket)
            
            # Clean up if no more connections
            if not self.active_connections[pipeline_id]:
                del self.active_connections[pipeline_id]
    
    async def send_personal_message(self, message: Dict, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        await websocket.send_json({
            **message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def broadcast(self, message: Dict, pipeline_id: str):
        """Broadcast a message to all connections for a pipeline."""
        if pipeline_id in self.active_connections:
            # Create tasks for all connections
            tasks = []
            for connection in self.active_connections[pipeline_id]:
                tasks.append(connection.send_json({
                    **message,
                    "timestamp": datetime.utcnow().isoformat()
                }))
            
            # Send to all connections concurrently
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def process_message(self, pipeline_id: str, data: Dict) -> Dict:
        """Process incoming WebSocket messages."""
        message_type = data.get("type", "chat")
        
        if message_type == "chat":
            # Process through the workflow manager
            from app.services.workflow_manager import get_workflow_manager
            
            workflow_manager = get_workflow_manager(self)
            result = await workflow_manager.process_message(
                pipeline_id=pipeline_id,
                message=data.get("message", ""),
                user=data.get("user", "user")
            )
            
            return {
                "type": "response",
                "response": result["response"],
                "workflow_state": result["workflow_state"],
                "requires_action": result["requires_action"]
            }
        
        elif message_type == "state_request":
            # Return current workflow state
            from app.services.workflow_manager import get_workflow_manager
            
            workflow_manager = get_workflow_manager(self)
            workflow = workflow_manager.get_workflow(pipeline_id)
            
            if workflow:
                return {
                    "type": "workflow_state",
                    "workflow": workflow.model_dump(mode='json')
                }
            else:
                # Create initial workflow for new pipelines
                workflow = workflow_manager.create_workflow(pipeline_id, data.get("user", "user"))
                return {
                    "type": "workflow_state",
                    "workflow": workflow.model_dump(mode='json')
                }
        
        elif message_type == "approval":
            # Handle approval response
            from app.services.workflow_manager import get_workflow_manager
            
            workflow_manager = get_workflow_manager(self)
            workflow = await workflow_manager.approve_action(
                pipeline_id=pipeline_id,
                approval_id=data.get("approval_id"),
                approved=data.get("approved", False),
                user=data.get("user", "user")
            )
            
            return {
                "type": "approval_processed",
                "workflow": workflow.model_dump(mode='json')
            }
        
        elif message_type == "ping":
            # Health check
            return {"type": "pong"}
        
        else:
            return {
                "type": "error",
                "message": f"Unknown message type: {message_type}"
            }
    
    async def stream_execution_updates(
        self,
        pipeline_id: str,
        url: str,
        status: str,
        data: Any = None,
        error: str = None
    ):
        """Stream execution updates to connected clients."""
        await self.broadcast({
            "type": "execution_update",
            "url": url,
            "status": status,
            "data": data,
            "error": error
        }, pipeline_id)