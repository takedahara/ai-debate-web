"""API routes"""

from .health import router as health_router
from .debate import router as debate_router

__all__ = ["health_router", "debate_router"]
