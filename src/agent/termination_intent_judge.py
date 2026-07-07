"""Prompt and response parsing for interview termination intent."""


def build_termination_judge_prompt(generated_content: str) -> str:
    return (
        f'{generated_content}\n'
        '判断上述文本是不是触发访谈终止的意图，只输出“yes”或“no”'
    )


def is_termination_intent(judgement: str) -> bool:
    """Only an unambiguous `yes` response terminates the interview."""
    return judgement.strip().lower().strip('“”"\'。.!！') == "yes"
