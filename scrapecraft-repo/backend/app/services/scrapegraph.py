from typing import List, Dict, Optional, Any
import asyncio
from scrapegraph_py import AsyncClient
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class ScrapingService:
    """Service for interacting with ScrapeGraphAI API."""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def execute_pipeline(
        self,
        urls: List[str],
        schema: Optional[Dict[str, Any]],
        prompt: str
    ) -> List[Dict]:
        """Execute scraping for multiple URLs concurrently."""
        results = []
        
        try:
            async with AsyncClient(api_key=self.api_key) as client:
                tasks = []
                
                for url in urls:
                    # Create task for each URL
                    if schema:
                        # Convert schema dict to Pydantic model dynamically
                        schema_model = self._create_pydantic_model(schema)
                        task = client.smartscraper(
                            website_url=url,
                            user_prompt=prompt,
                            output_schema=schema_model
                        )
                    else:
                        task = client.smartscraper(
                            website_url=url,
                            user_prompt=prompt
                        )
                    
                    tasks.append(task)
                
                # Execute all tasks concurrently
                raw_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for i, result in enumerate(raw_results):
                    if isinstance(result, Exception):
                        results.append({
                            "url": urls[i],
                            "success": False,
                            "data": None,
                            "error": str(result)
                        })
                        logger.error(f"Scraping failed for {urls[i]}: {result}")
                    else:
                        results.append({
                            "url": urls[i],
                            "success": True,
                            "data": result,
                            "error": None
                        })
                        logger.info(f"Successfully scraped {urls[i]}")
                
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            # Return error for all URLs
            results = [{
                "url": url,
                "success": False,
                "data": None,
                "error": str(e)
            } for url in urls]
        
        return results
    
    def _create_pydantic_model(self, schema: Dict[str, Any]) -> type[BaseModel]:
        """Dynamically create a Pydantic model from a schema dictionary."""
        from pydantic import create_model
        
        # Convert schema dict to Pydantic field definitions
        field_definitions = {}
        for field_name, field_type in schema.items():
            # Map string type names to Python types
            if isinstance(field_type, str):
                type_mapping = {
                    'str': str,
                    'int': int,
                    'float': float,
                    'bool': bool,
                    'list': list,
                    'dict': dict
                }
                field_type = type_mapping.get(field_type, str)
            
            # Create field with Optional type
            field_definitions[field_name] = (Optional[field_type], None)
        
        # Create and return the model
        return create_model('DynamicSchema', **field_definitions)
    
    async def search_urls(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Search for URLs using ScrapeGraphAI SearchScraper."""
        try:
            async with AsyncClient(api_key=self.api_key) as client:
                # Define schema for structured output
                from pydantic import BaseModel, Field
                from typing import List
                
                class WebsiteInfo(BaseModel):
                    name: str = Field(description="Name of the website")
                    url: str = Field(description="Full URL of the website")
                    description: str = Field(description="Brief description of what the website offers")
                
                class SearchResults(BaseModel):
                    websites: List[WebsiteInfo] = Field(description="List of relevant websites")
                
                # Use searchscraper to find information about the topic
                search_prompt = f"Find the top {max_results} most relevant websites and their URLs for: {query}. Return a list of websites with their URLs and descriptions."
                
                try:
                    # Use searchscraper to find URLs - don't use schema for now
                    result = await client.searchscraper(
                        user_prompt=search_prompt
                    )
                    
                    # Log the result to understand its structure
                    logger.info(f"SearchScraper raw result type: {type(result)}")
                    logger.info(f"SearchScraper raw result: {result}")
                    
                    urls = []
                    
                    # Handle the response - it's a dict when using searchscraper
                    if isinstance(result, dict):
                        # Extract from the result field
                        if 'result' in result and isinstance(result['result'], dict):
                            websites_data = result['result'].get('websites', [])
                            
                            for website in websites_data:
                                if isinstance(website, dict) and 'url' in website:
                                    urls.append({
                                        'url': website['url'],
                                        'description': website.get('description', website.get('name', f'Found via search for: {query}'))
                                    })
                        
                        # Also add reference URLs if they're different
                        if 'reference_urls' in result and result['reference_urls']:
                            for ref_url in result['reference_urls']:
                                if not any(u['url'] == ref_url for u in urls):
                                    urls.append({
                                        'url': ref_url,
                                        'description': f'Reference source for: {query}'
                                    })
                    
                    logger.info(f"Final URLs extracted: {urls}")
                    return urls
                    
                except AttributeError as e:
                    # If searchscraper doesn't exist, try alternative approach
                    logger.warning(f"searchscraper method not found, trying smartscraper: {e}")
                    
                    # Use smartscraper on a search engine
                    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
                    result = await client.smartscraper(
                        website_url=search_url,
                        user_prompt=f"Extract the top {max_results} relevant website URLs from these search results. Return only actual website URLs (not Google URLs)."
                    )
                    
                    urls = []
                    if isinstance(result, dict) and 'result' in result:
                        # Extract URLs from the result
                        import re
                        url_pattern = r'https?://(?!www\.google)[^\s<>"{}|\\^`\[\]]+'
                        found_urls = re.findall(url_pattern, str(result['result']))
                        
                        for url in found_urls[:max_results]:
                            urls.append({
                                'url': url,
                                'description': f'Found via search for: {query}'
                            })
                    
                    return urls
                    
        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}")
            return []
    
    async def validate_api_key(self) -> bool:
        """Validate if the API key is working."""
        try:
            async with AsyncClient(api_key=self.api_key) as client:
                # Try a simple request
                result = await client.smartscraper(
                    website_url="https://example.com",
                    user_prompt="Extract the page title"
                )
                return True
        except Exception as e:
            logger.error(f"API key validation failed: {e}")
            return False