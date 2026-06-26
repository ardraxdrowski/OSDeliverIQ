import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from src.database import engine, Base
from src.api.routes import router
from src.ingestion.scheduler import start_scheduler, shutdown_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("osdeliveriq")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")
    
    logger.info("Starting background scheduler...")
    start_scheduler()
    
    yield
    
    logger.info("Shutting down background scheduler...")
    shutdown_scheduler()
    logger.info("Shutdown completed.")

app = FastAPI(
    title="OSDeliverIQ",
    version="1.0.0",
    lifespan=lifespan
)

# Request logging middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url.path}")
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Response: {request.method} {request.url.path} - Status: {response.status_code} - Duration: {process_time:.4f}s")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {e} - Duration: {process_time:.4f}s", exc_info=True)
        raise

# Include API and dashboard routes
app.include_router(router)
