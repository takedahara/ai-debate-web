"""Data classes for AI debate"""

from dataclasses import dataclass, field
from typing import Optional, Literal
from datetime import datetime
import uuid


@dataclass
class Character:
    """Debater character configuration"""
    name: str
    age: str = "20歳"
    job: str = "学生"
    tone: str = "丁寧な口調"
    personality: str = "論理的"
    color: str = "#888888"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "age": self.age,
            "job": self.job,
            "tone": self.tone,
            "personality": self.personality,
            "color": self.color,
        }


@dataclass
class Speaker:
    """Speaker info for a turn"""
    role: Literal["pro", "con"]
    name: str
    color: str


@dataclass
class TurnResult:
    """Result of a single debate turn"""
    turn_number: int
    speaker: Speaker
    text: str
    next_speaker: Optional[Literal["pro", "con"]] = None

    def to_dict(self) -> dict:
        return {
            "turn_number": self.turn_number,
            "speaker": {
                "role": self.speaker.role,
                "name": self.speaker.name,
                "color": self.speaker.color,
            },
            "text": self.text,
            "next_speaker": self.next_speaker,
        }


@dataclass
class JudgeResult:
    """Result of judge evaluation"""
    winner: Literal["pro", "con"]
    winner_name: str
    text: str

    def to_dict(self) -> dict:
        return {
            "winner": self.winner,
            "winner_name": self.winner_name,
            "text": self.text,
        }


@dataclass
class DebateSession:
    """Active debate session"""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    pro: Character = field(default_factory=lambda: Character(name="さくら"))
    con: Character = field(default_factory=lambda: Character(name="あおい"))
    history: list[str] = field(default_factory=list)
    turn_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_speaker: Optional[Literal["pro", "con"]] = None

    def add_turn(self, text: str, speaker: Literal["pro", "con"]) -> None:
        """Add a turn to the history"""
        self.history.append(text)
        self.turn_count += 1
        self.last_speaker = speaker

    def get_next_speaker(self) -> Literal["pro", "con"]:
        """Get the next speaker based on history"""
        if self.last_speaker is None or self.last_speaker == "con":
            return "pro"
        return "con"

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "pro": {
                "name": self.pro.name,
                "color": self.pro.color,
            },
            "con": {
                "name": self.con.name,
                "color": self.con.color,
            },
        }
