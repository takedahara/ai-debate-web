"""Default configuration for AI debate"""

from .types import Character

# Default characters (from ai_debate_voicevox.py lines 33-56)
DEFAULT_CHARACTERS = {
    "pro": Character(
        name="さくら",
        age="17歳",
        job="高校生",
        tone="元気で明るい口調",
        personality="ポジティブ、熱血、たまにドジ",
        color="#FF69B4",  # Hot Pink
    ),
    "con": Character(
        name="あおい",
        age="18歳",
        job="大学生",
        tone="クールで知的な口調",
        personality="冷静、論理的、ちょっと毒舌",
        color="#87CEEB",  # Sky Blue
    ),
}

# Default topic
DEFAULT_TOPIC = "AIは人間の仕事を奪う"

# LLM settings
LLM_MODEL = "llama-3.3-70b-versatile"
LLM_MAX_TOKENS_DEBATE = 500
LLM_MAX_TOKENS_JUDGE = 800
