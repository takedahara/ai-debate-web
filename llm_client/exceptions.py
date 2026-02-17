"""Exceptions for LLM client"""


class LLMError(Exception):
    """Base exception for LLM errors"""
    pass


class RateLimitError(LLMError):
    """Raised when API rate limit is exceeded"""

    def __init__(self, message: str = "API rate limit exceeded", retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class APIKeyError(LLMError):
    """Raised when API key is missing or invalid"""

    def __init__(self, message: str = "API key is missing or invalid"):
        super().__init__(message)


class ModelError(LLMError):
    """Raised when there's an issue with the model"""

    def __init__(self, message: str = "Model error"):
        super().__init__(message)
