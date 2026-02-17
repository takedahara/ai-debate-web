"""Debate Core - Core logic for AI debate simulation"""

from .types import Character, DebateSession, TurnResult, JudgeResult, Speaker
from .config import DEFAULT_CHARACTERS, DEFAULT_TOPIC
from .prompts import create_debater_prompt, create_judge_prompt
from .session import SessionManager

__all__ = [
    "Character",
    "DebateSession",
    "TurnResult",
    "JudgeResult",
    "Speaker",
    "DEFAULT_CHARACTERS",
    "DEFAULT_TOPIC",
    "create_debater_prompt",
    "create_judge_prompt",
    "SessionManager",
]
