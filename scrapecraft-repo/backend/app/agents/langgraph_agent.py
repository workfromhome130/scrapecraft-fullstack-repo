"""
LangGraph-based agent for ScrapeCraft with proper state management and workflow orchestration.
"""
from typing import Dict, List, Optional, TypedDict, Annotated, Sequence, Literal, Any
from enum import Enum
import json
import asyncio
from datetime import datetime
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.services.openrouter import get_llm
from app.services.scrapegraph import ScrapingService


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


class URLInfo(BaseModel):
    """Information about a URL."""
    url: str
    description: str = ""
    relevance: Literal["high", "medium", "low"] = "medium"
    validated: bool = False
    validation_reason: Optional[str] = None


class SchemaField(BaseModel):
    """Schema field definition."""
    name: str
    type: str
    description: str
    required: bool = True
    example: Optional[str] = None


class AgentState(TypedDict):
    """State for the LangGraph agent."""
    # Conversation
    messages: Sequence[BaseMessage]
    
    # Pipeline information
    pipeline_id: str
    user_request: str
    
    # Workflow phase
    phase: WorkflowPhase
    
    # URLs
    urls: List[URLInfo]
    urls_validated: bool
    
    # Schema
    schema_fields: List[SchemaField]
    schema_validated: bool
    
    # Generated code
    generated_code: str
    
    # Execution results
    execution_results: List[Dict]
    
    # Approval gates
    requires_approval: bool
    approval_status: Optional[Literal["pending", "approved", "rejected"]]
    
    # Error tracking
    errors: List[str]
    
    # Extracted entities from request
    extracted_entities: Dict[str, Any]
    
    # Metadata
    created_at: datetime
    updated_at: datetime


class ScrapeCraftAgent:
    """LangGraph-based agent for web scraping pipelines."""
    
    def __init__(self):
        self.llm = get_llm()
        self.scraping_service = ScrapingService(settings.SCRAPEGRAPH_API_KEY)
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("analyze_request", self.analyze_request)
        workflow.add_node("collect_urls", self.collect_urls)
        workflow.add_node("validate_urls", self.validate_urls)
        workflow.add_node("define_schema", self.define_schema)
        workflow.add_node("validate_schema", self.validate_schema)
        workflow.add_node("generate_code", self.generate_code)
        workflow.add_node("await_approval", self.await_approval)
        workflow.add_node("execute_pipeline", self.execute_pipeline)
        workflow.add_node("handle_error", self.handle_error)
        
        # Set entry point
        workflow.set_entry_point("analyze_request")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "analyze_request",
            self.route_after_analysis,
            {
                "collect_urls": "collect_urls",
                "validate_urls": "validate_urls",
                "define_schema": "define_schema",
                "generate_code": "generate_code",
                "error": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "collect_urls",
            lambda state: "validate_urls" if state["urls"] else "handle_error"
        )
        
        workflow.add_conditional_edges(
            "validate_urls",
            lambda state: "await_approval" if state["requires_approval"] else "define_schema"
        )
        
        workflow.add_conditional_edges(
            "await_approval",
            self.route_after_approval,
            {
                "continue": "define_schema",
                "reject": "collect_urls",
                "timeout": "handle_error"
            }
        )
        
        workflow.add_conditional_edges(
            "define_schema",
            lambda state: "validate_schema" if state["schema_fields"] else "handle_error"
        )
        
        workflow.add_conditional_edges(
            "validate_schema",
            lambda state: "generate_code" if state["schema_validated"] else "define_schema"
        )
        
        workflow.add_edge("generate_code", "await_approval")
        
        workflow.add_conditional_edges(
            "await_approval",
            self.route_code_approval,
            {
                "execute": "execute_pipeline",
                "regenerate": "generate_code",
                "end": END
            }
        )
        
        workflow.add_edge("execute_pipeline", END)
        workflow.add_edge("handle_error", END)
        
        return workflow.compile(checkpointer=self.memory)
    
    async def analyze_request(self, state: AgentState) -> AgentState:
        """Analyze the user's request to determine the workflow path."""
        messages = state["messages"]
        last_message = messages[-1].content if messages else ""
        
        # First, check if the request is clear enough
        clarity_prompt = f"""Analyze this web scraping request for clarity:

User request: "{last_message}"

Determine:
1. Is the request specific enough to proceed?
2. What key information might be missing?
3. What clarifying questions should we ask?

Consider:
- Are specific data fields mentioned?
- Is the target website/domain specified?
- For location-based requests, are the locations clear?
- Is the data type clear (prices, reviews, weather, etc.)?

Respond in JSON format:
{{
    "is_clear": boolean,
    "clarity_score": 1-10,
    "missing_info": ["list of missing information"],
    "clarification_needed": boolean,
    "clarification_questions": ["list of questions to ask"],
    "extracted_entities": {{
        "domain": "website domain if mentioned",
        "locations": ["list of locations"],
        "data_type": "type of data requested",
        "specific_items": ["specific items mentioned"]
    }}
}}"""

        clarity_response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert at analyzing web scraping requests."),
            HumanMessage(content=clarity_prompt)
        ])
        
        try:
            clarity_analysis = json.loads(clarity_response.content)
            
            # If clarification is needed, ask the user
            if clarity_analysis.get("clarification_needed", False) and clarity_analysis["clarity_score"] < 7:
                questions = clarity_analysis.get("clarification_questions", [])
                if questions:
                    clarification_message = "I'd like to better understand your request. " + " ".join(questions)
                    state["messages"].append(AIMessage(content=clarification_message))
                    state["phase"] = WorkflowPhase.INITIAL
                    state["requires_approval"] = True
                    state["updated_at"] = datetime.utcnow()
                    return state
            
            # Store extracted entities for later use
            state["extracted_entities"] = clarity_analysis.get("extracted_entities", {})
            
        except Exception as e:
            # Continue with regular analysis if clarity check fails
            pass
        
        # Analyze intent using LLM
        analysis_prompt = f"""Analyze this user request for a web scraping pipeline:

User request: "{last_message}"

Determine:
1. What phase should we start with?
2. Did they provide URLs directly?
3. Do they need URL search?
4. Did they define a schema?
5. Are they asking to generate code?

Respond in JSON format:
{{
    "starting_phase": "url_collection|schema_definition|code_generation",
    "has_urls": boolean,
    "needs_search": boolean,
    "has_schema": boolean,
    "urls_provided": ["list of URLs if any"]
}}"""

        response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert at analyzing web scraping requests."),
            HumanMessage(content=analysis_prompt)
        ])
        
        try:
            analysis = json.loads(response.content)
            
            # Update state based on analysis
            state["user_request"] = last_message
            
            if analysis.get("urls_provided"):
                state["urls"] = [URLInfo(url=url, validated=False) for url in analysis["urls_provided"]]
                state["phase"] = WorkflowPhase.URL_VALIDATION
            elif analysis.get("needs_search"):
                state["phase"] = WorkflowPhase.URL_COLLECTION
            elif analysis.get("has_schema"):
                state["phase"] = WorkflowPhase.SCHEMA_DEFINITION
            else:
                state["phase"] = WorkflowPhase.URL_COLLECTION
                
        except Exception as e:
            state["errors"].append(f"Failed to analyze request: {str(e)}")
            state["phase"] = WorkflowPhase.ERROR
            
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def collect_urls(self, state: AgentState) -> AgentState:
        """Collect URLs through search or user input."""
        user_request = state["user_request"]
        extracted_entities = state.get("extracted_entities", {})
        
        # Generate multiple search queries for better coverage
        search_prompt = f"""Based on this request: "{user_request}"
        
Extracted entities: {json.dumps(extracted_entities, indent=2)}

Generate multiple search queries to find the most relevant URLs.
For location-based requests, create separate queries for each location.
If a specific domain is mentioned, use site: operator.

Examples:
- Request: "scrape weather data for Milan and Turin from ilmeteo.it"
  Queries: ["Milan weather site:ilmeteo.it", "Turin weather site:ilmeteo.it", "meteo Milano site:ilmeteo.it", "meteo Torino site:ilmeteo.it"]
  
- Request: "find product prices on amazon"
  Queries: ["site:amazon.com", "amazon product prices"]

Respond in JSON format:
{{
    "search_queries": ["query1", "query2", ...],
    "search_strategy": "explanation of search strategy"
}}"""
        
        response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert at generating search queries for web scraping."),
            HumanMessage(content=search_prompt)
        ])
        
        try:
            search_plan = json.loads(response.content)
            search_queries = search_plan.get("search_queries", [user_request])
            
            # Collect URLs from all searches
            all_urls = []
            seen_urls = set()
            
            for query in search_queries[:3]:  # Limit to 3 queries to avoid too many results
                try:
                    search_results = await self.scraping_service.search_urls(query, max_results=10)
                    
                    for result in search_results:
                        if isinstance(result, dict):
                            url = result.get('url', '')
                            if url and url not in seen_urls:
                                seen_urls.add(url)
                                all_urls.append(URLInfo(
                                    url=url,
                                    description=result.get('description', ''),
                                    validated=False
                                ))
                except Exception as e:
                    state["errors"].append(f"Search failed for '{query}': {str(e)}")
                    
                    # If search fails, try to construct URLs directly if domain is known
                    if extracted_entities.get("domain") and extracted_entities.get("locations"):
                        domain = extracted_entities["domain"]
                        for location in extracted_entities["locations"]:
                            # Try common URL patterns
                            location_lower = location.lower()
                            
                            # Special handling for known sites
                            if "ilmeteo.it" in domain:
                                # ilmeteo.it uses specific patterns
                                if location_lower == "milan":
                                    location_lower = "milano"
                                elif location_lower == "turin":
                                    location_lower = "torino"
                                potential_urls = [
                                    f"https://www.ilmeteo.it/meteo/{location_lower}",
                                    f"https://ilmeteo.it/meteo/{location_lower}"
                                ]
                            else:
                                potential_urls = [
                                    f"https://{domain}/meteo/{location_lower}",
                                    f"https://{domain}/weather/{location_lower}",
                                    f"https://{domain}/{location_lower}",
                                    f"https://www.{domain}/meteo/{location_lower}",
                                    f"https://www.{domain}/weather/{location_lower}"
                                ]
                            
                            for potential_url in potential_urls:
                                if potential_url not in seen_urls:
                                    seen_urls.add(potential_url)
                                    all_urls.append(URLInfo(
                                        url=potential_url,
                                        description=f"Direct link for {location} weather data",
                                        validated=False
                                    ))
                                    break  # Only add one URL per location
                    
            state["urls"] = all_urls
            
            if all_urls:
                state["phase"] = WorkflowPhase.URL_VALIDATION
                # Add informative message
                state["messages"].append(AIMessage(
                    content=f"I searched for '{', '.join(search_queries)}' and found {len(all_urls)} URLs. Let me validate them for relevance to your specific request."
                ))
            else:
                # No URLs found - ask user for help
                state["phase"] = WorkflowPhase.INITIAL
                state["requires_approval"] = True
                error_msg = "I couldn't find any URLs through search. "
                if state["errors"]:
                    error_msg += f"Search errors: {'; '.join(state['errors'][:2])}. "
                error_msg += "Could you please:\n1. Provide direct URLs you'd like to scrape, or\n2. Try a different search term, or\n3. Check if the website is accessible?"
                state["messages"].append(AIMessage(content=error_msg))
            
        except Exception as e:
            # Fallback to simple search
            search_query = user_request
            try:
                search_results = await self.scraping_service.search_urls(search_query, max_results=10)
                
                urls = []
                for result in search_results:
                    if isinstance(result, dict):
                        urls.append(URLInfo(
                            url=result.get('url', ''),
                            description=result.get('description', ''),
                            validated=False
                        ))
                        
                state["urls"] = urls
                state["phase"] = WorkflowPhase.URL_VALIDATION
                
                state["messages"].append(AIMessage(
                    content=f"I found {len(urls)} URLs for '{search_query}'. Let me validate them for relevance."
                ))
            except Exception as search_error:
                state["errors"].append(f"URL search failed: {str(search_error)}")
                state["phase"] = WorkflowPhase.ERROR
            
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def validate_urls(self, state: AgentState) -> AgentState:
        """Validate and filter URLs based on relevance."""
        urls = state["urls"]
        user_request = state["user_request"]
        extracted_entities = state.get("extracted_entities", {})
        
        if not urls:
            state["phase"] = WorkflowPhase.ERROR
            state["errors"].append("No URLs to validate")
            return state
        
        # Create detailed validation prompt with entity extraction
        url_list = "\n".join([f"{i+1}. {url.url}: {url.description}" for i, url in enumerate(urls)])
        
        validation_prompt = f"""Carefully validate these URLs for the request: "{user_request}"

Extracted entities from request:
{json.dumps(extracted_entities, indent=2)}

URLs to validate:
{url_list}

For each URL, analyze:
1. URL Pattern Analysis:
   - Does the URL path contain specific requested entities (e.g., city names, product names)?
   - Is this a specific data page or a general navigation/overview page?
   - URL depth (deeper paths are often more specific)

2. Content Relevance:
   - Based on the description, does this page contain the requested data?
   - Is this the primary source for the data or a secondary/aggregated page?

3. Scoring Criteria:
   - HIGH relevance: URL directly matches request (e.g., /meteo/milano for "Milan weather")
   - MEDIUM relevance: Related but not specific (e.g., /italy for "Milan weather")
   - LOW relevance: General or navigation pages (e.g., homepage, category pages)

Only include URLs with HIGH relevance unless there are very few high-relevance URLs.

Examples:
- Request: "weather data for Milan and Turin from ilmeteo.it"
  - HIGH: ilmeteo.it/meteo/milano, ilmeteo.it/meteo/torino
  - LOW: ilmeteo.it/italia, ilmeteo.it/meteo-europa

Respond in JSON format:
{{
    "analysis_summary": "Brief explanation of filtering strategy",
    "validated_urls": [
        {{
            "url": "full URL",
            "relevance": "high|medium|low",
            "include": boolean,
            "specificity_score": 1-10,
            "matches_entities": ["list of matched entities"],
            "reason": "detailed explanation"
        }}
    ],
    "excluded_count": number,
    "excluded_reasons": ["list of common exclusion reasons"]
}}"""

        response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert at validating URLs for web scraping with strict relevance criteria."),
            HumanMessage(content=validation_prompt)
        ])
        
        try:
            validation = json.loads(response.content)
            
            # Filter and update URLs
            validated_urls = []
            excluded_urls = []
            
            for url_info in urls:
                validated_data = next(
                    (v for v in validation["validated_urls"] if v["url"] == url_info.url),
                    None
                )
                
                if validated_data:
                    # Only include high relevance URLs, or medium if we have very few
                    if validated_data["relevance"] == "high" or (
                        validated_data["relevance"] == "medium" and 
                        len([v for v in validation["validated_urls"] if v["relevance"] == "high"]) < 3
                    ):
                        if validated_data.get("include", False):
                            url_info.relevance = validated_data["relevance"]
                            url_info.validated = True
                            url_info.validation_reason = validated_data["reason"]
                            validated_urls.append(url_info)
                        else:
                            excluded_urls.append({
                                "url": url_info.url,
                                "reason": validated_data["reason"]
                            })
                    else:
                        excluded_urls.append({
                            "url": url_info.url,
                            "reason": f"Relevance too low: {validated_data['relevance']}"
                        })
                        
            state["urls"] = validated_urls
            state["urls_validated"] = True
            state["phase"] = WorkflowPhase.SCHEMA_DEFINITION
            
            # Create detailed response message
            message_parts = [
                f"Found {len(urls)} URLs. After analysis, {len(validated_urls)} URLs directly match your request"
            ]
            
            if extracted_entities.get("locations"):
                message_parts.append(f"for {', '.join(extracted_entities['locations'])}")
            
            if extracted_entities.get("data_type"):
                message_parts.append(f"{extracted_entities['data_type']} data")
            
            message_parts.append(":\n\n**Selected URLs:**")
            
            for url in validated_urls[:5]:  # Show first 5
                message_parts.append(f"✅ {url.url} - {url.validation_reason}")
            
            if len(validated_urls) > 5:
                message_parts.append(f"... and {len(validated_urls) - 5} more relevant URLs")
            
            if excluded_urls:
                message_parts.append(f"\n**Excluded {len(excluded_urls)} URLs** (not specific enough for your request)")
                if validation.get("excluded_reasons"):
                    message_parts.append("Common reasons: " + ", ".join(validation["excluded_reasons"][:3]))
            
            state["messages"].append(AIMessage(
                content=" ".join(message_parts)
            ))
            
            # Request approval if we filtered out many URLs
            if len(validated_urls) < 3 or len(validated_urls) < len(urls) * 0.3:
                state["requires_approval"] = True
                state["messages"].append(AIMessage(
                    content="🤔 I found fewer specific URLs than expected. Would you like me to include more general pages, or shall we proceed with these specific ones?"
                ))
                
        except Exception as e:
            state["errors"].append(f"URL validation failed: {str(e)}")
            state["phase"] = WorkflowPhase.ERROR
            
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def define_schema(self, state: AgentState) -> AgentState:
        """Define the data extraction schema."""
        urls = state["urls"]
        user_request = state["user_request"]
        
        # Generate schema suggestions
        url_list = "\n".join([f"- {url.url}" for url in urls[:3]])
        
        schema_prompt = f"""Based on the request: "{user_request}"
        And these URLs:
{url_list}

Define a data extraction schema with appropriate fields.
Consider the type of data likely available on these sites.

Respond in JSON format:
{{
    "schema_fields": [
        {{
            "name": "field_name",
            "type": "str|int|float|bool|list",
            "description": "what this field contains",
            "required": boolean,
            "example": "example value"
        }}
    ]
}}"""

        response = await self.llm.ainvoke([HumanMessage(content=schema_prompt)])
        
        try:
            schema_data = json.loads(response.content)
            
            schema_fields = []
            for field in schema_data["schema_fields"]:
                schema_fields.append(SchemaField(**field))
                
            state["schema_fields"] = schema_fields
            state["phase"] = WorkflowPhase.SCHEMA_VALIDATION
            
            state["messages"].append(AIMessage(
                content=f"I've defined a schema with {len(schema_fields)} fields for data extraction."
            ))
            
        except Exception as e:
            state["errors"].append(f"Schema definition failed: {str(e)}")
            state["phase"] = WorkflowPhase.ERROR
            
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def validate_schema(self, state: AgentState) -> AgentState:
        """Validate the schema completeness."""
        schema_fields = state["schema_fields"]
        
        if len(schema_fields) < 2:
            state["schema_validated"] = False
            state["messages"].append(AIMessage(
                content="The schema seems too simple. Let me add more fields."
            ))
        else:
            state["schema_validated"] = True
            state["phase"] = WorkflowPhase.CODE_GENERATION
            
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def generate_code(self, state: AgentState) -> AgentState:
        """Generate the SmartScraper code."""
        urls = [url.url for url in state["urls"]]
        schema_dict = {field.name: field.type for field in state["schema_fields"]}
        
        # Generate code using the helper method
        code = self._generate_smartscraper_code(urls, schema_dict, state["user_request"])
        
        state["generated_code"] = code
        state["phase"] = WorkflowPhase.READY_TO_EXECUTE
        state["requires_approval"] = True
        
        state["messages"].append(AIMessage(
            content="I've generated the SmartScraper code. Please review it before execution."
        ))
        
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def await_approval(self, state: AgentState) -> AgentState:
        """Wait for user approval (placeholder for frontend interaction)."""
        # In real implementation, this would pause and wait for user input
        # For now, we'll auto-approve
        state["approval_status"] = "approved"
        state["requires_approval"] = False
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def execute_pipeline(self, state: AgentState) -> AgentState:
        """Execute the generated code (placeholder)."""
        state["phase"] = WorkflowPhase.COMPLETED
        state["messages"].append(AIMessage(
            content="Pipeline execution completed successfully!"
        ))
        state["updated_at"] = datetime.utcnow()
        return state
    
    async def handle_error(self, state: AgentState) -> AgentState:
        """Handle errors in the workflow."""
        error_msg = "; ".join(state["errors"]) if state["errors"] else "Unknown error occurred"
        state["messages"].append(AIMessage(
            content=f"I encountered an error: {error_msg}. Let's try a different approach."
        ))
        state["phase"] = WorkflowPhase.ERROR
        state["updated_at"] = datetime.utcnow()
        return state
    
    def route_after_analysis(self, state: AgentState) -> str:
        """Route after analyzing the request."""
        if state["phase"] == WorkflowPhase.ERROR:
            return "error"
        elif state["urls"]:
            return "validate_urls"
        elif state["phase"] == WorkflowPhase.URL_COLLECTION:
            return "collect_urls"
        elif state["phase"] == WorkflowPhase.SCHEMA_DEFINITION:
            return "define_schema"
        else:
            return "collect_urls"
    
    def route_after_approval(self, state: AgentState) -> str:
        """Route after approval gate."""
        if state["approval_status"] == "approved":
            return "continue"
        elif state["approval_status"] == "rejected":
            return "reject"
        else:
            return "timeout"
    
    def route_code_approval(self, state: AgentState) -> str:
        """Route after code generation approval."""
        if state["approval_status"] == "approved":
            return "execute"
        elif state["approval_status"] == "rejected":
            return "regenerate"
        else:
            return "end"
    
    def _generate_smartscraper_code(self, urls: List[str], schema: Dict[str, str], description: str) -> str:
        """Generate SmartScraper code (reused from previous implementation)."""
        # Convert schema to Pydantic model fields
        schema_fields = []
        for field_name, field_type in schema.items():
            type_mapping = {
                'str': 'str',
                'string': 'str',
                'int': 'int',
                'integer': 'int',
                'float': 'float',
                'bool': 'bool',
                'boolean': 'bool',
                'list': 'List[str]',
                'dict': 'Dict[str, Any]'
            }
            python_type = type_mapping.get(field_type.lower(), 'str')
            
            if python_type not in ['List[str]', 'Dict[str, Any]']:
                python_type = f"Optional[{python_type}]"
            
            field_desc = field_name.replace('_', ' ').title()
            schema_fields.append(f"    {field_name}: {python_type} = Field(description=\"{field_desc}\")")
        
        code = f'''import asyncio
from scrapegraph_py import AsyncClient
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import json

# Define the data schema
class {description.replace(' ', '')}Schema(BaseModel):
    """Schema for extracting {description.lower()} data."""
{chr(10).join(schema_fields)}

async def scrape_{description.lower().replace(' ', '_')}(urls: List[str], api_key: str):
    """Scrape {description.lower()} from provided URLs using SmartScraper API."""
    async with AsyncClient(api_key=api_key) as client:
        tasks = []
        for url in urls:
            task = client.smartscraper(
                website_url=url,
                user_prompt="Extract {description.lower()} including: {', '.join(schema.keys())}",
                output_schema={description.replace(' ', '')}Schema
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        scraped_data = []
        errors = []
        
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                error_msg = f"Error scraping {{urls[idx]}}: {{str(result)}}"
                print(error_msg)
                errors.append(error_msg)
            else:
                scraped_data.append({{
                    "url": urls[idx],
                    "data": result.model_dump() if hasattr(result, 'model_dump') else result,
                    "success": True
                }})
        
        return {{
            "scraped_data": scraped_data,
            "errors": errors,
            "total_success": len(scraped_data),
            "total_failed": len(errors)
        }}

if __name__ == "__main__":
    urls = {json.dumps(urls, indent=8)}
    
    api_key = "your-scrapegraph-api-key"  # Replace with your actual API key
    
    results = asyncio.run(scrape_{description.lower().replace(' ', '_')}(urls, api_key))
    
    print(f"\\nSuccessfully scraped: {{results['total_success']}} URLs")
    print(f"Failed: {{results['total_failed']}} URLs\\n")
    
    for item in results['scraped_data']:
        print(f"\\n{'='*50}")
        print(f"URL: {{item['url']}}")
        print(f"Data: {{json.dumps(item['data'], indent=2)}}")
'''
        return code
    
    async def process_message(
        self, 
        message: str, 
        pipeline_id: str, 
        thread_id: Optional[str] = None
    ) -> Dict:
        """Process a message through the LangGraph workflow."""
        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "pipeline_id": pipeline_id,
            "user_request": message,
            "phase": WorkflowPhase.INITIAL,
            "urls": [],
            "urls_validated": False,
            "schema_fields": [],
            "schema_validated": False,
            "generated_code": "",
            "execution_results": [],
            "requires_approval": False,
            "approval_status": None,
            "errors": [],
            "extracted_entities": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Configure thread
        config = {"configurable": {"thread_id": thread_id or pipeline_id}}
        
        # Run the graph
        try:
            result = await self.graph.ainvoke(initial_state, config)
            
            # Extract response
            last_ai_message = next(
                (msg for msg in reversed(result["messages"]) if isinstance(msg, AIMessage)),
                None
            )
            
            return {
                "response": last_ai_message.content if last_ai_message else "Processing complete",
                "phase": result["phase"].value,
                "urls": [url.dict() for url in result["urls"]],
                "schema": {field.name: field.type for field in result["schema_fields"]},
                "code": result["generated_code"],
                "results": result["execution_results"],
                "requires_approval": result["requires_approval"],
                "errors": result["errors"]
            }
            
        except Exception as e:
            return {
                "response": f"Error processing request: {str(e)}",
                "phase": WorkflowPhase.ERROR.value,
                "urls": [],
                "schema": {},
                "code": "",
                "results": [],
                "requires_approval": False,
                "errors": [str(e)]
            }