"""Debate API endpoints"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel, Field

from debate_core import (
    SessionManager,
    Character,
    TurnResult,
    JudgeResult,
    Speaker,
    DEFAULT_TOPIC,
)
from debate_core.prompts import (
    create_debater_prompt,
    create_judge_prompt,
    create_initial_prompt,
    create_rebuttal_prompt,
    JUDGE_SYSTEM_PROMPT,
)
from debate_core.config import LLM_MAX_TOKENS_DEBATE, LLM_MAX_TOKENS_JUDGE
from llm_client import GroqClient, RateLimitError, APIKeyError, LLMError
from api_server.middleware.rate_limit import limiter, get_rate_limit_string

router = APIRouter(prefix="/debate", tags=["debate"])

# Global session manager
session_manager = SessionManager(session_timeout_minutes=30)


def get_llm_client(api_key: Optional[str] = None) -> GroqClient:
    """Get LLM client with the provided API key

    Args:
        api_key: API key from request header (takes priority) or env var
    """
    try:
        return GroqClient(api_key=api_key)
    except APIKeyError as e:
        raise HTTPException(
            status_code=401,
            detail="APIキーが必要です。Groq APIキーを入力してください。"
        )


# Request/Response models
class CharacterInput(BaseModel):
    """Character configuration input"""
    name: str = Field(..., min_length=1, max_length=20)
    age: str = Field(default="20歳", max_length=10)
    job: str = Field(default="学生", max_length=20)
    tone: str = Field(default="丁寧な口調", max_length=50)
    personality: str = Field(default="論理的", max_length=50)
    color: str = Field(default="#888888", pattern=r"^#[0-9A-Fa-f]{6}$")


class StartRequest(BaseModel):
    """Request to start a debate"""
    topic: str = Field(default=DEFAULT_TOPIC, min_length=1, max_length=200)
    pro_character: Optional[CharacterInput] = None
    con_character: Optional[CharacterInput] = None


class SessionRequest(BaseModel):
    """Request with session ID"""
    session_id: str


class StartResponse(BaseModel):
    """Response when starting a debate"""
    session_id: str
    topic: str
    pro: dict
    con: dict


class TurnResponse(BaseModel):
    """Response for a debate turn"""
    turn_number: int
    speaker: dict
    text: str
    next_speaker: Optional[str]


class JudgeResponse(BaseModel):
    """Response for judge evaluation"""
    verdict: dict
    history: list[str]
    turn_count: int


@router.post("/start", response_model=StartResponse, status_code=201)
@limiter.limit(get_rate_limit_string())
async def start_debate(
    request: Request,
    body: StartRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Start a new debate session

    Creates a new session with the given topic and optional character customization.
    API key can be provided via X-API-Key header or GROQ_API_KEY env var.
    """
    # Validate API key is available
    get_llm_client(x_api_key)

    # Convert input to Character objects
    pro_char = None
    con_char = None

    if body.pro_character:
        pro_char = Character(**body.pro_character.model_dump())
    if body.con_character:
        con_char = Character(**body.con_character.model_dump())

    session = session_manager.create_session(
        topic=body.topic,
        pro_character=pro_char,
        con_character=con_char,
    )

    return StartResponse(**session.to_dict())


@router.post("/turn", response_model=TurnResponse)
@limiter.limit(get_rate_limit_string())
async def debate_turn(
    request: Request,
    body: SessionRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Execute a single debate turn

    Alternates between pro and con speakers. Returns the generated text.
    """
    session = session_manager.get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    client = get_llm_client(x_api_key)

    # Determine current speaker
    current_role = session.get_next_speaker()
    current_char = session.pro if current_role == "pro" else session.con
    opponent_char = session.con if current_role == "pro" else session.pro

    # Create prompts
    system_prompt = create_debater_prompt(current_role, session.topic, current_char)

    if session.turn_count == 0:
        # First turn
        user_prompt = create_initial_prompt(session.topic)
    else:
        # Rebuttal to previous statement
        last_statement = session.history[-1]
        user_prompt = create_rebuttal_prompt(opponent_char.name, last_statement)

    # Get response from LLM
    try:
        text = client.get_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=LLM_MAX_TOKENS_DEBATE,
        ).strip()
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {e.retry_after} seconds.",
            headers={"Retry-After": str(e.retry_after)},
        )
    except LLMError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Update session
    session.add_turn(text, current_role)

    # Build response
    next_speaker = "con" if current_role == "pro" else "pro"

    result = TurnResult(
        turn_number=session.turn_count,
        speaker=Speaker(
            role=current_role,
            name=current_char.name,
            color=current_char.color,
        ),
        text=text,
        next_speaker=next_speaker,
    )

    return TurnResponse(**result.to_dict())


@router.post("/judge", response_model=JudgeResponse)
@limiter.limit(get_rate_limit_string())
async def judge_debate(
    request: Request,
    body: SessionRequest,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    """Get judge evaluation for the debate

    Evaluates the debate and returns the verdict with winner.
    """
    session = session_manager.get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if len(session.history) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 turns required for judging"
        )

    client = get_llm_client(x_api_key)

    # Create judge prompt
    judge_prompt = create_judge_prompt(
        topic=session.topic,
        history=session.history,
        pro_name=session.pro.name,
        con_name=session.con.name,
    )

    # Get judge response
    try:
        judge_text = client.get_response(
            prompt=judge_prompt,
            system_prompt=JUDGE_SYSTEM_PROMPT,
            max_tokens=LLM_MAX_TOKENS_JUDGE,
        ).strip()
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry after {e.retry_after} seconds.",
            headers={"Retry-After": str(e.retry_after)},
        )
    except LLMError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Determine winner from text
    winner = "pro"
    winner_name = session.pro.name
    if session.con.name in judge_text and "勝者" in judge_text:
        # Check if con name appears near "勝者"
        con_idx = judge_text.find(session.con.name)
        pro_idx = judge_text.find(session.pro.name)
        winner_idx = judge_text.find("勝者")
        if con_idx != -1 and (pro_idx == -1 or abs(con_idx - winner_idx) < abs(pro_idx - winner_idx)):
            winner = "con"
            winner_name = session.con.name

    verdict = JudgeResult(
        winner=winner,
        winner_name=winner_name,
        text=judge_text,
    )

    return JudgeResponse(
        verdict=verdict.to_dict(),
        history=session.history,
        turn_count=session.turn_count,
    )
