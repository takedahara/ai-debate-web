"""Health check endpoint"""

from datetime import datetime
from fastapi import APIRouter

router = APIRouter()

VERSION = "1.0.0"


@router.get("/health")
async def health_check():
    """Health check endpoint

    Returns:
        Health status with timestamp and version
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": VERSION,
    }
