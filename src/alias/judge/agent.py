from pydantic_ai import Agent

from alias.judge.prompts import SYSTEM_PROMPT
from alias.judge.service import JudgeDecision
from alias.settings import Settings


def build_judge_agent(settings: Settings) -> Agent[None, JudgeDecision]:
    """Build and return the pydantic-ai judge agent.

    Args:
        settings: Application settings; settings.judge_model must be non-empty.

    Returns:
        A configured Agent that returns JudgeDecision structured output.

    Raises:
        ValueError: If judge_model is not set in settings.
    """
    if not settings.judge_model:
        raise ValueError("judge_model must be set in settings to build the judge agent")
    return Agent(
        model=settings.judge_model,
        output_type=JudgeDecision,
        system_prompt=SYSTEM_PROMPT,
        model_settings={"temperature": settings.judge_temperature},
    )
