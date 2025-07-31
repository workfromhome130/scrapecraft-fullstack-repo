from typing import Dict, List, Optional
from app.config import settings
from app.services.scrapegraph import ScrapingService

class SimpleScrapingAgent:
    def __init__(self):
        self.scraping_service = ScrapingService(settings.SCRAPEGRAPH_API_KEY)
        self.pipelines = {}
    
    async def process_message(self, message: str, pipeline_id: str, context: Dict = None) -> Dict:
        """Process a user message and return the response."""
        
        # Simple command parsing
        message_lower = message.lower()
        
        if context is None:
            context = {"urls": [], "schema": {}, "generated_code": ""}
        
        response = "I can help you build a web scraping pipeline. Try these commands:\n"
        response += "- 'add url <url>': Add a URL to scrape\n"
        response += "- 'list urls': Show all URLs\n"
        response += "- 'define schema': Define data fields to extract\n"
        response += "- 'generate code': Generate Python code\n"
        response += "- 'run pipeline': Execute the scraping"
        
        # Handle add URL
        if "add url" in message_lower:
            url = message.split("add url", 1)[1].strip()
            if url:
                context["urls"].append(url)
                response = f"✅ Added URL: {url}\nTotal URLs: {len(context['urls'])}"
        
        # Handle list URLs
        elif "list urls" in message_lower:
            if context["urls"]:
                response = "📋 Current URLs:\n" + "\n".join(f"- {url}" for url in context["urls"])
            else:
                response = "No URLs added yet. Use 'add url <url>' to add one."
        
        # Handle schema definition
        elif "define schema" in message_lower or "add field" in message_lower:
            response = "To define schema fields, use:\n"
            response += "'add field <name> <type>' where type is: str, int, float, bool, list\n"
            response += f"Current fields: {list(context.get('schema', {}).keys())}"
        
        # Handle generate code
        elif "generate code" in message_lower:
            if context["urls"] and context.get("schema"):
                code = self._generate_simple_code(context["urls"], context["schema"])
                context["generated_code"] = code
                response = "✅ Generated Python code for your pipeline. Check the Code tab!"
            else:
                response = "❌ Please add URLs and define schema fields first."
        
        # Handle run pipeline
        elif "run" in message_lower or "execute" in message_lower:
            if context["urls"] and context.get("schema"):
                response = "🚀 Starting pipeline execution..."
                # In real implementation, this would trigger actual scraping
            else:
                response = "❌ Please add URLs and define schema fields first."
        
        return {
            "response": response,
            "urls": context["urls"],
            "schema": context.get("schema", {}),
            "code": context.get("generated_code", ""),
            "results": [],
            "status": "idle",
            "error": None
        }
    
    def _generate_simple_code(self, urls: List[str], schema: Dict) -> str:
        """Generate simple Python code for scraping."""
        code = f'''import asyncio
from scrapegraph_py import AsyncClient

async def scrape_data():
    """Scrape data from multiple URLs."""
    urls = {urls}
    
    async with AsyncClient(api_key="YOUR_API_KEY") as client:
        results = []
        for url in urls:
            result = await client.smartscraper(
                website_url=url,
                user_prompt="Extract: {', '.join(schema.keys())}"
            )
            results.append(result)
    
    return results

# Run the scraper
if __name__ == "__main__":
    data = asyncio.run(scrape_data())
    print(data)
'''
        return code

# Create a singleton instance
simple_agent = SimpleScrapingAgent()