from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class SchedulerSettings(BaseSettings):
    followup_interval_sec: int = 5
    scheduled_interval_sec: int = 15
    reply_poll_interval_sec: int = 30
    working_hours_start: int = 10
    working_hours_end: int = 17
    working_days: str = "1-5"
    timezone: str = "Asia/Kolkata"
    reply_cleanup_hours_ist: str = "10,16"

    class Config:
        env_prefix = "SCHEDULER_"


class FollowupSettings(BaseSettings):
    max_auto_sends_per_cycle: int = 200
    max_parallel_workers: int = 2
    cooldown_sec: float = 1.5
    client_max_stage: int = 2
    client_intervals: str = "0:2,1:4"
    investor_max_stage: int = 3
    investor_intervals: str = "0:2,1:4,2:6"

    class Config:
        env_prefix = "FOLLOWUP_"


class EmailSettings(BaseSettings):
    default_cc: str = "lalit.h@qvscl.com"
    vismaya_cc: str = "rajesh.s@qvscl.com"
    default_sender_email: str = "system@qvscl.com"
    frontend_url: str = "https://leadstreamai.onrender.com"
    backend_url: str = "https://lead-backend-g9de.onrender.com"
    tracking_enabled_default: bool = True

    class Config:
        env_prefix = "EMAIL_"


class LLMSettings(BaseSettings):
    anthropic_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    claude_model: str = "claude-3-5-sonnet-20240620"
    gemini_model: str = "gemini-3-flash-preview"
    groq_model: str = "llama-3.3-70b-versatile"

    class Config:
        env_prefix = "LLM_"


class EmailEngineSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    queue_name: str = "emails"
    scheduled_queue_name: str = "emails_scheduled"
    dead_letter_queue_name: str = "emails_dlq"
    workers_per_user: int = 2
    max_total_workers: int = 8
    gmail_rate_limit_per_sec: int = 100
    gmail_burst_limit: int = 200
    max_retries: int = 3
    retry_base_delay_sec: int = 30
    retry_max_delay_sec: int = 300
    idempotency_ttl_hours: int = 24
    template_dir: str = "app/email_engine/templates"
    template_cache_size: int = 100

    class Config:
        env_prefix = "EMAIL_ENGINE_"


class DatabaseSettings(BaseSettings):
    database_url: str
    db_pool_min: int = 2
    db_pool_max: int = 10

    class Config:
        env_prefix = "DB_"


class AppSettings(BaseSettings):
    debug: bool = False
    admin_username: str = "admin"
    admin_password: str = "admin123"
    cors_allowed_origins: str = ""
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: Optional[str] = None
    family_offices_path: Optional[str] = None
    rag_url: str = "https://rag-sys-gz59.onrender.com"
    rag_timeout: int = 300

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()


@lru_cache()
def get_scheduler_settings() -> SchedulerSettings:
    return SchedulerSettings()


@lru_cache()
def get_followup_settings() -> FollowupSettings:
    return FollowupSettings()


@lru_cache()
def get_email_settings() -> EmailSettings:
    return EmailSettings()


@lru_cache()
def get_llm_settings() -> LLMSettings:
    return LLMSettings()


@lru_cache()
def get_email_engine_settings() -> EmailEngineSettings:
    return EmailEngineSettings()


@lru_cache()
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()