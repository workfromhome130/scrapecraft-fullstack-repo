from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import asyncio
import subprocess
import tempfile
import os
import json
from datetime import datetime

from app.config import settings
from app.services.scrapegraph import ScrapingService
from app.services.websocket import ConnectionManager
from app.services.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

class ExecuteRequest(BaseModel):
    pipeline_id: str
    code: str
    urls: List[str]
    schema: Dict[str, Any]
    api_key: Optional[str] = None

class ExecuteResponse(BaseModel):
    success: bool
    results: List[Dict]
    errors: List[str]
    execution_time: float
    timestamp: datetime

@router.post("/execute", response_model=ExecuteResponse)
async def execute_pipeline(
    request: ExecuteRequest,
    connection_manager: ConnectionManager = Depends(lambda: connection_manager)
):
    """Execute the generated scraping code."""
    start_time = asyncio.get_event_loop().time()
    results = []
    errors = []
    
    try:
        # Use provided API key or fallback to settings
        api_key = request.api_key or settings.SCRAPEGRAPH_API_KEY
        if not api_key:
            raise HTTPException(status_code=400, detail="SCRAPEGRAPH_API_KEY not configured")
        
        # Stream start of execution
        await connection_manager.stream_execution_updates(
            pipeline_id=request.pipeline_id,
            url="all",
            status="starting",
            data={"message": "Starting pipeline execution..."}
        )
        
        # Create temporary Python file with the code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Inject the API key and URLs into the code
            modified_code = request.code.replace(
                '"your-scrapegraph-api-key"',
                f'"{api_key}"'
            ).replace(
                '["url1", "url2"]',
                json.dumps(request.urls)
            )
            
            # Add result capture logic
            capture_code = f"""
import json
import sys

# Original code
{modified_code}

# Capture and output results
if __name__ == "__main__":
    try:
        import asyncio
        results = asyncio.run(scrape_weather_data())
        print("EXECUTION_RESULTS_START")
        print(json.dumps({{"success": True, "results": results}}))
        print("EXECUTION_RESULTS_END")
    except Exception as e:
        print("EXECUTION_RESULTS_START")
        print(json.dumps({{"success": False, "error": str(e)}}))
        print("EXECUTION_RESULTS_END")
"""
            f.write(capture_code)
            temp_file = f.name
        
        try:
            # Execute the Python script
            process = await asyncio.create_subprocess_exec(
                'python', temp_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Parse execution results
            stdout_str = stdout.decode('utf-8')
            stderr_str = stderr.decode('utf-8')
            
            if stderr_str:
                errors.append(f"Execution warnings/errors: {stderr_str}")
            
            # Extract results from stdout
            if "EXECUTION_RESULTS_START" in stdout_str and "EXECUTION_RESULTS_END" in stdout_str:
                start_idx = stdout_str.find("EXECUTION_RESULTS_START") + len("EXECUTION_RESULTS_START")
                end_idx = stdout_str.find("EXECUTION_RESULTS_END")
                result_json = stdout_str[start_idx:end_idx].strip()
                
                try:
                    execution_result = json.loads(result_json)
                    if execution_result.get("success"):
                        results = execution_result.get("results", [])
                        
                        # Stream successful results
                        for idx, result in enumerate(results):
                            await connection_manager.stream_execution_updates(
                                pipeline_id=request.pipeline_id,
                                url=request.urls[idx] if idx < len(request.urls) else "unknown",
                                status="completed",
                                data=result
                            )
                    else:
                        errors.append(execution_result.get("error", "Unknown error"))
                except json.JSONDecodeError:
                    errors.append(f"Failed to parse execution results: {result_json}")
            else:
                # Fallback: treat entire stdout as result
                results.append({"raw_output": stdout_str})
            
        finally:
            # Clean up temp file
            os.unlink(temp_file)
        
        # Stream completion
        await connection_manager.stream_execution_updates(
            pipeline_id=request.pipeline_id,
            url="all",
            status="completed",
            data={
                "message": "Pipeline execution completed",
                "total_results": len(results),
                "total_errors": len(errors)
            }
        )
        
    except Exception as e:
        errors.append(f"Execution failed: {str(e)}")
        
        # Stream error
        await connection_manager.stream_execution_updates(
            pipeline_id=request.pipeline_id,
            url="all",
            status="error",
            error=str(e)
        )
    
    execution_time = asyncio.get_event_loop().time() - start_time
    
    return ExecuteResponse(
        success=len(results) > 0,
        results=results,
        errors=errors,
        execution_time=execution_time,
        timestamp=datetime.utcnow()
    )

# Create singleton instance
connection_manager = ConnectionManager()