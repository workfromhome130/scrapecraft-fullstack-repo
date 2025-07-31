from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing import TypedDict, List, Dict, Annotated, Literal, Optional, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_community.chat_models import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
import operator
import json
import asyncio

from app.config import settings
from app.agents.tools import SCRAPING_TOOLS
from app.agents.prompts import SYSTEM_PROMPT, TOOL_SELECTION_PROMPT
from app.services.openrouter import get_llm
from app.services.scrapegraph import ScrapingService

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    pipeline_id: str
    urls: List[str]
    schema: Dict[str, Any]
    generated_code: str
    execution_results: List[Dict]
    current_status: str
    error: Optional[str]

class ScrapingAgent:
    def __init__(self):
        self.llm = get_llm()
        self.llm_with_tools = self.llm.bind_tools(SCRAPING_TOOLS)
        self.scraping_service = ScrapingService(settings.SCRAPEGRAPH_API_KEY)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        graph = StateGraph(AgentState)
        
        # Add nodes
        graph.add_node("analyze_request", self._analyze_request)
        graph.add_node("call_tools", self._call_tools)
        graph.add_node("generate_response", self._generate_response)
        graph.add_node("execute_scraping", self._execute_scraping)
        
        # Set entry point
        graph.set_entry_point("analyze_request")
        
        # Add edges
        graph.add_conditional_edges(
            "analyze_request",
            self._should_use_tools,
            {
                True: "call_tools",
                False: "generate_response"
            }
        )
        
        graph.add_conditional_edges(
            "call_tools",
            self._should_execute_scraping,
            {
                True: "execute_scraping",
                False: "generate_response"
            }
        )
        
        graph.add_edge("execute_scraping", "generate_response")
        graph.add_edge("generate_response", END)
        
        return graph.compile()
    
    async def _analyze_request(self, state: AgentState) -> AgentState:
        """Analyze the user request and determine action."""
        messages = state["messages"]
        
        # Create prompt with system message
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("messages")
        ])
        
        # Get response with tools
        response = await self.llm_with_tools.ainvoke(messages)
        
        return {
            **state,
            "messages": [response]
        }
    
    async def _call_tools(self, state: AgentState) -> AgentState:
        """Execute the selected tools."""
        last_message = state["messages"][-1]
        
        if not last_message.tool_calls:
            return state
        
        # Execute each tool call
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # Find and execute the tool
            tool = next((t for t in SCRAPING_TOOLS if t.name == tool_name), None)
            if tool:
                if asyncio.iscoroutinefunction(tool.func):
                    result = await tool.func(**tool_args)
                else:
                    result = tool.func(**tool_args)
                
                # Update state based on tool
                if tool_name == "add_url" and result["success"]:
                    state["urls"].append(tool_args["url"])
                elif tool_name == "remove_url" and result["success"]:
                    state["urls"].remove(tool_args["url"])
                elif tool_name == "define_schema" and result["success"]:
                    state["schema"] = result["schema"]
                elif tool_name == "generate_code" and result["success"]:
                    state["generated_code"] = result["code"]
                elif tool_name == "clear_pipeline" and result["success"]:
                    state["urls"] = []
                    state["schema"] = {}
                    state["generated_code"] = ""
                
                # Add tool response as message
                tool_message = AIMessage(
                    content=json.dumps(result),
                    name=tool_name,
                    additional_kwargs={"tool_call_id": tool_call["id"]}
                )
                state["messages"].append(tool_message)
        
        return state
    
    async def _execute_scraping(self, state: AgentState) -> AgentState:
        """Execute the actual scraping with ScrapeGraphAI."""
        if not state["urls"] or not state["schema"]:
            state["error"] = "No URLs or schema defined"
            return state
        
        try:
            results = await self.scraping_service.execute_pipeline(
                urls=state["urls"],
                schema=state["schema"],
                prompt="Extract data according to the defined schema"
            )
            state["execution_results"] = results
            state["current_status"] = "completed"
        except Exception as e:
            state["error"] = str(e)
            state["current_status"] = "error"
        
        return state
    
    async def _generate_response(self, state: AgentState) -> AgentState:
        """Generate the final response to the user."""
        # Create a summary of actions taken
        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "Summarize the actions taken and provide a helpful response to the user. Include any results, generated code, or next steps."),
            MessagesPlaceholder("messages")
        ])
        
        response = await self.llm.ainvoke(state["messages"])
        state["messages"].append(response)
        
        return state
    
    def _should_use_tools(self, state: AgentState) -> bool:
        """Determine if tools should be used."""
        last_message = state["messages"][-1]
        return hasattr(last_message, 'tool_calls') and len(last_message.tool_calls) > 0
    
    def _should_execute_scraping(self, state: AgentState) -> bool:
        """Determine if scraping should be executed."""
        # Check if user requested execution
        last_user_message = next(
            (msg for msg in reversed(state["messages"]) if isinstance(msg, HumanMessage)), 
            None
        )
        
        if last_user_message and any(
            keyword in last_user_message.content.lower() 
            for keyword in ["execute", "run", "scrape", "start scraping"]
        ):
            return bool(state["urls"] and state["schema"])
        
        return False
    
    async def process_message(self, message: str, pipeline_id: str, context: Dict = None) -> Dict:
        """Process a user message and return the response."""
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "pipeline_id": pipeline_id,
            "urls": context.get("urls", []) if context else [],
            "schema": context.get("schema", {}) if context else {},
            "generated_code": context.get("generated_code", "") if context else "",
            "execution_results": [],
            "current_status": "processing",
            "error": None
        }
        
        # Run the graph
        final_state = await self.graph.ainvoke(initial_state)
        
        # Extract the response
        last_ai_message = next(
            (msg for msg in reversed(final_state["messages"]) if isinstance(msg, AIMessage)), 
            None
        )
        
        return {
            "response": last_ai_message.content if last_ai_message else "No response generated",
            "urls": final_state["urls"],
            "schema": final_state["schema"],
            "code": final_state["generated_code"],
            "results": final_state["execution_results"],
            "status": final_state["current_status"],
            "error": final_state["error"]
        }

# Create a singleton instance
scraping_agent = ScrapingAgent()