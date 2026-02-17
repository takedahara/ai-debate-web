"""Groq API client (from ai_debate_voicevox.py lines 59-86)"""

import os
import time
from typing import Optional

from .exceptions import RateLimitError, APIKeyError, LLMError


class GroqClient:
    """Client for Groq API"""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Groq client

        Args:
            api_key: Groq API key. If not provided, reads from GROQ_API_KEY env var.

        Raises:
            APIKeyError: If no API key is provided or found in environment
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise APIKeyError(
                "GROQ_API_KEY not found. Set it as an environment variable or pass it to the constructor."
            )
        self._client = None

    def _get_client(self):
        """Lazy initialization of Groq client"""
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    def get_response(
        self,
        prompt: str,
        system_prompt: str,
        max_tokens: int = 200,
        model: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """Get a response from Groq API

        Args:
            prompt: User prompt
            system_prompt: System prompt
            max_tokens: Maximum tokens in response
            model: Model to use (defaults to DEFAULT_MODEL)
            max_retries: Number of retries on rate limit

        Returns:
            Response text

        Raises:
            RateLimitError: If rate limited after all retries
            LLMError: For other API errors
        """
        client = self._get_client()
        model = model or self.DEFAULT_MODEL

        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content

            except Exception as e:
                error_msg = str(e).lower()

                # Check for rate limit errors
                if "rate" in error_msg or "limit" in error_msg or "429" in error_msg:
                    wait_time = 5 * (attempt + 1)
                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RateLimitError(
                            f"API rate limit exceeded after {max_retries} retries",
                            retry_after=60,
                        )

                # Check for auth errors
                if "auth" in error_msg or "key" in error_msg or "401" in error_msg:
                    raise APIKeyError("Invalid API key")

                # Other errors
                raise LLMError(f"Groq API error: {e}")

        # Should not reach here, but just in case
        raise LLMError("Unexpected error in get_response")
