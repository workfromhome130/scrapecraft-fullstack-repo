"""
Tool-based LangGraph agent for web scraping with ScrapeGraphAI.
This implementation follows LangChain best practices with proper tool integration.
"""
from typing import Dict, List, Optional, TypedDict, Annotated, Sequence, Literal, Any
from datetime import datetime
import json
import logging

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.services.openrouter import get_llm
from app.agents.tools.scraping_tools import (
    smart_scraper_tool,
    smart_crawler_tool,
    search_scraper_tool,
    markdownify_tool,
    validate_urls_tool
)

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the tool-based agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    pipeline_id: str
    urls: List[Dict[str, Any]]
    schema_fields: List[Dict[str, Any]]
    generated_code: str
    scraping_results: List[Dict[str, Any]]


class ToolBasedScrapingAgent:
    """LangGraph agent using tools for web scraping."""
    
    def __init__(self):
        self.llm = get_llm()
        self.memory = MemorySaver()
        self.tools = self._get_tools()
        self.graph = self._build_graph()
        
    def _get_tools(self) -> List[BaseTool]:
        """Get all available tools."""
        return [
            smart_scraper_tool,
            smart_crawler_tool,
            search_scraper_tool,
            markdownify_tool,
            validate_urls_tool
        ]
        
    def _build_graph(self) -> StateGraph:
        """Build the tool-based agent graph."""
        # Bind tools to the LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # System prompt for the agent
        system_prompt = """You are a helpful web scraping assistant powered by ScrapeGraphAI.
        
Your capabilities:
1. **Search for websites** using search_scraper to find relevant URLs
2. **Extract data from single pages** using smart_scraper with natural language prompts
3. **Crawl multiple pages** using smart_crawler for comprehensive data collection
4. **Convert pages to markdown** using markdownify for readable content
5. **Validate URLs** before scraping to ensure they're accessible

When helping users:
- If they want to scrape specific URLs, use smart_scraper or smart_crawler
- If they need to find URLs first, use search_scraper
- If they want readable content, use markdownify
- Always validate URLs if there's any doubt about accessibility
- Explain what you're doing and why
- Present results in a clear, structured format

Remember: You can use multiple tools in sequence to accomplish complex tasks."""
        
        async def assistant(state: AgentState) -> Dict[str, Any]:
            """Main assistant node that calls the LLM."""
            # Prepend system message to the conversation
            messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
            
            # Call LLM with tools
            response = await llm_with_tools.ainvoke(messages)
            
            return {"messages": [response]}
        
        async def human_feedback(state: AgentState) -> Dict[str, Any]:
            """Node for human feedback/approval."""
            # Check if we need human approval
            last_message = state["messages"][-1]
            
            # For now, auto-approve to keep the flow going
            # In production, this would wait for actual human input
            return {"messages": []}
        
        # Build the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("assistant", assistant)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_node("human_feedback", human_feedback)
        
        # Set entry point
        workflow.add_edge(START, "assistant")
        
        # Add conditional routing from assistant
        workflow.add_conditional_edges(
            "assistant",
            tools_condition,  # Routes to tools if tool call, else END
            {
                "tools": "tools",
                END: END
            }
        )
        
        # After tools, always go back to assistant
        workflow.add_edge("tools", "assistant")
        
        # Compile with memory
        return workflow.compile(checkpointer=self.memory)
    
    async def process_message(
        self,
        message: str,
        pipeline_id: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a user message through the agent."""
        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "pipeline_id": pipeline_id,
            "urls": [],
            "schema_fields": [],
            "generated_code": "",
            "scraping_results": []
        }
        
        # Configure thread
        config = {"configurable": {"thread_id": thread_id or pipeline_id}}
        
        try:
            # Run the graph
            final_state = await self.graph.ainvoke(initial_state, config)
            
            # Extract the last AI message
            ai_messages = [
                msg for msg in final_state["messages"] 
                if isinstance(msg, AIMessage)
            ]
            
            last_response = ai_messages[-1].content if ai_messages else "No response generated"
            
            # Extract any tool results
            tool_results = []
            for msg in final_state["messages"]:
                if isinstance(msg, ToolMessage):
                    tool_results.append({
                        "tool": msg.name,
                        "result": msg.content
                    })
            
            return {
                "response": last_response,
                "tool_results": tool_results,
                "message_count": len(final_state["messages"]),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Agent processing failed: {str(e)}")
            return {
                "response": f"I encountered an error: {str(e)}. Please try again.",
                "error": str(e),
                "success": False
            }
    
    async def search_and_collect_urls(
        self,
        search_query: str,
        pipeline_id: str
    ) -> List[Dict[str, Any]]:
        """Helper method to search and collect URLs."""
        message = f"Search for websites about: {search_query}"
        result = await self.process_message(message, pipeline_id)
        
        # Extract URLs from tool results
        urls = []
        for tool_result in result.get("tool_results", []):
            if tool_result["tool"] == "search_scraper":
                try:
                    data = json.loads(tool_result["result"]) if isinstance(tool_result["result"], str) else tool_result["result"]
                    if data.get("success") and data.get("results"):
                        urls.extend(data["results"])
                except:
                    pass
                    
        return urls
    
    async def scrape_url(
        self,
        url: str,
        prompt: str,
        pipeline_id: str
    ) -> Dict[str, Any]:
        """Helper method to scrape a single URL."""
        message = f"Extract the following from {url}: {prompt}"
        result = await self.process_message(message, pipeline_id)
        
        # Extract scraping results
        for tool_result in result.get("tool_results", []):
            if tool_result["tool"] == "smart_scraper":
                try:
                    data = json.loads(tool_result["result"]) if isinstance(tool_result["result"], str) else tool_result["result"]
                    if data.get("success"):
                        return data
                except:
                    pass
                    
        return {"success": False, "error": "No scraping results found"}


# Export the agent class
__all__ = ["ToolBasedScrapingAgent"]