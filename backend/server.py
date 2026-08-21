"""
FastAPI server for XToX Converter backend.
"""
import logging
import os

from database import Database
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import conversion, documents, status

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the main app
app = FastAPI(title="XToPDF API", description="Convert LaTeX to PDF API")

# Add CORS middleware
# TODO: Production hardening - Configure specific allowed origins
# Current implementation allows all origins for development
# In production, set ALLOWED_ORIGINS environment variable with comma-separated list
allowed_origins_env = os.environ.get('ALLOWED_ORIGINS', '*')
if allowed_origins_env == '*':
    # Development mode - allow all origins
    # TODO: Remove this before production deployment
    logging.warning("CORS configured to allow all origins. Set ALLOWED_ORIGINS for production.")
    allowed_origins = ["*"]
else:
    # Production mode - specific origins
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(',')]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-Request-ID"],
    expose_headers=["X-Conversion-ID", "X-Request-ID"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Add rate limiting middleware if enabled
from config import RATE_LIMIT_ENABLED, RATE_LIMIT_REQUESTS

if RATE_LIMIT_ENABLED:
    from middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware, requests_per_minute=RATE_LIMIT_REQUESTS)
    logger.info(f"Rate limiting enabled: {RATE_LIMIT_REQUESTS} requests per minute")

# Add error handling middleware
from middleware.error_handler import error_handler_middleware

app.middleware("http")(error_handler_middleware)

# Include routers
app.include_router(conversion.router)
app.include_router(status.router)
app.include_router(documents.router)

# Include new feature routers
from routers import batch, history, webhooks  # noqa: E402

app.include_router(batch.router)
app.include_router(history.router)
app.include_router(webhooks.router)
@app.on_event("startup")
async def startup_db_client():
    await Database.connect()
    logger.info("Connected to the MongoDB database")

@app.on_event("shutdown")
async def shutdown_db_client():
    await Database.close()
    logger.info("Disconnected from the MongoDB database")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
