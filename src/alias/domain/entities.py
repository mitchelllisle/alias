from enum import Enum
from typing import Literal, NamedTuple

from pydantic import BaseModel

Sensitivity = Literal["low", "medium", "high", "critical"]


class EntityType(str, Enum):
    """Entity types recognised by the detection engine."""

    # Standard presidio / spaCy types
    PERSON = "PERSON"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    PHONE_NUMBER = "PHONE_NUMBER"
    CREDIT_CARD = "CREDIT_CARD"
    LOCATION = "LOCATION"
    DATE_TIME = "DATE_TIME"
    NRP = "NRP"  # Nationality / religion / political group

    # Australian financial & government identifiers (slice 2)
    AU_TFN = "AU_TFN"            # Tax File Number — critical PII
    AU_ABN = "AU_ABN"            # Australian Business Number — not personal PII
    AU_ACN = "AU_ACN"            # Australian Company Number — not personal PII
    AU_BSB = "AU_BSB"            # Bank State Branch code
    AU_ACCOUNT_NUMBER = "AU_ACCOUNT_NUMBER"  # Bank account number
    AU_MEDICARE = "AU_MEDICARE"  # Medicare card number — critical PII
    AU_PHONE = "AU_PHONE"        # Australian mobile / landline


class EntityClassification(NamedTuple):
    """PII classification and sensitivity level for an entity type."""

    is_pii: bool
    sensitivity: Sensitivity


# Business rules: classification for each recognised entity type.
# Every EntityType member must have an entry — KeyError means enum and map are out of sync.
ENTITY_CLASSIFICATION: dict[EntityType, EntityClassification] = {
    # Standard types
    EntityType.PERSON: EntityClassification(is_pii=True, sensitivity="high"),
    EntityType.EMAIL_ADDRESS: EntityClassification(is_pii=True, sensitivity="medium"),
    EntityType.PHONE_NUMBER: EntityClassification(is_pii=True, sensitivity="medium"),
    EntityType.CREDIT_CARD: EntityClassification(is_pii=True, sensitivity="critical"),
    EntityType.LOCATION: EntityClassification(is_pii=True, sensitivity="low"),
    EntityType.DATE_TIME: EntityClassification(is_pii=False, sensitivity="low"),
    EntityType.NRP: EntityClassification(is_pii=False, sensitivity="low"),
    # Australian types
    EntityType.AU_TFN: EntityClassification(is_pii=True, sensitivity="critical"),
    EntityType.AU_ABN: EntityClassification(is_pii=False, sensitivity="low"),
    EntityType.AU_ACN: EntityClassification(is_pii=False, sensitivity="low"),
    EntityType.AU_BSB: EntityClassification(is_pii=True, sensitivity="high"),
    EntityType.AU_ACCOUNT_NUMBER: EntityClassification(is_pii=True, sensitivity="high"),
    EntityType.AU_MEDICARE: EntityClassification(is_pii=True, sensitivity="critical"),
    EntityType.AU_PHONE: EntityClassification(is_pii=True, sensitivity="medium"),
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
