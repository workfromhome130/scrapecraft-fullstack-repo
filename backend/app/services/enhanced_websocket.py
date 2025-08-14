"""
Enhanced WebSocket Manager
Provides real-time streaming, progress updates, and collaborative features.
"""
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List, Any, Optional, Set
import json
import asyncio
from datetime import datetime
from enum import Enum
import uuid


class MessageType(str, Enum):
    """WebSocket message types."""
    # Core messages
    CONNECTION = "connection"
    CHAT = "chat"
    RESPONSE = "response"
    
    # Progress updates
    SCRAPING_PROGRESS = "scraping_progress"
    EXECUTION_UPDATE = "execution_update"
    
    # Suggestions and AI
    SUGGESTION = "suggestion"
    PATTERN_DETECTED = "pattern_detected"
    OPTIMIZATION_SUGGESTED = "optimization_suggested"
    
    # Collaboration
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    PIPELINE_UPDATED = "pipeline_updated"
    
    # System
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PING = "ping"
    PONG = "pong"


class StreamingResponse:
    """Helper for streaming responses."""
    
    def __init__(self, websocket: WebSocket, message_id: str):
        self.websocket = websocket
        self.message_id = message_id
        self.chunks = []
        self.start_time = datetime.utcnow()
    
    async def send_chunk(self, chunk: str):
        """Send a chunk of the response."""
        self.chunks.append(chunk)
        await self.websocket.send_json({
            "type": MessageType.RESPONSE,
            "message_id": self.message_id,
            "chunk": chunk,
            "is_streaming": True,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def finish(self):
        """Finish streaming and send complete response."""
        complete_response = "".join(self.chunks)
        duration = (datetime.utcnow() - self.start_time).total_seconds()
        
        await self.websocket.send_json({
            "type": MessageType.RESPONSE,
            "message_id": self.message_id,
            "content": complete_response,
            "is_streaming": True,  # Keep as streaming to avoid duplicate handling
            "is_complete": True,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat()
        })


class EnhancedWebSocketManager:
    """Enhanced WebSocket manager with streaming and collaboration features."""
    
    def __init__(self):
        # Connection management
        self.connections: Dict[str, Dict[str, WebSocket]] = {}  # pipeline_id -> {user_id: websocket}
        self.user_info: Dict[str, Dict] = {}  # user_id -> user info
        
        # Pipeline states
        self.pipeline_states: Dict[str, Dict] = {}
        self.pipeline_locks: Dict[str, str] = {}  # pipeline_id -> user_id (who has edit lock)
        
        # Streaming management
        self.active_streams: Dict[str, StreamingResponse] = {}
        
        # Auto-save drafts
        self.draft_timers: Dict[str, asyncio.Task] = {}
    
    async def connect(
        self,
        websocket: WebSocket,
        pipeline_id: str,
        user_id: Optional[str] = None
    ):
        """Accept and manage a WebSocket connection."""
        await websocket.accept()
        
        # Generate user ID if not provided
        if not user_id:
            user_id = str(uuid.uuid4())[:8]
        
        # Initialize pipeline connections
        if pipeline_id not in self.connections:
            self.connections[pipeline_id] = {}
            self.pipeline_states[pipeline_id] = {
                "urls": [],
                "schema": {},
                "code": "",
                "status": "idle",
                "collaborators": []
            }
        
        # Add connection
        self.connections[pipeline_id][user_id] = websocket
        
        # Store user info
        self.user_info[user_id] = {
            "id": user_id,
            "pipeline_id": pipeline_id,
            "connected_at": datetime.utcnow().isoformat(),
            "is_editing": False
        }
        
        # Update collaborators
        self.pipeline_states[pipeline_id]["collaborators"].append(user_id)
        
        # Send connection confirmation
        await websocket.send_json({
            "type": MessageType.CONNECTION,
            "status": "connected",
            "user_id": user_id,
            "pipeline_id": pipeline_id,
            "state": self.pipeline_states[pipeline_id],
            "collaborators": list(self.connections[pipeline_id].keys()),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Notify other users
        await self.broadcast_to_others(
            pipeline_id,
            user_id,
            {
                "type": MessageType.USER_JOINED,
                "user_id": user_id,
                "total_users": len(self.connections[pipeline_id])
            }
        )
    
    def disconnect(self, websocket: WebSocket, pipeline_id: str, user_id: str):
        """Remove a WebSocket connection."""
        if pipeline_id in self.connections:
            if user_id in self.connections[pipeline_id]:
                del self.connections[pipeline_id][user_id]
            
            # Update collaborators
            if user_id in self.pipeline_states[pipeline_id]["collaborators"]:
                self.pipeline_states[pipeline_id]["collaborators"].remove(user_id)
            
            # Release edit lock if held by this user
            if self.pipeline_locks.get(pipeline_id) == user_id:
                del self.pipeline_locks[pipeline_id]
            
            # Cancel auto-save timer if exists
            if user_id in self.draft_timers:
                self.draft_timers[user_id].cancel()
                del self.draft_timers[user_id]
            
            # Clean up if no more connections
            if not self.connections[pipeline_id]:
                del self.connections[pipeline_id]
                if pipeline_id in self.pipeline_states:
                    del self.pipeline_states[pipeline_id]
        
        # Remove user info
        if user_id in self.user_info:
            del self.user_info[user_id]
    
    async def broadcast(self, pipeline_id: str, message: Dict):
        """Broadcast message to all connections for a pipeline."""
        if pipeline_id not in self.connections:
            return
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        
        # Send to all connected users
        tasks = []
        for user_id, websocket in self.connections[pipeline_id].items():
            tasks.append(self._send_safe(websocket, message))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def broadcast_to_others(
        self,
        pipeline_id: str,
        sender_id: str,
        message: Dict
    ):
        """Broadcast message to all connections except sender."""
        if pipeline_id not in self.connections:
            return
        
        message["timestamp"] = datetime.utcnow().isoformat()
        
        tasks = []
        for user_id, websocket in self.connections[pipeline_id].items():
            if user_id != sender_id:
                tasks.append(self._send_safe(websocket, message))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _send_safe(self, websocket: WebSocket, message: Dict):
        """Safely send message to websocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            print(f"Error sending message: {e}")
    
    async def stream_scraping_progress(
        self,
        pipeline_id: str,
        progress: Dict
    ):
        """Stream real-time scraping progress with preview."""
        message = {
            "type": MessageType.SCRAPING_PROGRESS,
            "pipeline_id": pipeline_id,
            "current_url": progress.get("current_url"),
            "current_index": progress.get("current_index", 0),
            "total_urls": progress.get("total", 0),
            "percent_complete": (
                (progress.get("completed", 0) / progress.get("total", 1)) * 100
                if progress.get("total", 0) > 0 else 0
            ),
            "status": progress.get("status", "processing"),
            "extracted_data_preview": progress.get("preview"),
            "estimated_time_remaining": progress.get("eta"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast(pipeline_id, message)
    
    async def stream_suggestions(
        self,
        pipeline_id: str,
        user_id: str,
        suggestions: List[Dict]
    ):
        """Stream AI suggestions as they're generated."""
        for i, suggestion in enumerate(suggestions):
            message = {
                "type": MessageType.SUGGESTION,
                "pipeline_id": pipeline_id,
                "user_id": user_id,
                "suggestion": suggestion,
                "suggestion_index": i,
                "total_suggestions": len(suggestions),
                "confidence": suggestion.get("confidence", 0.8),
                "category": suggestion.get("category", "general"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.broadcast(pipeline_id, message)
            
            # Small delay between suggestions for better UX
            await asyncio.sleep(0.1)
    
    async def notify_pattern_detected(
        self,
        pipeline_id: str,
        pattern: Dict
    ):
        """Notify users when a pattern is detected."""
        message = {
            "type": MessageType.PATTERN_DETECTED,
            "pipeline_id": pipeline_id,
            "pattern": pattern,
            "suggestion": pattern.get("suggestion"),
            "similar_pipelines": pattern.get("similar_pipelines", []),
            "confidence": pattern.get("confidence", 0.7),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast(pipeline_id, message)
    
    async def notify_optimization(
        self,
        pipeline_id: str,
        optimization: Dict
    ):
        """Notify users of optimization opportunities."""
        message = {
            "type": MessageType.OPTIMIZATION_SUGGESTED,
            "pipeline_id": pipeline_id,
            "optimization": optimization,
            "expected_improvement": optimization.get("improvement"),
            "auto_apply": optimization.get("auto_apply", False),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast(pipeline_id, message)
    
    async def handle_collaborative_edit(
        self,
        pipeline_id: str,
        user_id: str,
        edit: Dict
    ) -> bool:
        """Handle collaborative editing with conflict resolution."""
        # Check if user has edit lock
        if pipeline_id in self.pipeline_locks:
            if self.pipeline_locks[pipeline_id] != user_id:
                # Another user is editing
                await self._send_safe(
                    self.connections[pipeline_id][user_id],
                    {
                        "type": MessageType.WARNING,
                        "message": f"User {self.pipeline_locks[pipeline_id]} is currently editing",
                        "retry_after": 2
                    }
                )
                return False
        else:
            # Acquire edit lock
            self.pipeline_locks[pipeline_id] = user_id
            
            # Auto-release lock after 30 seconds
            asyncio.create_task(self._auto_release_lock(pipeline_id, user_id, 30))
        
        # Apply edit to pipeline state
        if edit.get("field") == "urls":
            self.pipeline_states[pipeline_id]["urls"] = edit.get("value", [])
        elif edit.get("field") == "schema":
            self.pipeline_states[pipeline_id]["schema"] = edit.get("value", {})
        elif edit.get("field") == "code":
            self.pipeline_states[pipeline_id]["code"] = edit.get("value", "")
        
        # Broadcast update to other users
        await self.broadcast_to_others(
            pipeline_id,
            user_id,
            {
                "type": MessageType.PIPELINE_UPDATED,
                "user_id": user_id,
                "field": edit.get("field"),
                "value": edit.get("value"),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Schedule auto-save
        await self._schedule_auto_save(pipeline_id, user_id)
        
        return True
    
    async def _auto_release_lock(self, pipeline_id: str, user_id: str, timeout: int):
        """Auto-release edit lock after timeout."""
        await asyncio.sleep(timeout)
        
        if self.pipeline_locks.get(pipeline_id) == user_id:
            del self.pipeline_locks[pipeline_id]
            
            # Notify user
            if user_id in self.connections.get(pipeline_id, {}):
                await self._send_safe(
                    self.connections[pipeline_id][user_id],
                    {
                        "type": MessageType.INFO,
                        "message": "Edit lock released due to inactivity"
                    }
                )
    
    async def _schedule_auto_save(self, pipeline_id: str, user_id: str):
        """Schedule auto-save of draft."""
        # Cancel existing timer
        timer_key = f"{pipeline_id}:{user_id}"
        if timer_key in self.draft_timers:
            self.draft_timers[timer_key].cancel()
        
        # Schedule new save in 5 seconds
        self.draft_timers[timer_key] = asyncio.create_task(
            self._auto_save_draft(pipeline_id, user_id, 5)
        )
    
    async def _auto_save_draft(self, pipeline_id: str, user_id: str, delay: int):
        """Auto-save draft after delay."""
        await asyncio.sleep(delay)
        
        # Save draft (would save to database in production)
        draft_data = self.pipeline_states.get(pipeline_id, {})
        
        # Notify user of auto-save
        if user_id in self.connections.get(pipeline_id, {}):
            await self._send_safe(
                self.connections[pipeline_id][user_id],
                {
                    "type": MessageType.INFO,
                    "message": "Draft auto-saved",
                    "draft_id": f"draft_{pipeline_id}_{datetime.utcnow().timestamp()}"
                }
            )
    
    async def start_streaming_response(
        self,
        websocket: WebSocket,
        message_id: str
    ) -> StreamingResponse:
        """Start a streaming response."""
        stream = StreamingResponse(websocket, message_id)
        self.active_streams[message_id] = stream
        return stream
    
    async def process_message(
        self,
        pipeline_id: str,
        user_id: str,
        data: Dict
    ) -> Dict:
        """Process incoming WebSocket message with unified agent."""
        message_type = data.get("type", MessageType.CHAT)
        
        if message_type == MessageType.CHAT:
            # Process with unified agent
            from app.agents.unified_agent import unified_agent
            
            # Initialize agent if needed
            if not hasattr(unified_agent, 'initialized'):
                await unified_agent.initialize()
                unified_agent.initialized = True
            
            # Get websocket for streaming
            websocket = self.connections[pipeline_id][user_id]
            
            # Start streaming response
            message_id = str(uuid.uuid4())
            stream = await self.start_streaming_response(websocket, message_id)
            
            # Process message
            result = await unified_agent.process_message(
                message=data.get("message", ""),
                pipeline_id=pipeline_id,
                user_id=user_id,
                context=self.pipeline_states.get(pipeline_id)
            )
            
            # Stream the response
            response_text = result.get("message", "")
            chunk_size = 50  # Characters per chunk
            
            for i in range(0, len(response_text), chunk_size):
                chunk = response_text[i:i + chunk_size]
                await stream.send_chunk(chunk)
                await asyncio.sleep(0.05)  # Small delay for streaming effect
            
            await stream.finish()
            
            # Update pipeline state if changed
            if "updated_context" in result:
                import logging
                logger = logging.getLogger(__name__)
                updated = result["updated_context"]
                # Map the fields correctly
                if "urls" in updated:
                    self.pipeline_states[pipeline_id]["urls"] = updated["urls"]
                if "schema" in updated:
                    self.pipeline_states[pipeline_id]["schema"] = updated["schema"]
                    logger.info(f"Updated schema for {pipeline_id}: {updated['schema']}")
                if "generated_code" in updated:
                    self.pipeline_states[pipeline_id]["code"] = updated["generated_code"]
                if "current_phase" in updated:
                    self.pipeline_states[pipeline_id]["status"] = updated["current_phase"]
                logger.info(f"Pipeline state after update: urls={len(self.pipeline_states[pipeline_id]['urls'])}, schema_fields={len(self.pipeline_states[pipeline_id]['schema'])}")
            
            # Send suggestions if available (commented out to reduce noise)
            # if "suggested_actions" in result:
            #     await self.stream_suggestions(
            #         pipeline_id,
            #         user_id,
            #         [{"action": action, "confidence": 0.8} for action in result["suggested_actions"]]
            #     )
            
            # Send similar pipelines if found (commented out to reduce noise)
            # if "similar_pipelines" in result and result["similar_pipelines"]:
            #     await self.notify_pattern_detected(
            #         pipeline_id,
            #         {
            #             "pattern": "similar_pipelines_found",
            #             "similar_pipelines": result["similar_pipelines"],
            #             "suggestion": "Consider using one of these similar pipelines as a template"
            #         }
            #     )
            
            return result
        
        elif message_type == MessageType.PING:
            return {"type": MessageType.PONG}
        
        else:
            return {
                "type": MessageType.ERROR,
                "message": f"Unknown message type: {message_type}"
            }
    
    def get_pipeline_state(self, pipeline_id: str) -> Dict:
        """Get current pipeline state."""
        return self.pipeline_states.get(pipeline_id, {})
    
    def get_active_users(self, pipeline_id: str) -> List[str]:
        """Get list of active users for a pipeline."""
        return list(self.connections.get(pipeline_id, {}).keys())
    
    async def cleanup(self):
        """Cleanup resources."""
        # Cancel all timers
        for timer in self.draft_timers.values():
            timer.cancel()
        
        # Close all connections
        for pipeline_connections in self.connections.values():
            for websocket in pipeline_connections.values():
                await websocket.close()


# Singleton instance
enhanced_manager = EnhancedWebSocketManager()