"""Prompt generation for AI debate (from ai_debate_voicevox.py lines 135-173)"""

from .types import Character


def create_debater_prompt(role: str, topic: str, character: Character) -> str:
    """Create system prompt for a debater

    Args:
        role: "pro" for affirmative, "con" for negative
        topic: The debate topic
        character: Character configuration

    Returns:
        System prompt string
    """
    stance = "賛成" if role == "pro" else "反対"
    return f"""あなたは{character.name}という名前の{character.age}の{character.job}です。
「{topic}」に{stance}の立場で議論しています。

【最重要ルール】
- 必ず「{topic}」の具体的な内容について話すこと
- 具体例や根拠を挙げて議論すること

【話し方のルール】
- 一文〜二文で返答する
- {character.tone}で話す
- 自然な会話調で話す

性格: {character.personality}"""


def create_judge_prompt(topic: str, history: list[str], pro_name: str, con_name: str) -> str:
    """Create prompt for the judge

    Args:
        topic: The debate topic
        history: List of debate messages (alternating pro/con)
        pro_name: Name of the pro debater
        con_name: Name of the con debater

    Returns:
        Judge prompt string
    """
    conversation = ""
    for i, msg in enumerate(history):
        speaker = pro_name if i % 2 == 0 else con_name
        conversation += f"{speaker}: {msg}\n"

    return f"""あなたはディベート大会の審判です。今回の議論を振り返って、自然な口調で評価してください。

【議題】{topic}

【議論内容】
{conversation}

【評価のポイント】
- 論理性、具体性、反論力、説得力の4つの観点で評価
- 各25点満点、合計100点で採点
- 必ず実際の発言内容を「」で引用しながらコメントすること

【回答のルール】
- 箇条書きや■などの記号は使わず、話し言葉で自然に語る
- 具体的にどの発言が良かったか・悪かったかを「」で引用する
- 最後に勝者を発表し、両者への励ましの言葉で締める

【回答例】
それでは判定結果を発表します！

まず{pro_name}さんですが、「〜〜」という主張がとても印象的でした。具体例をしっかり挙げていて説得力がありましたね。ただ、「〜〜」の部分は少し根拠が弱かったかな。論理性20点、具体性22点、反論力21点、説得力20点、合計83点です！

続いて{con_name}さん。「〜〜」という反論は鋭くて良かったです！でも...（以下同様）

ということで、今回の勝者は○○さんです！おめでとうございます！

（両者への前向きなコメント）"""


def create_initial_prompt(topic: str) -> str:
    """Create the initial prompt for the first turn"""
    return f"「{topic}」について、具体例を一つ挙げて自分の意見を言って。"


def create_rebuttal_prompt(opponent_name: str, opponent_text: str) -> str:
    """Create a rebuttal prompt"""
    return f"{opponent_name}「{opponent_text}」\n\n↑この主張に反論して。"


# Judge system prompt
JUDGE_SYSTEM_PROMPT = """あなたは明るく親しみやすいディベート大会の審判です。
友達に話しかけるような自然な口調で、でも公正に評価してください。
実際の発言を「」で引用しながら、どこが良かったか具体的に褒めてください。
最後は両者を励ます前向きな言葉で締めくくってください。"""
