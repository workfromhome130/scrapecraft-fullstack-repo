from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.api import auth, chat, pipelines, scraping, execution, workflow
from app.services.websocket import ConnectionManager
from app.services.workflow_manager import get_workflow_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection manager for WebSocket
manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(scraping.router, prefix="/api/scraping", tags=["scraping"])
app.include_router(execution.router, prefix="/api/execution", tags=["execution"])
app.include_router(workflow.router, prefix="/api/workflow", tags=["workflow"])

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.websocket("/ws/{pipeline_id}")
async def websocket_endpoint(websocket: WebSocket, pipeline_id: str):
    await manager.connect(websocket, pipeline_id)
    try:
        while True:
            data = await websocket.receive_json()
            # Process the message through the agent
            response = await manager.process_message(pipeline_id, data)
            await manager.send_personal_message(response, websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket, pipeline_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, pipeline_id)