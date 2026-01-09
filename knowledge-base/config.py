from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    elasticsearch_url: str = "http://localhost:9200"
    index_name: str = "open_rabbit_knowledge_base"
    
    redis_url: str = "redis://localhost:6379/0"
    
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4"
    
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"


settings = Settings()
