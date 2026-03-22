from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "One-Person Company Control Plane"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    default_company_id: str = "default"
    state_store_backend: str = "memory"

    postgres_dsn: str = "postgresql://postgres:postgres@postgres:5432/multi_agent_company"
    redis_url: str = "redis://redis:6379/0"
    vector_db_url: str = "http://qdrant:6333"
    object_store_endpoint: str = "http://minio:9000"
    object_store_access_key: str = "minioadmin"
    object_store_secret_key: str = "minioadmin"
    feishu_bot_apps_json: str = "[]"
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    feishu_send_max_attempts: int = 3
    feishu_send_retry_backoff_seconds: float = 0.4
    feishu_stream_enabled: bool = True
    feishu_stream_chunk_chars: int = 260
    feishu_stream_chunk_delay_seconds: float = 0.12
    feishu_visible_handoff_turn_limit: int = 20
    openclaw_model_config_path: str = "docs/development-plan/openclaw-model-config.json"
    openclaw_bailian_api_key: str = ""
    openclaw_runtime_mode: str = "gateway"
    openclaw_gateway_base_url: str = "http://openclaw-gateway:18789"
    openclaw_gateway_token: str = ""
    openclaw_gateway_api_key: str = ""
    openclaw_gateway_timeout_seconds: int = 25
    openclaw_runtime_home: str = ".runtime/openclaw/home"
    openclaw_gateway_host_port: int = 18789
    openclaw_visible_follow_up_limit: int = 3
    openclaw_control_ui_auto_pair_local: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
