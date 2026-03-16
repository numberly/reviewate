from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AutomaticReviewTriggerEnum(StrEnum):
    CREATION = "creation"
    COMMIT = "commit"
    LABEL = "label"
    NONE = "none"


class OrganizationSettingsUpdate(BaseModel):
    automatic_review_trigger: AutomaticReviewTriggerEnum | None = None
    automatic_summary_trigger: AutomaticReviewTriggerEnum | None = None


class OrganizationSettings(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    automatic_review_trigger: str
    automatic_summary_trigger: str


class OrganizationEventMessage(BaseModel):
    user_id: str
    action: str
    organization: dict[str, Any]
    timestamp: str | None = None


class MemberListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_identity_id: UUID
    username: str | None
    avatar_url: str | None
    role: str
    reviewate_enabled: bool
    is_linked: bool = Field(
        description="Whether this identity is linked to a Reviewate user account"
    )


class MemberSettingsUpdate(BaseModel):
    reviewate_enabled: bool | None = None
