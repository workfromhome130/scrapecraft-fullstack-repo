"""
Enhanced workflow API endpoints with support for tool-based agent.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, List, Any, Optional
import os

from app.services.websocket import ConnectionManager
from app.services.workflow_manager_v2 import get_enhanced_workflow_manager
from app.models.workflow import WorkflowState
from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/v2/workflow", tags=["workflow-v2"])


@router.get("/agent-mode")
async def get_agent_mode() -> Dict[str, Any]:
    """Get current agent mode (tools-based or state-based)."""
    # This could be configured via environment variable
    import os
    use_tools = os.getenv("USE_TOOLS_AGENT", "false").lower() == "true"
    
    return {
        "mode": "tools-based" if use_tools else "state-based",
        "features": {
            "tools_based": {
                "enabled": use_tools,
                "description": "Simplified tool-based agent with better error handling",
                "advantages": [
                    "Simpler state management",
                    "Better error recovery",
                    "Direct tool access",
                    "Easier to extend"
                ]
            },
            "state_based": {
                "enabled": not use_tools,
                "description": "Original state machine agent with complex workflows",
                "advantages": [
                    "Fine-grained control",
                    "Complex workflow support",
                    "Detailed state tracking",
                    "Custom routing logic"
                ]
            }
        }
    }


@router.post("/search")
async def search_urls(
    search_query: str,
    pipeline_id: str,
    max_results: int = Query(10, ge=1, le=50),
    connection_manager: ConnectionManager = Depends(lambda: ConnectionManager()),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Search for URLs using the enhanced workflow manager.
    
    This endpoint uses the tool-based agent if enabled for better search capabilities.
    """
    use_tools = os.getenv("USE_TOOLS_AGENT", "false").lower() == "true"
    manager = get_enhanced_workflow_manager(connection_manager, use_tools)
    
    try:
        urls = await manager.search_urls(pipeline_id, search_query)
        
        return {
            "success": True,
            "query": search_query,
            "urls": urls,
            "count": len(urls),
            "agent_mode": "tools-based" if use_tools else "state-based"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape")
async def scrape_urls(
    request: Dict[str, Any],
    connection_manager: ConnectionManager = Depends(lambda: ConnectionManager()),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Scrape multiple URLs with a given prompt.
    
    Request body:
    {
        "pipeline_id": "string",
        "urls": ["url1", "url2"],
        "extraction_prompt": "What data to extract"
    }
    """
    pipeline_id = request.get("pipeline_id")
    urls = request.get("urls", [])
    extraction_prompt = request.get("extraction_prompt", "Extract all relevant data")
    
    if not pipeline_id or not urls:
        raise HTTPException(status_code=400, detail="pipeline_id and urls are required")
    
    use_tools = os.getenv("USE_TOOLS_AGENT", "false").lower() == "true"
    manager = get_enhanced_workflow_manager(connection_manager, use_tools)
    
    try:
        results = await manager.scrape_urls(pipeline_id, urls, extraction_prompt)
        
        return {
            "success": True,
            "urls_scraped": len(urls),
            "results": results,
            "agent_mode": "tools-based" if use_tools else "state-based"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def get_available_tools(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get list of available tools in the tool-based agent."""
    return {
        "tools": [
            {
                "name": "smart_scraper",
                "description": "Extract structured data from a single webpage",
                "parameters": ["website_url", "user_prompt"],
                "use_cases": [
                    "Extract contact information",
                    "Get product details",
                    "Scrape article content"
                ]
            },
            {
                "name": "smart_crawler",
                "description": "Crawl and extract data from multiple pages",
                "parameters": ["website_url", "user_prompt", "max_depth", "max_pages"],
                "use_cases": [
                    "Scrape entire product catalogs",
                    "Collect data from blog archives",
                    "Extract data from multi-page listings"
                ]
            },
            {
                "name": "search_scraper",
                "description": "Search for websites based on a query",
                "parameters": ["search_query", "max_results"],
                "use_cases": [
                    "Find relevant websites for a topic",
                    "Discover data sources",
                    "Research competitors"
                ]
            },
            {
                "name": "markdownify",
                "description": "Convert webpage to clean markdown",
                "parameters": ["website_url"],
                "use_cases": [
                    "Create documentation from web pages",
                    "Extract readable content",
                    "Archive web content"
                ]
            },
            {
                "name": "validate_urls",
                "description": "Check if URLs are accessible",
                "parameters": ["urls"],
                "use_cases": [
                    "Verify URLs before scraping",
                    "Filter out broken links",
                    "Check website availability"
                ]
            }
        ]
    }


@router.post("/migrate")
async def migrate_workflow(
    pipeline_id: str,
    connection_manager: ConnectionManager = Depends(lambda: ConnectionManager()),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Migrate a workflow from state-based to tool-based agent.
    
    This helps users transition their existing workflows to the new agent.
    """
    # Get both managers
    state_manager = get_enhanced_workflow_manager(connection_manager, use_tools=False)
    tools_manager = get_enhanced_workflow_manager(connection_manager, use_tools=True)
    
    # Get existing workflow
    workflow = state_manager.get_workflow(pipeline_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    # Create simplified message for tool-based agent
    migration_summary = []
    
    if workflow.urls:
        migration_summary.append(f"Found {len(workflow.urls)} URLs to process")
        
    if workflow.schema_fields:
        schema_desc = ", ".join([f.name for f in workflow.schema_fields])
        migration_summary.append(f"Schema fields: {schema_desc}")
        
    if workflow.generated_code:
        migration_summary.append("Has generated code ready")
        
    # Process with new agent
    message = f"""Migrate this workflow to use the new tool-based approach.
    
Current state: {workflow.phase.value}
{' '.join(migration_summary)}

Please analyze the current workflow and suggest how to proceed with the available tools."""
    
    result = await tools_manager.process_message(pipeline_id, message, current_user.username)
    
    return {
        "success": True,
        "original_workflow": {
            "phase": workflow.phase.value,
            "urls_count": len(workflow.urls),
            "schema_fields_count": len(workflow.schema_fields),
            "has_code": bool(workflow.generated_code)
        },
        "migration_result": result,
        "recommendations": [
            "Use smart_scraper for single-page extraction",
            "Use smart_crawler for multi-page scraping",
            "Use search_scraper to find new URLs",
            "The new agent handles state automatically"
        ]
    }


# Import and include in main app
__all__ = ["router"]