"""
Enhanced workflow manager that supports both the original and tool-based agents.
Provides a migration path from the complex state-based agent to the simpler tool-based approach.
"""
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime
import json
import logging

from app.models.workflow import (
    WorkflowState, WorkflowPhase, URLInfo, SchemaField
)
from app.agents.langgraph_agent import ScrapeCraftAgent
from app.agents.langgraph_tools_agent import ToolBasedScrapingAgent
from app.services.websocket import ConnectionManager

logger = logging.getLogger(__name__)


class EnhancedWorkflowManager:
    """Enhanced workflow manager supporting multiple agent implementations."""
    
    def __init__(self, connection_manager: ConnectionManager, use_tools_agent: bool = False):
        self.workflows: Dict[str, WorkflowState] = {}
        self.connection_manager = connection_manager
        self.use_tools_agent = use_tools_agent
        
        # Initialize the appropriate agent
        if use_tools_agent:
            logger.info("Using tool-based agent implementation")
            self.agent = ToolBasedScrapingAgent()
        else:
            logger.info("Using original state-based agent implementation")
            self.agent = ScrapeCraftAgent()
            
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
        """Process a message through the appropriate agent."""
        # Get or create workflow
        workflow = self.get_workflow(pipeline_id) or self.create_workflow(pipeline_id, user)
        
        if self.use_tools_agent:
            # Use the simpler tool-based agent
            result = await self._process_with_tools_agent(workflow, message, pipeline_id)
        else:
            # Use the original state-based agent
            result = await self._process_with_state_agent(workflow, message, pipeline_id)
        
        # Broadcast state update
        await self._broadcast_workflow_update(workflow)
        
        return result
    
    async def _process_with_tools_agent(
        self,
        workflow: WorkflowState,
        message: str,
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Process message using the tool-based agent."""
        # Determine intent from message
        message_lower = message.lower()
        
        # Update workflow phase based on intent
        if any(word in message_lower for word in ["search", "find urls", "look for"]):
            workflow.add_transition(WorkflowPhase.URL_COLLECTION, "User requested URL search", "user")
        elif any(word in message_lower for word in ["scrape", "extract", "get data"]):
            if workflow.urls:
                workflow.add_transition(WorkflowPhase.EXECUTING, "User requested data extraction", "user")
            else:
                workflow.add_transition(WorkflowPhase.URL_COLLECTION, "Need URLs before scraping", "agent")
        
        # Process through tool agent
        result = await self.agent.process_message(message, pipeline_id)
        
        # Update workflow based on tool results
        if result.get("success"):
            await self._update_workflow_from_tools(workflow, result)
            
            # Determine response type
            response_data = {
                "response": result["response"],
                "workflow_state": workflow.model_dump(mode='json'),
                "requires_action": False
            }
            
            # Check for URLs in tool results
            for tool_result in result.get("tool_results", []):
                if tool_result["tool"] == "search_scraper":
                    try:
                        data = json.loads(tool_result["result"]) if isinstance(tool_result["result"], str) else tool_result["result"]
                        if data.get("results"):
                            # Convert to URLInfo objects
                            urls = []
                            for url_data in data["results"]:
                                urls.append(URLInfo(
                                    url=url_data.get("url", ""),
                                    description=url_data.get("description", ""),
                                    relevance="high",
                                    validated=False
                                ))
                            workflow.urls = urls
                            workflow.add_transition(WorkflowPhase.URL_VALIDATION, "URLs found", "agent")
                            response_data["requires_action"] = True
                    except Exception as e:
                        logger.error(f"Failed to parse search results: {e}")
                        
                elif tool_result["tool"] == "smart_scraper":
                    try:
                        data = json.loads(tool_result["result"]) if isinstance(tool_result["result"], str) else tool_result["result"]
                        if data.get("success"):
                            workflow.execution_results.append(data)
                            workflow.add_transition(WorkflowPhase.COMPLETED, "Data extracted successfully", "agent")
                    except Exception as e:
                        logger.error(f"Failed to parse scraping results: {e}")
            
            return response_data
        else:
            workflow.add_transition(WorkflowPhase.ERROR, f"Agent error: {result.get('error', 'Unknown')}", "agent")
            return {
                "response": result["response"],
                "workflow_state": workflow.model_dump(mode='json'),
                "requires_action": False
            }
    
    async def _process_with_state_agent(
        self,
        workflow: WorkflowState,
        message: str,
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Process message using the original state-based agent."""
        # Use the original agent processing
        result = await self.agent.process_message(message, pipeline_id)
        
        # Update workflow state based on result
        await self._update_workflow_from_result(workflow, result)
        
        return {
            "response": result["response"],
            "workflow_state": workflow.model_dump(mode='json'),
            "requires_action": result.get("requires_approval", False)
        }
    
    async def _update_workflow_from_tools(
        self,
        workflow: WorkflowState,
        result: Dict[str, Any]
    ):
        """Update workflow state from tool-based agent results."""
        # This is simplified compared to the original
        # The tool-based agent handles most logic internally
        workflow.updated_at = datetime.utcnow()
    
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
            workflow.code_validated = False
        
        # Update results
        if result.get("results"):
            workflow.execution_results = result["results"]
    
    async def _broadcast_workflow_update(self, workflow: WorkflowState):
        """Broadcast workflow state update to connected clients."""
        await self.connection_manager.broadcast({
            "type": "workflow_update",
            "workflow": workflow.model_dump(mode='json'),
            "progress": workflow.get_phase_progress()
        }, workflow.pipeline_id)
    
    # Additional helper methods for the tool-based approach
    
    async def search_urls(self, pipeline_id: str, search_query: str) -> List[Dict[str, Any]]:
        """Search for URLs using the tool-based agent."""
        if self.use_tools_agent:
            return await self.agent.search_and_collect_urls(search_query, pipeline_id)
        else:
            # Fallback to a simple message
            result = await self.process_message(
                pipeline_id,
                f"Search for URLs about: {search_query}",
                "user"
            )
            workflow = self.get_workflow(pipeline_id)
            return [url.dict() for url in (workflow.urls if workflow else [])]
    
    async def scrape_urls(
        self,
        pipeline_id: str,
        urls: List[str],
        extraction_prompt: str
    ) -> List[Dict[str, Any]]:
        """Scrape multiple URLs with the given prompt."""
        if self.use_tools_agent:
            results = []
            for url in urls:
                result = await self.agent.scrape_url(url, extraction_prompt, pipeline_id)
                results.append(result)
            return results
        else:
            # Fallback to processing through message
            url_list = "\n".join(urls)
            result = await self.process_message(
                pipeline_id,
                f"Scrape these URLs and extract: {extraction_prompt}\n\nURLs:\n{url_list}",
                "user"
            )
            workflow = self.get_workflow(pipeline_id)
            return workflow.execution_results if workflow else []


# Factory function to get the appropriate workflow manager
def get_enhanced_workflow_manager(
    connection_manager: ConnectionManager,
    use_tools_agent: bool = False
) -> EnhancedWorkflowManager:
    """Get or create enhanced workflow manager instance."""
    return EnhancedWorkflowManager(connection_manager, use_tools_agent)