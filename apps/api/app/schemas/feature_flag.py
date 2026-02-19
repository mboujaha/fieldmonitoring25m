from pydantic import BaseModel


class FeatureFlagResponse(BaseModel):
    key: str
    enabled: bool


class FeatureFlagUpdateRequest(BaseModel):
    enabled: bool
