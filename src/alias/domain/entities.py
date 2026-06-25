from enum import Enum
from typing import Literal, NamedTuple

from pydantic import BaseModel

Sensitivity = Literal["low", "medium", "high", "critical"]


class EntityType(str, Enum):
    """Entity types recognised by the detection engine.

    Standard presidio types only. Australian financial types are added in slice 2.
    """

    PERSON = "PERSON"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    CREDIT_CARD = "CREDIT_CARD"
    LOCATION = "LOCATION"
    DATE_TIME = "DATE_TIME"
    NRP = "NRP"  # Nationality / religion / political group


class EntityClassification(NamedTuple):
    """PII classification and sensitivity level for an entity type."""

    is_pii: bool
    sensitivity: Sensitivity


# Business rules: classification for each recognised entity type.
# Every EntityType member must have an entry — KeyError means enum and map are out of sync.
ENTITY_CLASSIFICATION: dict[EntityType, EntityClassification] = {
    EntityType.PERSON: EntityClassification(is_pii=True, sensitivity="high"),
    EntityType.EMAIL_ADDRESS: EntityClassification(is_pii=True, sensitivity="medium"),
    EntityType.PHONE_NUMBER: EntityClassification(is_pii=True, sensitivity="medium"),
    EntityType.CREDIT_CARD: EntityClassification(is_pii=True, sensitivity="critical"),
    EntityType.LOCATION: EntityClassification(is_pii=True, sensitivity="low"),
    EntityType.DATE_TIME: EntityClassification(is_pii=False, sensitivity="low"),
    EntityType.NRP: EntityClassification(is_pii=False, sensitivity="low"),
}


class Entity(BaseModel, frozen=True):
    """A detected entity span with its position, classification, and confidence score."""

    text: str
    entity_type: EntityType
    start: int
    end: int
    score: float
    is_pii: bool
    sensitivity: Sensitivity
