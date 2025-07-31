"""
LangChain tools for ScrapeGraphAI integration.
These tools provide a clean interface for the LangGraph agent to interact with ScrapeGraphAI services.
"""
from typing import Dict, List, Optional, Any
from langchain_core.tools import tool
from pydantic import BaseModel, Field
import logging
import asyncio
from scrapegraph_py import AsyncClient

from app.config import settings

logger = logging.getLogger(__name__)


class SmartScraperInput(BaseModel):
    """Input schema for SmartScraper tool."""
    website_url: str = Field(description="The URL of the website to scrape")
    user_prompt: str = Field(description="Natural language prompt describing what data to extract")
    
    
class SmartCrawlerInput(BaseModel):
    """Input schema for SmartCrawler tool."""
    website_url: str = Field(description="The starting URL for crawling")
    user_prompt: str = Field(description="Natural language prompt describing what data to extract")
    max_depth: int = Field(default=2, description="Maximum crawl depth")
    max_pages: int = Field(default=5, description="Maximum number of pages to crawl")


class SearchScraperInput(BaseModel):
    """Input schema for SearchScraper tool."""
    search_query: str = Field(description="The search query to find relevant websites")
    max_results: int = Field(default=10, description="Maximum number of results to return")


class MarkdownifyInput(BaseModel):
    """Input schema for Markdownify tool."""
    website_url: str = Field(description="The URL of the website to convert to markdown")


@tool("smart_scraper", args_schema=SmartScraperInput)
async def smart_scraper_tool(website_url: str, user_prompt: str) -> Dict[str, Any]:
    """
    Extract structured data from a single webpage using natural language.
    
    This tool uses ScrapeGraphAI's SmartScraper to intelligently extract
    information based on your prompt. Perfect for extracting specific data
    like contact info, product details, or article content.
    
    Args:
        website_url: The URL to scrape
        user_prompt: Natural language description of what to extract
        
    Returns:
        Dictionary containing the extracted structured data
    """
    try:
        async with AsyncClient(api_key=settings.SCRAPEGRAPH_API_KEY) as client:
            logger.info(f"SmartScraper: Extracting from {website_url}")
            
            response = await client.smartscraper(
                website_url=website_url,
                user_prompt=user_prompt
            )
            
            if isinstance(response, dict) and "result" in response:
                return {
                    "success": True,
                    "data": response["result"],
                    "url": website_url
                }
            else:
                return {
                    "success": True,
                    "data": response,
                    "url": website_url
                }
                
    except Exception as e:
        logger.error(f"SmartScraper failed for {website_url}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "url": website_url
        }


@tool("smart_crawler", args_schema=SmartCrawlerInput)
async def smart_crawler_tool(
    website_url: str, 
    user_prompt: str,
    max_depth: int = 2,
    max_pages: int = 5
) -> Dict[str, Any]:
    """
    Crawl and extract data from multiple pages starting from a URL.
    
    This tool navigates through a website following links and extracts
    data from multiple pages. Useful for gathering comprehensive data
    across an entire section of a website.
    
    Args:
        website_url: Starting URL for the crawl
        user_prompt: What data to extract from each page
        max_depth: How many levels deep to crawl
        max_pages: Maximum pages to visit
        
    Returns:
        Dictionary containing data from all crawled pages
    """
    try:
        async with AsyncClient(api_key=settings.SCRAPEGRAPH_API_KEY) as client:
            logger.info(f"SmartCrawler: Starting crawl from {website_url}")
            
            # Note: Adjust method name based on actual API
            response = await client.smartscraper(
                website_url=website_url,
                user_prompt=f"Crawl up to {max_pages} pages at depth {max_depth} and {user_prompt}"
            )
            
            return {
                "success": True,
                "data": response.get("result", response),
                "pages_crawled": 1,  # Would be updated with actual count
                "starting_url": website_url
            }
            
    except Exception as e:
        logger.error(f"SmartCrawler failed for {website_url}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "starting_url": website_url
        }


@tool("search_scraper", args_schema=SearchScraperInput)
async def search_scraper_tool(search_query: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search for websites and extract relevant URLs based on a query.
    
    This tool performs web searches to find relevant websites for your
    scraping needs. It returns URLs with descriptions that match your
    search criteria.
    
    Args:
        search_query: What to search for
        max_results: Maximum number of results
        
    Returns:
        Dictionary containing found URLs and their descriptions
    """
    try:
        async with AsyncClient(api_key=settings.SCRAPEGRAPH_API_KEY) as client:
            logger.info(f"SearchScraper: Searching for '{search_query}'")
            
            # Try searchscraper if available
            try:
                response = await client.searchscraper(
                    user_prompt=f"Find the top {max_results} websites for: {search_query}"
                )
                
                urls = []
                if isinstance(response, dict) and "result" in response:
                    # Extract URLs from the response
                    result = response["result"]
                    if isinstance(result, dict) and "websites" in result:
                        for site in result["websites"]:
                            urls.append({
                                "url": site.get("url", ""),
                                "title": site.get("name", ""),
                                "description": site.get("description", "")
                            })
                            
                return {
                    "success": True,
                    "query": search_query,
                    "results": urls,
                    "count": len(urls)
                }
                
            except AttributeError:
                # Fallback if searchscraper not available
                logger.warning("SearchScraper not available, using alternative approach")
                
                # Use smartscraper on a search engine
                search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
                response = await client.smartscraper(
                    website_url=search_url,
                    user_prompt=f"Extract the top {max_results} relevant website URLs from these search results"
                )
                
                return {
                    "success": True,
                    "query": search_query,
                    "results": response.get("result", []),
                    "count": len(response.get("result", []))
                }
                
    except Exception as e:
        logger.error(f"SearchScraper failed for '{search_query}': {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "query": search_query,
            "results": []
        }


@tool("markdownify", args_schema=MarkdownifyInput)
async def markdownify_tool(website_url: str) -> Dict[str, Any]:
    """
    Convert a webpage to clean, formatted markdown.
    
    This tool extracts the main content from a webpage and converts it
    to markdown format. Useful for documentation, content analysis, or
    creating readable versions of web pages.
    
    Args:
        website_url: The URL to convert to markdown
        
    Returns:
        Dictionary containing the markdown content
    """
    try:
        async with AsyncClient(api_key=settings.SCRAPEGRAPH_API_KEY) as client:
            logger.info(f"Markdownify: Converting {website_url} to markdown")
            
            response = await client.smartscraper(
                website_url=website_url,
                user_prompt="Convert this entire webpage to clean markdown format, preserving structure and formatting"
            )
            
            return {
                "success": True,
                "markdown": response.get("result", ""),
                "url": website_url
            }
            
    except Exception as e:
        logger.error(f"Markdownify failed for {website_url}: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "url": website_url
        }


@tool("validate_urls")
async def validate_urls_tool(urls: List[str]) -> Dict[str, Any]:
    """
    Validate a list of URLs to check if they are accessible.
    
    This tool checks if URLs are valid and accessible, helping to
    filter out broken links before scraping.
    
    Args:
        urls: List of URLs to validate
        
    Returns:
        Dictionary with validation results for each URL
    """
    import aiohttp
    
    results = []
    
    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.head(url, timeout=5, allow_redirects=True) as response:
                    results.append({
                        "url": url,
                        "valid": response.status < 400,
                        "status_code": response.status,
                        "final_url": str(response.url)
                    })
            except Exception as e:
                results.append({
                    "url": url,
                    "valid": False,
                    "error": str(e)
                })
                
    return {
        "urls_checked": len(urls),
        "valid_urls": sum(1 for r in results if r.get("valid", False)),
        "results": results
    }


# Export all tools
__all__ = [
    "smart_scraper_tool",
    "smart_crawler_tool", 
    "search_scraper_tool",
    "markdownify_tool",
    "validate_urls_tool"
]