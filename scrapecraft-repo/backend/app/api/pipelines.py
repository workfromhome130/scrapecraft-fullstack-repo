from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import uuid

from app.models.pipeline import Pipeline, PipelineCreate, PipelineUpdate
from app.services.database import get_db
from sqlalchemy.orm import Session

router = APIRouter()

# In-memory storage for now (should be replaced with database)
pipelines_store = {}

@router.post("/", response_model=Pipeline)
async def create_pipeline(pipeline: PipelineCreate):
    """Create a new scraping pipeline."""
    pipeline_id = str(uuid.uuid4())
    new_pipeline = Pipeline(
        id=pipeline_id,
        name=pipeline.name,
        description=pipeline.description,
        urls=pipeline.urls or [],
        schema=pipeline.schema or {},
        code="",
        status="idle",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    pipelines_store[pipeline_id] = new_pipeline
    return new_pipeline

@router.get("/{pipeline_id}", response_model=Pipeline)
async def get_pipeline(pipeline_id: str):
    """Get a specific pipeline by ID."""
    if pipeline_id not in pipelines_store:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    return pipelines_store[pipeline_id]

@router.get("/", response_model=List[Pipeline])
async def list_pipelines(skip: int = 0, limit: int = 10):
    """List all pipelines."""
    pipelines = list(pipelines_store.values())
    return pipelines[skip:skip + limit]

@router.put("/{pipeline_id}", response_model=Pipeline)
async def update_pipeline(pipeline_id: str, update: PipelineUpdate):
    """Update an existing pipeline."""
    if pipeline_id not in pipelines_store:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = pipelines_store[pipeline_id]
    
    if update.name is not None:
        pipeline.name = update.name
    if update.description is not None:
        pipeline.description = update.description
    if update.urls is not None:
        pipeline.urls = update.urls
    if update.schema is not None:
        pipeline.schema = update.schema
    if update.code is not None:
        pipeline.code = update.code
    
    pipeline.updated_at = datetime.utcnow()
    return pipeline

@router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    """Delete a pipeline."""
    if pipeline_id not in pipelines_store:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    del pipelines_store[pipeline_id]
    return {"message": "Pipeline deleted successfully"}

@router.post("/{pipeline_id}/run")
async def run_pipeline(pipeline_id: str):
    """Execute a scraping pipeline."""
    if pipeline_id not in pipelines_store:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = pipelines_store[pipeline_id]
    
    if not pipeline.urls:
        raise HTTPException(status_code=400, detail="No URLs defined in pipeline")
    
    if not pipeline.schema:
        raise HTTPException(status_code=400, detail="No schema defined in pipeline")
    
    # TODO: Execute scraping through the agent
    pipeline.status = "running"
    
    return {
        "pipeline_id": pipeline_id,
        "status": "running",
        "message": "Pipeline execution started"
    }

@router.get("/{pipeline_id}/status")
async def get_pipeline_status(pipeline_id: str):
    """Get the current status of a pipeline."""
    if pipeline_id not in pipelines_store:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = pipelines_store[pipeline_id]
    
    return {
        "pipeline_id": pipeline_id,
        "status": pipeline.status,
        "updated_at": pipeline.updated_at
    }

@router.get("/{pipeline_id}/results")
async def get_pipeline_results(pipeline_id: str):
    """Get the results of a pipeline execution."""
    if pipeline_id not in pipelines_store:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    # TODO: Retrieve actual results from storage
    return {
        "pipeline_id": pipeline_id,
        "results": [],
        "total": 0,
        "success": 0,
        "failed": 0
    }

@router.post("/{pipeline_id}/export")
async def export_pipeline_results(
    pipeline_id: str,
    format: str = "json"
):
    """Export pipeline results in various formats."""
    if pipeline_id not in pipelines_store:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    if format not in ["json", "csv", "excel"]:
        raise HTTPException(status_code=400, detail="Invalid export format")
    
    # TODO: Implement export functionality
    return {
        "message": f"Results exported as {format}",
        "download_url": f"/api/pipelines/{pipeline_id}/download/{format}"
    }