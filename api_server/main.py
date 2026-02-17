"""FastAPI application entry point"""

import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load environment variables
load_dotenv()

from api_server.middleware import setup_cors, setup_rate_limit, setup_logging, LoggingMiddleware
from api_server.routes import health_router, debate_router

# Setup logging
logger = setup_logging()

# Create FastAPI app
app = FastAPI(
    title="AI Debate API",
    description="API for AI-powered debate simulation",
    version="1.0.0",
)

# Setup middleware
setup_cors(app)
setup_rate_limit(app)
app.add_middleware(LoggingMiddleware)

# Include routers
app.include_router(health_router)
app.include_router(debate_router)

# Serve static files (web frontend)
web_dir = Path(__file__).parent.parent / "web"
if web_dir.exists():
    app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

# Serve character assets
assets_dir = Path(__file__).parent.parent / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def serve_index():
        """Serve the main frontend page"""
        index_path = web_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Frontend not found. Access /docs for API documentation."}
else:
    @app.get("/")
    async def root():
        """Root endpoint when no frontend is present"""
        return {
            "message": "AI Debate API",
            "docs": "/docs",
            "health": "/health",
        }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "api_server.main:app",
        host=host,
        port=port,
        reload=True,
    )
