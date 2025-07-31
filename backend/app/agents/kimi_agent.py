from typing import Dict, List, Optional
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain.memory import ConversationBufferMemory
from langchain_core.tools import Tool

from app.config import settings
from app.services.openrouter import get_llm
from app.services.scrapegraph import ScrapingService

class KimiScrapingAgent:
    def __init__(self):
        self.llm = get_llm()
        self.scraping_service = ScrapingService(settings.SCRAPEGRAPH_API_KEY)
        self.memory = ConversationBufferMemory(return_messages=True)
        self.agent_executor = self._create_agent()
    
    def _create_agent(self):
        """Create the LangChain agent with tools."""
        
        # Define tools
        tools = [
            Tool(
                name="add_url",
                description="Add a URL to the scraping pipeline. Use this when the user wants to add a website to scrape.",
                func=self._add_url_tool
            ),
            Tool(
                name="list_urls",
                description="List all URLs in the current pipeline.",
                func=self._list_urls_tool
            ),
            Tool(
                name="define_schema",
                description="Define or update the data extraction schema. Use when user wants to specify what data to extract.",
                func=self._define_schema_tool
            ),
            Tool(
                name="generate_code",
                description="Generate Python code for the scraping pipeline.",
                func=self._generate_code_tool
            ),
            Tool(
                name="validate_url",
                description="Check if a URL is valid and accessible.",
                func=self._validate_url_tool
            )
        ]
        
        # Create prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are ScrapeCraft AI, an expert assistant for building web scraping pipelines using ScrapeGraphAI.

Your role is to help users:
1. Add and manage URLs they want to scrape
2. Define data schemas (what information to extract)
3. Generate Python code using the scrapegraph_py library
4. Execute scraping pipelines

Current pipeline state:
URLs: {urls}
Schema: {schema}

Be helpful, concise, and guide users through the scraping process. When users want to add URLs or define schemas, use the appropriate tools.
Always explain what you're doing and provide clear next steps."""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Create agent
        agent = create_openai_tools_agent(self.llm, tools, prompt)
        
        # Create executor
        return AgentExecutor(
            agent=agent,
            tools=tools,
            memory=self.memory,
            verbose=True,
            handle_parsing_errors=True
        )
    
    def _add_url_tool(self, url: str) -> str:
        """Tool to add URL to pipeline."""
        # In a real implementation, this would update the pipeline state
        return f"✅ Added URL: {url} to the pipeline"
    
    def _list_urls_tool(self, _: str = "") -> str:
        """Tool to list URLs."""
        # In a real implementation, this would fetch from pipeline state
        return "📋 Current URLs in pipeline: (none added yet)"
    
    def _define_schema_tool(self, schema_description: str) -> str:
        """Tool to define schema."""
        return f"📝 Schema defined: {schema_description}"
    
    def _generate_code_tool(self, _: str = "") -> str:
        """Tool to generate code."""
        code = '''import asyncio
from scrapegraph_py import AsyncClient

async def scrape_data():
    """Scrape data from configured URLs."""
    urls = []  # Add your URLs here
    
    async with AsyncClient(api_key="YOUR_API_KEY") as client:
        results = []
        for url in urls:
            result = await client.smartscraper(
                website_url=url,
                user_prompt="Extract the data according to schema"
            )
            results.append(result)
    
    return results

if __name__ == "__main__":
    data = asyncio.run(scrape_data())
    print(data)
'''
        return f"✅ Generated Python code:\n```python\n{code}\n```"
    
    def _validate_url_tool(self, url: str) -> str:
        """Tool to validate URL."""
        # Simple validation
        if url.startswith(('http://', 'https://')):
            return f"✅ URL {url} is valid"
        return f"❌ Invalid URL: {url}. URLs must start with http:// or https://"
    
    async def process_message(self, message: str, pipeline_id: str, context: Dict = None) -> Dict:
        """Process a user message using the Kimi-k2 model."""
        if context is None:
            context = {"urls": [], "schema": {}, "generated_code": ""}
        
        try:
            # Run the agent
            result = await self.agent_executor.ainvoke({
                "input": message,
                "urls": context.get("urls", []),
                "schema": context.get("schema", {})
            })
            
            response = result.get("output", "I'm here to help you build your scraping pipeline!")
            
            # Extract any state updates from the conversation
            # In a real implementation, this would parse tool outputs
            
            return {
                "response": response,
                "urls": context.get("urls", []),
                "schema": context.get("schema", {}),
                "code": context.get("generated_code", ""),
                "results": [],
                "status": "idle",
                "error": None
            }
            
        except Exception as e:
            return {
                "response": f"I encountered an error: {str(e)}. Please try again.",
                "urls": context.get("urls", []),
                "schema": context.get("schema", {}),
                "code": context.get("generated_code", ""),
                "results": [],
                "status": "error",
                "error": str(e)
            }

# Create singleton instance
kimi_agent = KimiScrapingAgent()