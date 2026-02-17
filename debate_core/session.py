"""Session management for AI debate"""

from typing import Optional
from datetime import datetime, timedelta
from .types import DebateSession, Character
from .config import DEFAULT_CHARACTERS


class SessionManager:
    """Manages active debate sessions"""

    def __init__(self, session_timeout_minutes: int = 30):
        self._sessions: dict[str, DebateSession] = {}
        self._timeout = timedelta(minutes=session_timeout_minutes)

    def create_session(
        self,
        topic: str,
        pro_character: Optional[Character] = None,
        con_character: Optional[Character] = None,
    ) -> DebateSession:
        """Create a new debate session

        Args:
            topic: The debate topic
            pro_character: Optional custom pro character
            con_character: Optional custom con character

        Returns:
            New DebateSession
        """
        session = DebateSession(
            topic=topic,
            pro=pro_character or DEFAULT_CHARACTERS["pro"],
            con=con_character or DEFAULT_CHARACTERS["con"],
        )
        self._sessions[session.session_id] = session
        self._cleanup_expired()
        return session

    def get_session(self, session_id: str) -> Optional[DebateSession]:
        """Get a session by ID

        Args:
            session_id: The session ID

        Returns:
            DebateSession if found and not expired, None otherwise
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None

        # Check if expired
        if datetime.utcnow() - session.created_at > self._timeout:
            del self._sessions[session_id]
            return None

        return session

    def delete_session(self, session_id: str) -> bool:
        """Delete a session

        Args:
            session_id: The session ID

        Returns:
            True if deleted, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def _cleanup_expired(self) -> None:
        """Remove expired sessions"""
        now = datetime.utcnow()
        expired = [
            sid for sid, session in self._sessions.items()
            if now - session.created_at > self._timeout
        ]
        for sid in expired:
            del self._sessions[sid]

    @property
    def active_session_count(self) -> int:
        """Get the number of active sessions"""
        self._cleanup_expired()
        return len(self._sessions)
