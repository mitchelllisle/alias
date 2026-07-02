"""Unit tests for priveil.judge.refiner."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from priveil.domain.entities import ENTITY_CLASSIFICATION, Entity, EntityType
from priveil.judge.refiner import Refiner
from priveil.settings import Settings


def _entity(entity_type: EntityType, text: str, start: int, score: float) -> Entity:
    is_pii, sensitivity = ENTITY_CLASSIFICATION[entity_type]
    return Entity(
        text=text,
        entity_type=entity_type,
        start=start,
        end=start + len(text),
        score=score,
        is_pii=is_pii,
        sensitivity=sensitivity,
    )


def _settings(**kwargs: object) -> Settings:
    return Settings(_env_file=None, spacy_model="en_core_web_sm", judge_model="openai:test", **kwargs)  # type: ignore[call-arg]


def _mock_client(content: str) -> SimpleNamespace:
    async def _create(**_: object) -> SimpleNamespace:
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))


@pytest.mark.asyncio
async def test_refine_skips_judge_when_no_uncertain_entities() -> None:
    entity = _entity(EntityType.EMAIL_ADDRESS, "a@b.com", 0, 0.7)
    refiner = Refiner(client=_mock_client('{"keep":[0]}'), settings=_settings())
    result = await refiner.refine("Email a@b.com", (entity,))
    assert result.entities == (entity,)
    assert result.judge_applied is False


@pytest.mark.asyncio
async def test_refine_keeps_only_judged_ids() -> None:
    person = _entity(EntityType.PERSON, "Jane Smith", 0, 0.8)
    location = _entity(EntityType.LOCATION, "Sydney", 20, 0.7)
    refiner = Refiner(client=_mock_client('{"keep":[1]}'), settings=_settings(judge_score_threshold=0.99))
    result = await refiner.refine("Jane Smith lives in Sydney", (person, location))
    assert result.entities == (location,)
    assert result.judge_applied is True


@pytest.mark.asyncio
async def test_refine_fail_open_on_timeout() -> None:
    async def _create(**_: object) -> SimpleNamespace:
        await asyncio.sleep(0.01)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"keep":[0]}'))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    refiner = Refiner(client=client, settings=_settings(judge_timeout_ms=1))
    person = _entity(EntityType.PERSON, "Jane Smith", 0, 0.7)
    result = await refiner.refine("Jane Smith", (person,))
    assert result.entities == (person,)
    assert result.judge_applied is False


@pytest.mark.asyncio
async def test_refine_includes_certain_entities_without_judging_them() -> None:
    trusted = _entity(EntityType.PHONE_NUMBER, "0400 000 000", 0, 1.0)
    uncertain = _entity(EntityType.PERSON, "Jane Smith", 15, 0.7)
    refiner = Refiner(client=_mock_client('{"keep":[0]}'), settings=_settings())
    result = await refiner.refine("0400 000 000 Jane Smith", (trusted, uncertain))
    assert result.entities == (trusted, uncertain)
    assert result.judge_applied is True
