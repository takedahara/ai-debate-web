"""Logging configuration"""

import logging
import time
import uuid
from typing import Callable
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def setup_logging() -> logging.Logger:
    """Configure JSON-style logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    return logging.getLogger("api_server")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""

    def __init__(self, app: FastAPI):
        super().__init__(app)
        self.logger = logging.getLogger("api_server")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Add request_id to request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Log request
        log_data = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "ip": request.client.host if request.client else "unknown",
        }

        # Log level based on status code
        if response.status_code >= 500:
            self.logger.error(str(log_data))
        elif response.status_code >= 400:
            self.logger.warning(str(log_data))
        else:
            self.logger.info(str(log_data))

        # Add request_id to response headers
        response.headers["X-Request-ID"] = request_id

        return response
