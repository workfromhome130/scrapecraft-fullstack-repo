from typing import Dict, List, Optional
import json
import re
import asyncio
from datetime import datetime
from app.config import settings
from app.services.openrouter import get_llm
from app.services.scrapegraph import ScrapingService

class OpenRouterAgent:
    def __init__(self):
        self.llm = get_llm()
        self.scraping_service = ScrapingService(settings.SCRAPEGRAPH_API_KEY)
        # Store conversation history per pipeline
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.system_prompt = """You are ScrapeCraft AI, an expert assistant for building web scraping pipelines using ScrapeGraphAI's SmartScraper API.

Your capabilities:
1. Help users add URLs to scrape - ALWAYS search for proper URLs using search functionality
2. Define data extraction schemas using Pydantic models
3. Generate CORRECT Python code using scrapegraph_py SmartScraper API
4. Guide users through the scraping process

IMPORTANT: When users ask to add URLs for a topic (e.g., "Milan weather", "product prices"), 
you MUST search for the actual URLs using the search functionality. Never make up or guess URLs.

When generating scraping code, ALWAYS use this correct SmartScraper API pattern:

```python
import asyncio
from scrapegraph_py import AsyncClient
from pydantic import BaseModel, Field
from typing import Optional, List

# Define schema based on user requirements
class DataSchema(BaseModel):
    # Add fields based on what user wants to extract
    field1: str = Field(description="Description of field1")
    field2: Optional[str] = Field(description="Description of field2")
    # ... more fields as needed

async def scrape_data(urls: List[str], api_key: str):
    \"\"\"Scrape data from provided URLs using SmartScraper API.\"\"\"
    async with AsyncClient(api_key=api_key) as client:
        tasks = []
        for url in urls:
            task = client.smartscraper(
                website_url=url,
                user_prompt="Extract [specific data user wants]",
                output_schema=DataSchema  # Use the defined schema
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        scraped_data = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error scraping {urls[idx]}: {result}")
            else:
                scraped_data.append({
                    "url": urls[idx],
                    "data": result
                })
        
        return scraped_data

# Main execution
if __name__ == "__main__":
    urls = ["url1", "url2"]  # Will be replaced with actual URLs
    api_key = "your-scrapegraph-api-key"  # Will be replaced with actual key
    
    results = asyncio.run(scrape_data(urls, api_key))
    
    # Display results
    for result in results:
        print(f"\\nData from {result['url']}:")
        print(result['data'])
```

REMEMBER:
- Always use AsyncClient for better performance
- Always define a Pydantic schema for structured output
- Always handle errors gracefully with try-except or gather with return_exceptions=True
- Always use descriptive Field descriptions in the schema
- Always make the user_prompt specific to what needs to be extracted

Be helpful, concise, and professional. Use emojis sparingly for clarity."""
    
    def _get_conversation_history(self, pipeline_id: str) -> List[Dict]:
        """Get conversation history for a pipeline."""
        return self.conversation_history.get(pipeline_id, [])
    
    def _add_to_history(self, pipeline_id: str, role: str, content: str):
        """Add a message to conversation history."""
        if pipeline_id not in self.conversation_history:
            self.conversation_history[pipeline_id] = []
        
        self.conversation_history[pipeline_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only last 20 messages to prevent context from getting too large
        if len(self.conversation_history[pipeline_id]) > 20:
            self.conversation_history[pipeline_id] = self.conversation_history[pipeline_id][-20:]
    
    def clear_conversation_history(self, pipeline_id: str):
        """Clear conversation history for a pipeline."""
        if pipeline_id in self.conversation_history:
            del self.conversation_history[pipeline_id]
    
    def _format_conversation_for_context(self, pipeline_id: str, limit: int = 10) -> str:
        """Format recent conversation history for context."""
        history = self._get_conversation_history(pipeline_id)
        recent_history = history[-limit:] if len(history) > limit else history
        
        if not recent_history:
            return "No previous conversation."
        
        formatted = "Recent conversation history:\n"
        for msg in recent_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            formatted += f"{role}: {msg['content'][:200]}...\n" if len(msg['content']) > 200 else f"{role}: {msg['content']}\n"
        
        return formatted
    
    async def process_message(self, message: str, pipeline_id: str, context: Dict = None) -> Dict:
        """Process a user message using the Kimi-k2 model."""
        if context is None:
            context = {"urls": [], "schema": {}, "generated_code": ""}
        
        try:
            # Add user message to history
            self._add_to_history(pipeline_id, "user", message)
            
            # First, let AI analyze the user's intent with conversation context
            intent = await self._analyze_intent(message, context, pipeline_id)
            
            # Handle based on intent
            result = None
            if intent.get("needs_url_search"):
                # User wants to find URLs for a topic
                search_query = intent.get("search_query", message)
                result = await self._handle_url_search(search_query, context, message)
            elif intent.get("has_direct_urls"):
                # User provided direct URLs
                result = await self._handle_direct_urls(message, context, intent.get("urls", []))
            else:
                # General conversation about schema, code generation, etc.
                result = await self._handle_general_message(message, context, pipeline_id)
            
            # Add assistant response to history
            if result:
                self._add_to_history(pipeline_id, "assistant", result["response"])
            
            return result
            
        except Exception as e:
            return {
                "response": f"I encountered an error: {str(e)}. Please make sure your OpenRouter API key is set correctly.",
                "urls": context.get("urls", []),
                "schema": context.get("schema", {}),
                "code": context.get("generated_code", ""),
                "results": [],
                "status": "error",
                "error": str(e)
            }
    
    def _parse_actions(self, response: str, context: Dict) -> Dict:
        """Parse the AI response for actions to update context."""
        updated_context = context.copy()
        
        # Check if AI is adding URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+[^\s<>"{}|\\^`\[\].,;:!?]'
        urls_found = re.findall(url_pattern, response.lower())
        
        for url in urls_found:
            if url not in updated_context["urls"] and ("add" in response.lower() or "added" in response.lower()):
                updated_context["urls"].append(url)
        
        # Check if AI is defining schema
        if "schema" in response.lower() and ("field" in response.lower() or "extract" in response.lower()):
            # Try to extract field definitions
            field_pattern = r'(?:field|extract|get):\s*(\w+)\s*(?:\(|:|-)?\s*(?:type:)?\s*(str|string|int|integer|float|bool|boolean|list)?'
            fields = re.findall(field_pattern, response.lower())
            
            for field_name, field_type in fields:
                if field_name and field_name not in updated_context.get("schema", {}):
                    type_map = {
                        'str': 'str', 'string': 'str',
                        'int': 'int', 'integer': 'int',
                        'float': 'float',
                        'bool': 'bool', 'boolean': 'bool',
                        'list': 'list'
                    }
                    updated_context.setdefault("schema", {})[field_name] = type_map.get(field_type, 'str')
        
        # Check if code is being generated
        if "```python" in response:
            code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
            if code_match:
                updated_context["generated_code"] = code_match.group(1)
        
        return updated_context
    
    async def _analyze_intent(self, message: str, context: Dict, pipeline_id: str = None) -> Dict:
        """Use AI to analyze user intent and determine action needed."""
        # Get conversation history for better context understanding
        conversation_context = ""
        if pipeline_id:
            conversation_context = self._format_conversation_for_context(pipeline_id, limit=5)
        
        intent_prompt = f"""Analyze this user message and determine their intent for a web scraping pipeline.

{conversation_context}

Current user message: "{message}"

Current pipeline state:
- URLs in pipeline: {len(context.get('urls', []))}
- Schema defined: {'Yes' if context.get('schema') else 'No'}

Determine:
1. Does the user want to search for URLs about a topic? (needs_url_search: true/false)
2. If yes, what should we search for? (search_query: "...")
3. Did the user provide direct URLs? (has_direct_urls: true/false)
4. If yes, extract the URLs (urls: [...])
5. What is the main intent? (intent: "add_urls" | "define_schema" | "generate_code" | "ask_question" | "run_pipeline")

Respond in JSON format:
{{
    "needs_url_search": boolean,
    "search_query": "string or null",
    "has_direct_urls": boolean,
    "urls": ["list of URLs if found"],
    "intent": "string",
    "topic": "what they want to scrape"
}}"""

        try:
            messages = [
                {"role": "system", "content": "You are an intent analyzer. Respond only in valid JSON."},
                {"role": "user", "content": intent_prompt}
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            import json
            intent_data = json.loads(response.content.strip())
            return intent_data
            
        except Exception as e:
            # Fallback to simple detection if AI fails
            return {
                "needs_url_search": self._simple_url_search_check(message),
                "search_query": message,
                "has_direct_urls": bool(re.search(r'https?://[^\s<>"{}|\\^`\[\]]+', message)),
                "urls": re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', message),
                "intent": "add_urls",
                "topic": "general"
            }
    
    def _simple_url_search_check(self, message: str) -> bool:
        """Simple fallback check for URL search intent."""
        message_lower = message.lower()
        
        # Check if message seems to be about finding/adding content but has no URLs
        has_direct_url = bool(re.search(r'https?://[^\s<>"{}|\\^`\[\]]+', message))
        
        # Keywords suggesting they want to scrape something
        scrape_keywords = ["scrape", "extract", "get data", "pipeline", "build", "create", "want", "need"]
        has_scrape_intent = any(keyword in message_lower for keyword in scrape_keywords)
        
        return has_scrape_intent and not has_direct_url
    
    async def _analyze_url_relevance(self, urls: List[tuple], search_query: str, user_prompt: str) -> List[tuple]:
        """Use AI to analyze and filter URLs based on relevance to the user's prompt."""
        try:
            # Prepare URL information for analysis
            url_info = "\n".join([f"{i+1}. URL: {url}\n   Description: {desc}" 
                                for i, (url, desc) in enumerate(urls)])
            
            analysis_prompt = f"""Analyze these URLs found for "{search_query}" and determine which are most relevant.

User's original request: "{user_prompt}"
Search query used: "{search_query}"

Found URLs:
{url_info}

For each URL, determine:
1. How relevant is it to the user's request? (high/medium/low)
2. Why is it relevant or not?
3. Should it be included? (yes/no)

Consider:
- Does the URL match the specific topic requested?
- Is it from a reliable source for this type of data?
- Does it contain the type of information the user wants to extract?

Respond in JSON format:
{{
    "analyzed_urls": [
        {{
            "url": "url1",
            "relevance": "high|medium|low",
            "reason": "explanation",
            "include": true|false
        }}
    ],
    "summary": "Brief explanation of filtering decisions"
}}"""

            messages = [
                {"role": "system", "content": "You are an expert at analyzing URL relevance for web scraping tasks."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse the analysis
            try:
                import json
                analysis = json.loads(response.content.strip())
                
                # Filter URLs based on analysis
                filtered_urls = []
                for i, (url, desc) in enumerate(urls):
                    # Find analysis for this URL
                    url_analysis = next((a for a in analysis.get("analyzed_urls", []) 
                                       if a["url"] in url), None)
                    
                    if url_analysis and url_analysis.get("include", True):
                        # Add relevance info to description
                        enhanced_desc = f"{desc} [Relevance: {url_analysis.get('relevance', 'unknown')}]"
                        filtered_urls.append((url, enhanced_desc))
                    elif not url_analysis:
                        # If not analyzed, include by default
                        filtered_urls.append((url, desc))
                
                return filtered_urls
                
            except json.JSONDecodeError:
                # If parsing fails, return all URLs
                return urls
                
        except Exception as e:
            # On any error, return all URLs unfiltered
            print(f"Error analyzing URL relevance: {e}")
            return urls
    
    async def _handle_url_search(self, search_query: str, context: Dict, original_message: str) -> Dict:
        """Handle URL search requests using AI-determined search query."""
        try:
            # Search for URLs using ScrapeGraphAI (get more results for better filtering)
            search_results = await self.scraping_service.search_urls(search_query, max_results=10)
            
            # Process search results
            if search_results:
                # First collect all found URLs
                found_urls = []
                for result in search_results:
                    if isinstance(result, dict):
                        url = result.get('url', '')
                        desc = result.get('description', '')
                    else:
                        url = str(result)
                        desc = ''
                    
                    if url:
                        found_urls.append((url, desc))
                
                # Analyze and filter URLs based on relevance
                filtered_urls = await self._analyze_url_relevance(
                    found_urls, 
                    search_query, 
                    original_message
                )
                
                # Now add the filtered URLs
                updated_urls = list(context.get("urls", []))
                added_urls = []
                
                for url, desc in filtered_urls:
                    if url not in updated_urls:
                        updated_urls.append(url)
                        added_urls.append((url, desc))
                
                # Create response
                if added_urls:
                    total_found = len(found_urls)
                    total_added = len(added_urls)
                    
                    response = f"I searched for '{search_query}' and found {total_found} URLs. "
                    if total_found > total_added:
                        response += f"After analyzing relevance, I selected the {total_added} most relevant ones:\n\n"
                    else:
                        response += f"All found URLs are relevant to your request:\n\n"
                    
                    for i, (url, desc) in enumerate(added_urls, 1):
                        response += f"{i}. {url}\n"
                        if desc:
                            response += f"   {desc}\n"
                    
                    if total_found > total_added:
                        response += f"\n🔍 Filtered out {total_found - total_added} less relevant URLs to ensure quality results."
                    
                    response += f"\n✅ Added {len(added_urls)} URLs to your pipeline.\n\n"
                    
                    # Automatically suggest schema definition with AI
                    response += "**Next Step: Define Your Data Schema**\n\n"
                    response += f"Now let's define what data you want to extract from these {search_query} websites.\n\n"
                    
                    # Use AI to suggest relevant schema fields
                    schema_suggestions = await self._generate_schema_suggestions(search_query, added_urls)
                    response += schema_suggestions
                else:
                    response = f"All found URLs for '{search_query}' are already in your pipeline."
            else:
                response = f"I couldn't find any URLs for '{search_query}'. Please try a different search term or provide a direct URL."
                updated_urls = context.get("urls", [])
            
            return {
                "response": response,
                "urls": updated_urls,
                "schema": context.get("schema", {}),
                "code": context.get("generated_code", ""),
                "results": [],
                "status": "idle",
                "error": None
            }
            
        except Exception as e:
            return {
                "response": f"Error searching for URLs: {str(e)}",
                "urls": context.get("urls", []),
                "schema": context.get("schema", {}),
                "code": context.get("generated_code", ""),
                "results": [],
                "status": "error",
                "error": str(e)
            }
    
    async def _handle_direct_urls(self, message: str, context: Dict, urls: List[str]) -> Dict:
        """Handle messages with direct URLs."""
        updated_urls = list(context.get("urls", []))
        added_urls = []
        
        for url in urls:
            if url not in updated_urls:
                updated_urls.append(url)
                added_urls.append(url)
        
        if added_urls:
            response = f"✅ Added {len(added_urls)} URL(s) to your pipeline:\n\n"
            for i, url in enumerate(added_urls, 1):
                response += f"{i}. {url}\n"
            
            # Automatically suggest schema definition with AI
            response += "\n**Next Step: Define Your Data Schema**\n\n"
            response += "Now let's define what data you want to extract from these websites.\n\n"
            
            # Try to infer topic from URLs
            topic = "the content from these websites"
            if added_urls:
                # Simple topic inference from URL patterns
                url_text = " ".join(added_urls).lower()
                if "weather" in url_text or "wind" in url_text:
                    topic = "weather and wind data"
                elif "product" in url_text or "shop" in url_text:
                    topic = "product information"
                elif "news" in url_text or "article" in url_text:
                    topic = "news articles"
            
            # Use AI to suggest relevant schema fields
            url_tuples = [(url, "") for url in added_urls]
            schema_suggestions = await self._generate_schema_suggestions(topic, url_tuples)
            response += schema_suggestions
        else:
            response = "All provided URLs are already in your pipeline."
        
        return {
            "response": response,
            "urls": updated_urls,
            "schema": context.get("schema", {}),
            "code": context.get("generated_code", ""),
            "results": [],
            "status": "idle",
            "error": None
        }
    
    def _generate_smartscraper_code(self, urls: List[str], schema: Dict[str, str], description: str = "") -> str:
        """Generate correct SmartScraper API code based on schema and URLs."""
        # Convert schema to Pydantic model fields
        schema_fields = []
        for field_name, field_type in schema.items():
            # Convert simple types to Python types
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
            
            # Make fields optional by default for flexibility
            if python_type not in ['List[str]', 'Dict[str, Any]']:
                python_type = f"Optional[{python_type}]"
            
            field_desc = field_name.replace('_', ' ').title()
            schema_fields.append(f"    {field_name}: {python_type} = Field(description=\"{field_desc}\")")
        
        # Build the complete code
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
        
        # Execute all scraping tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process and structure results
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

# Main execution
if __name__ == "__main__":
    # URLs to scrape
    urls = {json.dumps(urls, indent=8)}
    
    # Your ScrapeGraphAI API key
    api_key = "your-scrapegraph-api-key"  # Replace with your actual API key
    
    # Run the scraper
    results = asyncio.run(scrape_{description.lower().replace(' ', '_')}(urls, api_key))
    
    # Display results
    print(f"\\nSuccessfully scraped: {{results['total_success']}} URLs")
    print(f"Failed: {{results['total_failed']}} URLs\\n")
    
    for item in results['scraped_data']:
        print(f"\\n{'='*50}")
        print(f"URL: {{item['url']}}")
        print(f"Data: {{json.dumps(item['data'], indent=2)}}")
    
    if results['errors']:
        print(f"\\n{'='*50}")
        print("Errors encountered:")
        for error in results['errors']:
            print(f"- {{error}}")
'''
        return code
    
    async def _generate_schema_suggestions(self, search_query: str, urls: List[tuple]) -> str:
        """Use AI to generate relevant schema field suggestions based on the search topic and URLs."""
        try:
            # Prepare URL info for context
            url_info = "\n".join([f"- {url} ({desc})" for url, desc in urls[:3]])  # Use first 3 URLs
            
            prompt = f"""Based on the search topic "{search_query}" and these URLs:
{url_info}

Suggest relevant data fields that would be useful to extract. 
Be specific to the topic but comprehensive. 
Format your response as a list of fields with their purpose.

For example, if the topic is about weather, suggest fields like wind speed, temperature, etc.
If it's about products, suggest price, availability, etc.
Be smart and context-aware.

Provide 5-8 relevant fields that make sense for this specific topic."""

            messages = [
                {"role": "system", "content": "You are a data extraction expert. Suggest relevant fields for web scraping based on the topic."},
                {"role": "user", "content": prompt}
            ]
            
            response = await self.llm.ainvoke(messages)
            suggestion_text = response.content
            
            # Format the response
            formatted_response = "Based on your search topic, here are some suggested data fields to extract:\n\n"
            formatted_response += suggestion_text
            formatted_response += "\n\nWould you like to use these fields, modify them, or create your own custom schema?"
            
            return formatted_response
            
        except Exception as e:
            # Fallback to generic prompt if AI fails
            return "What specific information would you like to extract from these websites? Please tell me what data fields you need."
    
    async def _handle_general_message(self, message: str, context: Dict, pipeline_id: str = None) -> Dict:
        """Handle general conversation about schema, code generation, etc."""
        # Build messages with conversation history
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add recent conversation history
        if pipeline_id:
            history = self._get_conversation_history(pipeline_id)
            # Include last 5 exchanges (10 messages)
            recent_history = history[-10:] if len(history) > 10 else history
            
            for hist_msg in recent_history[:-1]:  # Exclude the current message we just added
                if hist_msg["role"] == "user":
                    messages.append({"role": "user", "content": hist_msg["content"]})
                elif hist_msg["role"] == "assistant":
                    messages.append({"role": "assistant", "content": hist_msg["content"]})
        
        # Add current context and message
        messages.append({
            "role": "user", 
            "content": f"Current pipeline state:\nURLs: {context['urls']}\nSchema: {context.get('schema', {})}\n\nUser message: {message}"
        })
        
        response = await self.llm.ainvoke(messages)
        ai_response = response.content
        
        # Parse actions from the response
        updated_context = self._parse_actions(ai_response, context)
        
        # If user is asking for code generation and we have URLs and schema, generate SmartScraper code
        if ("generate" in message.lower() and "code" in message.lower()) or "generate code" in ai_response.lower():
            if updated_context.get("urls") and updated_context.get("schema"):
                # Extract description from context or message
                description = "data"
                if "weather" in str(updated_context).lower() or "weather" in message.lower():
                    description = "weather data"
                elif "product" in str(updated_context).lower() or "product" in message.lower():
                    description = "product information"
                elif "news" in str(updated_context).lower() or "news" in message.lower():
                    description = "news articles"
                
                # Generate the SmartScraper code
                generated_code = self._generate_smartscraper_code(
                    urls=updated_context["urls"],
                    schema=updated_context["schema"],
                    description=description
                )
                updated_context["generated_code"] = generated_code
                
                # Add explanation to response
                ai_response += f"\n\n💻 I've generated the SmartScraper code for you! The code:\n"
                ai_response += f"- Uses the AsyncClient for better performance\n"
                ai_response += f"- Defines a Pydantic schema with your fields\n"
                ai_response += f"- Handles errors gracefully\n"
                ai_response += f"- Processes multiple URLs concurrently\n"
                ai_response += f"- Returns structured results\n\n"
                ai_response += f"You can now run this code by clicking the 'Run Pipeline' button!"
        
        return {
            "response": ai_response,
            "urls": updated_context["urls"],
            "schema": updated_context["schema"],
            "code": updated_context.get("generated_code", ""),
            "results": [],
            "status": "idle",
            "error": None
        }

# Create singleton instance
openrouter_agent = OpenRouterAgent()