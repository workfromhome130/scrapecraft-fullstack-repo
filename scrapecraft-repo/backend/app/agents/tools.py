from langchain_core.tools import tool
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from urllib.parse import urlparse

class URLInput(BaseModel):
    url: str = Field(description="URL to add to the pipeline")

class SchemaField(BaseModel):
    name: str = Field(description="Field name")
    type: str = Field(description="Field type (str, int, float, bool, list)")
    description: str = Field(description="Field description")

class SchemaInput(BaseModel):
    fields: List[SchemaField] = Field(description="List of schema fields")

@tool
def add_url(url: str) -> Dict[str, Any]:
    """Add a URL to the scraping pipeline."""
    # Validate URL format
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            return {"success": False, "error": "Invalid URL format"}
        
        # Check if URL starts with http/https
        if result.scheme not in ['http', 'https']:
            return {"success": False, "error": "URL must start with http:// or https://"}
        
        return {
            "success": True,
            "url": url,
            "message": f"Successfully added {url} to the pipeline"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def remove_url(url: str) -> Dict[str, Any]:
    """Remove a URL from the scraping pipeline."""
    return {
        "success": True,
        "url": url,
        "message": f"Successfully removed {url} from the pipeline"
    }

@tool
def validate_url(url: str) -> Dict[str, Any]:
    """Validate if a URL is accessible and returns valid HTML."""
    import requests
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        
        if response.status_code < 400:
            return {
                "success": True,
                "url": url,
                "status_code": response.status_code,
                "valid": True,
                "message": "URL is accessible"
            }
        else:
            return {
                "success": True,
                "url": url,
                "status_code": response.status_code,
                "valid": False,
                "message": f"URL returned status code {response.status_code}"
            }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "valid": False,
            "error": str(e)
        }

@tool
def define_schema(schema_fields: List[Dict[str, str]]) -> Dict[str, Any]:
    """Define the extraction schema for scraping."""
    try:
        schema_dict = {}
        for field in schema_fields:
            field_type = field.get('type', 'str')
            if field_type == 'str':
                schema_dict[field['name']] = str
            elif field_type == 'int':
                schema_dict[field['name']] = int
            elif field_type == 'float':
                schema_dict[field['name']] = float
            elif field_type == 'bool':
                schema_dict[field['name']] = bool
            elif field_type == 'list':
                schema_dict[field['name']] = list
            else:
                schema_dict[field['name']] = str
        
        return {
            "success": True,
            "schema": schema_dict,
            "fields": schema_fields,
            "message": f"Schema defined with {len(schema_fields)} fields"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@tool
def generate_code(urls: List[str], extraction_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Generate Python code for the scraping pipeline."""
    code_template = '''import asyncio
from scrapegraph_py import AsyncClient
from pydantic import BaseModel
from typing import List, Optional

# Define the schema
class DataSchema(BaseModel):
{schema_fields}

async def scrape_urls(api_key: str):
    """Execute web scraping for multiple URLs concurrently."""
    urls = {urls}
    
    async with AsyncClient(api_key=api_key) as client:
        tasks = []
        for url in urls:
            task = client.smartscraper(
                website_url=url,
                user_prompt="Extract data according to the schema",
                output_schema=DataSchema
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        successful_results = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({{"url": urls[i], "error": str(result)}})
            else:
                successful_results.append({{"url": urls[i], "data": result}})
        
        return {{"success": successful_results, "errors": errors}}

if __name__ == "__main__":
    # Replace with your actual API key
    API_KEY = "your_scrapegraph_api_key"
    
    # Run the scraper
    results = asyncio.run(scrape_urls(API_KEY))
    
    # Print results
    print(f"Successfully scraped {{len(results['success'])}} URLs")
    print(f"Failed to scrape {{len(results['errors'])}} URLs")
    
    # Print data
    for result in results['success']:
        print(f"\\nURL: {{result['url']}}")
        print(f"Data: {{result['data']}}")
'''
    
    # Generate schema fields
    schema_fields = []
    for field_name, field_type in extraction_schema.items():
        type_str = field_type.__name__ if hasattr(field_type, '__name__') else str(field_type)
        schema_fields.append(f"    {field_name}: {type_str}")
    
    schema_str = "\n".join(schema_fields) if schema_fields else "    pass"
    
    code = code_template.format(
        schema_fields=schema_str,
        urls=urls
    )
    
    return {
        "success": True,
        "code": code,
        "message": "Code generated successfully"
    }

@tool
def clear_pipeline() -> Dict[str, Any]:
    """Clear all URLs and reset the pipeline."""
    return {
        "success": True,
        "message": "Pipeline cleared successfully"
    }

# Tool list for the agent
SCRAPING_TOOLS = [
    add_url,
    remove_url,
    validate_url,
    define_schema,
    generate_code,
    clear_pipeline
]