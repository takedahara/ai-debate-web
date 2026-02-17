"""Rate limiting configuration"""

import os
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


def get_client_ip(request: Request) -> str:
    """Get client IP address, handling proxies"""
    # Check X-Forwarded-For header first (for reverse proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(key_func=get_client_ip)


def setup_rate_limit(app: FastAPI) -> None:
    """Configure rate limiting middleware

    Reads limits from environment variables:
    - RATE_LIMIT_PER_MINUTE: requests per minute (default: 30)
    - RATE_LIMIT_PER_DAY: requests per day (default: 1000)
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def get_rate_limit_string() -> str:
    """Get the rate limit string from environment"""
    per_minute = os.getenv("RATE_LIMIT_PER_MINUTE", "30")
    return f"{per_minute}/minute"
