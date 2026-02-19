from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8002, alias="APP_PORT")

    database_url: str = Field(alias="DATABASE_URL")

    redis_url: str = Field(alias="REDIS_URL")
    celery_broker_url: str = Field(alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(alias="CELERY_RESULT_BACKEND")

    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_refresh_secret_key: str = Field(alias="JWT_REFRESH_SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")

    s3_endpoint_url: str = Field(alias="S3_ENDPOINT_URL")
    s3_public_endpoint_url: str | None = Field(default=None, alias="S3_PUBLIC_ENDPOINT_URL")
    s3_region: str = Field(alias="S3_REGION")
    s3_bucket: str = Field(alias="S3_BUCKET")
    s3_access_key: str = Field(alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(alias="S3_SECRET_KEY")
    s3_secure: bool = Field(default=False, alias="S3_SECURE")

    pc_stac_url: str = Field(alias="PC_STAC_URL")
    pc_subscription_key: str | None = Field(default=None, alias="PC_SUBSCRIPTION_KEY")
    tiler_internal_url: str = Field(default="http://tiler:8081", alias="TILER_INTERNAL_URL")

    sr_analytics_default: bool = Field(default=False, alias="SR_ANALYTICS_DEFAULT")
    sr_provider: str = Field(default="sr4rs", alias="SR_PROVIDER")

    sr4rs_script_path: str = Field(default="/opt/sr4rs/code/sr.py", alias="SR4RS_SCRIPT_PATH")
    sr4rs_model_dir: str = Field(
        default="/workspace/.cache/sr4rs/sr4rs_sentinel2_bands4328_france2020_savedmodel",
        alias="SR4RS_MODEL_DIR",
    )
    sr4rs_model_url: str = Field(
        default="https://nextcloud.inrae.fr/s/6xM4jRzYx2A9Qn4/download?path=%2F&files=sr4rs_sentinel2_bands4328_france2020_savedmodel.zip",
        alias="SR4RS_MODEL_URL",
    )
    sr4rs_timeout_seconds: int = Field(default=1800, alias="SR4RS_TIMEOUT_SECONDS")
    sr4rs_scale_factor: int = Field(default=4, alias="SR4RS_SCALE_FACTOR")
    sr4rs_python_executable: str = Field(default="python3", alias="SR4RS_PYTHON_EXECUTABLE")

    s2dr3_external_endpoint: str | None = Field(default=None, alias="S2DR3_EXTERNAL_ENDPOINT")
    s2dr3_external_api_key: str | None = Field(default=None, alias="S2DR3_EXTERNAL_API_KEY")
    s2dr3_command_template: str | None = Field(default=None, alias="S2DR3_COMMAND_TEMPLATE")
    s2dr3_band_order: str = Field(default="B02,B03,B04,B08", alias="S2DR3_BAND_ORDER")
    s2dr3_scale_factor: int = Field(default=10, alias="S2DR3_SCALE_FACTOR")
    s2dr3_timeout_seconds: int = Field(default=1800, alias="S2DR3_TIMEOUT_SECONDS")

    cloud_cap_percent: float = Field(default=20.0, alias="CLOUD_CAP_PERCENT")
    min_valid_pixel_ratio: float = Field(default=0.60, alias="MIN_VALID_PIXEL_RATIO")
    min_scene_coverage_ratio: float = Field(default=0.98, alias="MIN_SCENE_COVERAGE_RATIO")
    cors_allowed_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ALLOWED_ORIGINS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
