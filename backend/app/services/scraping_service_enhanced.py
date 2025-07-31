"""
Enhanced scraping service with retry logic, timeout handling, and better error management.
"""
from typing import List, Dict, Optional, Any
import asyncio
from datetime import datetime
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_retry,
    after_retry
)
import aiohttp
from scrapegraph_py import AsyncClient
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)


class ScrapingError(Exception):
    """Base exception for scraping errors."""
    pass


class APIError(ScrapingError):
    """API-related errors (500, 503, etc.)."""
    pass


class RateLimitError(ScrapingError):
    """Rate limit exceeded error."""
    pass


class EnhancedScrapingService:
    """Enhanced service for ScrapeGraphAI with retry and error handling."""
    
    def __init__(self, api_key: str, max_retries: int = 3, timeout: int = 30):
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self._client = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = AsyncClient(api_key=self.api_key)
        await self._client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
    
    def _log_retry_attempt(self, retry_state):
        """Log retry attempts."""
        logger.warning(
            f"Retrying {retry_state.fn.__name__} "
            f"(attempt {retry_state.attempt_number}/{self.max_retries})"
        )
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((APIError, aiohttp.ClientError)),
        before=lambda retry_state: logger.warning(f"Retrying after error: {retry_state.outcome.exception()}")
    )
    async def smart_scraper(
        self,
        website_url: str,
        user_prompt: str,
        schema: Optional[type[BaseModel]] = None
    ) -> Dict[str, Any]:
        """
        Execute SmartScraper with retry logic.
        
        Args:
            website_url: URL to scrape
            user_prompt: Natural language prompt
            schema: Optional Pydantic model for structured output
            
        Returns:
            Dictionary with extraction results
        """
        try:
            # Add timeout to the request
            result = await asyncio.wait_for(
                self._client.smartscraper(
                    website_url=website_url,
                    user_prompt=user_prompt,
                    output_schema=schema
                ),
                timeout=self.timeout
            )
            
            logger.info(f"Successfully scraped {website_url}")
            return {
                "success": True,
                "url": website_url,
                "data": result.get("result", result),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except asyncio.TimeoutError:
            logger.error(f"Timeout scraping {website_url} after {self.timeout}s")
            raise ScrapingError(f"Scraping timeout after {self.timeout} seconds")
            
        except Exception as e:
            error_msg = str(e)
            
            # Categorize errors
            if "500" in error_msg or "503" in error_msg:
                raise APIError(f"API server error: {error_msg}")
            elif "429" in error_msg or "rate limit" in error_msg.lower():
                raise RateLimitError(f"Rate limit exceeded: {error_msg}")
            else:
                logger.error(f"Scraping failed for {website_url}: {error_msg}")
                raise ScrapingError(f"Scraping failed: {error_msg}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((APIError, aiohttp.ClientError))
    )
    async def search_urls(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, str]]:
        """
        Search for URLs with retry logic.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of URL dictionaries
        """
        try:
            # Try searchscraper first
            try:
                result = await asyncio.wait_for(
                    self._client.searchscraper(
                        user_prompt=f"Find top {max_results} websites for: {query}"
                    ),
                    timeout=self.timeout
                )
                
                urls = self._parse_search_results(result)
                logger.info(f"Found {len(urls)} URLs for query: {query}")
                return urls
                
            except AttributeError:
                # Fallback to smartscraper on search engine
                logger.warning("SearchScraper not available, using fallback")
                return await self._search_fallback(query, max_results)
                
        except asyncio.TimeoutError:
            logger.error(f"Search timeout for query: {query}")
            return []
            
        except Exception as e:
            error_msg = str(e)
            if "500" in error_msg or "503" in error_msg:
                raise APIError(f"Search API error: {error_msg}")
            else:
                logger.error(f"Search failed for '{query}': {error_msg}")
                return []
    
    async def _search_fallback(self, query: str, max_results: int) -> List[Dict[str, str]]:
        """Fallback search using web scraping."""
        search_url = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
        
        try:
            result = await self.smart_scraper(
                website_url=search_url,
                user_prompt=f"Extract the top {max_results} search result URLs and their descriptions"
            )
            
            if result.get("success") and result.get("data"):
                # Parse the results
                urls = []
                data = result["data"]
                
                if isinstance(data, list):
                    for item in data[:max_results]:
                        if isinstance(item, dict):
                            urls.append({
                                "url": item.get("url", ""),
                                "description": item.get("description", "")
                            })
                            
                return urls
                
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            
        return []
    
    def _parse_search_results(self, response: Dict[str, Any]) -> List[Dict[str, str]]:
        """Parse search results from various response formats."""
        urls = []
        
        if isinstance(response, dict):
            # Check for result field
            if "result" in response:
                result = response["result"]
                
                # Handle websites array
                if isinstance(result, dict) and "websites" in result:
                    for site in result["websites"]:
                        if isinstance(site, dict):
                            urls.append({
                                "url": site.get("url", ""),
                                "description": site.get("description", site.get("name", ""))
                            })
                            
                # Handle direct URL list
                elif isinstance(result, list):
                    for item in result:
                        if isinstance(item, dict):
                            urls.append({
                                "url": item.get("url", ""),
                                "description": item.get("description", "")
                            })
                            
            # Check for reference_urls
            if "reference_urls" in response and isinstance(response["reference_urls"], list):
                for url in response["reference_urls"]:
                    if not any(u["url"] == url for u in urls):
                        urls.append({
                            "url": url,
                            "description": "Reference URL"
                        })
                        
        return urls
    
    async def validate_urls(self, urls: List[str]) -> Dict[str, bool]:
        """
        Validate multiple URLs concurrently.
        
        Args:
            urls: List of URLs to validate
            
        Returns:
            Dictionary mapping URLs to their validity status
        """
        async def check_url(session: aiohttp.ClientSession, url: str) -> tuple[str, bool]:
            try:
                async with session.head(url, timeout=5, allow_redirects=True) as response:
                    return (url, response.status < 400)
            except Exception:
                return (url, False)
        
        async with aiohttp.ClientSession() as session:
            tasks = [check_url(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
        return dict(results)
    
    async def scrape_multiple(
        self,
        urls: List[str],
        prompt: str,
        schema: Optional[type[BaseModel]] = None,
        max_concurrent: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Scrape multiple URLs concurrently with rate limiting.
        
        Args:
            urls: List of URLs to scrape
            prompt: Extraction prompt
            schema: Optional output schema
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of scraping results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_limit(url: str) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.smart_scraper(url, prompt, schema)
                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {e}")
                    return {
                        "success": False,
                        "url": url,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    }
        
        tasks = [scrape_with_limit(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        successful = sum(1 for r in results if r.get("success"))
        logger.info(f"Scraped {successful}/{len(urls)} URLs successfully")
        
        return results


# Factory function
async def get_enhanced_scraping_service() -> EnhancedScrapingService:
    """Get an enhanced scraping service instance."""
    return EnhancedScrapingService(
        api_key=settings.SCRAPEGRAPH_API_KEY,
        max_retries=3,
        timeout=30
    )