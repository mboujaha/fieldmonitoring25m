from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import List, Optional

try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, PyEnum):
        pass

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RoleEnum(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class InviteStatusEnum(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ObservationStatusEnum(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    LOW_QUALITY_SKIPPED = "LOW_QUALITY_SKIPPED"
    FAILED = "FAILED"


class JobStatusEnum(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class LayerTypeEnum(StrEnum):
    NATIVE_INDEX = "NATIVE_INDEX"
    SR_INDEX = "SR_INDEX"
    RADAR = "RADAR"
    RGB = "RGB"


class AlertSeverityEnum(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class ExportFormatEnum(StrEnum):
    GEOTIFF = "GEOTIFF"
    CSV = "CSV"
    PNG = "PNG"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum, name="role_enum"), nullable=False)


class Invite(TimestampMixin, Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(Enum(RoleEnum, name="invite_role_enum"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[InviteStatusEnum] = mapped_column(
        Enum(InviteStatusEnum, name="invite_status_enum"), default=InviteStatusEnum.PENDING, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Farm(TimestampMixin, Base):
    __tablename__ = "farms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Field(TimestampMixin, Base):
    __tablename__ = "fields"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    geometry: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class FieldRevision(Base):
    __tablename__ = "field_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id"), nullable=False)
    changed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    geometry: Mapped[str] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    area_ha: Mapped[float] = mapped_column(Float, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SceneCandidate(TimestampMixin, Base):
    __tablename__ = "scene_candidates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="planetary_computer")
    collection: Mapped[str] = mapped_column(String(100), nullable=False)
    scene_id: Mapped[str] = mapped_column(String(255), nullable=False)
    acquisition_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cloud_cover: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    valid_pixel_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    assets_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class SRModelProfile(TimestampMixin, Base):
    __tablename__ = "sr_model_profiles"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_sr_model_name_version"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    supported_bands: Mapped[List[str]] = mapped_column(JSONB, default=list, nullable=False)
    scale_factor: Mapped[float] = mapped_column(Float, nullable=False, default=2.0)
    runtime_class: Mapped[str] = mapped_column(String(20), nullable=False, default="CPU")


class Observation(TimestampMixin, Base):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id"), nullable=False)
    scene_candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scene_candidates.id"), nullable=False)
    observed_on: Mapped[Date] = mapped_column(Date, nullable=False)
    status: Mapped[ObservationStatusEnum] = mapped_column(
        Enum(ObservationStatusEnum, name="observation_status_enum"), nullable=False
    )
    cloud_cover: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    valid_pixel_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    indices_native: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    indices_sr: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    sr_model_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sr_model_profiles.id"), nullable=True
    )


class AnalysisJob(TimestampMixin, Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id"), nullable=False)
    requested_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[JobStatusEnum] = mapped_column(Enum(JobStatusEnum, name="job_status_enum"), nullable=False)
    queue: Mapped[str] = mapped_column(String(50), nullable=False, default="analysis_cpu")
    params_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class LayerAsset(TimestampMixin, Base):
    __tablename__ = "layer_assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id"), nullable=False)
    observation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("observations.id"), nullable=True)
    layer_type: Mapped[LayerTypeEnum] = mapped_column(Enum(LayerTypeEnum, name="layer_type_enum"), nullable=False)
    index_name: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    tilejson_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_model_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class AlertEvent(TimestampMixin, Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    field_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id"), nullable=True)
    severity: Mapped[AlertSeverityEnum] = mapped_column(Enum(AlertSeverityEnum, name="alert_severity_enum"), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class ExportJob(TimestampMixin, Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fields.id"), nullable=False)
    requested_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    format: Mapped[ExportFormatEnum] = mapped_column(Enum(ExportFormatEnum, name="export_format_enum"), nullable=False)
    status: Mapped[JobStatusEnum] = mapped_column(Enum(JobStatusEnum, name="export_job_status_enum"), nullable=False)
    params_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class FeatureFlag(TimestampMixin, Base):
    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_feature_flags_org_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details_json: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
