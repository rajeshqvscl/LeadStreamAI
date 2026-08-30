from functools import lru_cache

from pydantic_settings import BaseSettings


class FeatureFlags(BaseSettings):
    use_pipeline_state: bool = False
    use_email_engine: bool = False
    use_campaign_resolver: bool = False
    use_followup_engine: bool = False
    use_reply_classifier: bool = False
    use_reply_workflow: bool = False
    use_lead_classifier: bool = False
    use_jinja2_templates: bool = False
    use_structured_logging: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "FEATURE_"
        case_sensitive = False


@lru_cache
def get_feature_flags() -> FeatureFlags:
    return FeatureFlags()
