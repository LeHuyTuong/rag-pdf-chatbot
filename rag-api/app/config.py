from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=('.env', '../.env'), extra='ignore')

    db_connection: str = Field('mysql', alias='DB_CONNECTION')
    db_host: str = Field('127.0.0.1', alias='DB_HOST')
    db_port: int = Field(3306, alias='DB_PORT')
    db_database: str = Field('rag', alias='DB_DATABASE')
    db_username: str = Field('raguser', alias='DB_USERNAME')
    db_password: str = Field('ragpass', alias='DB_PASSWORD')
    qdrant_url: str = Field('http://localhost:6333', alias='QDRANT_URL')
    qdrant_collection: str = Field('rag_chunks', alias='QDRANT_COLLECTION')
    qdrant_api_key: str | None = Field(None, alias='QDRANT_API_KEY')
    qdrant_local_path: str | None = Field(None, alias='QDRANT_LOCAL_PATH')
    embedding_model: str = Field('sentence-transformers/all-MiniLM-L6-v2', alias='EMBEDDING_MODEL')
    embedding_dimension: int = Field(384, alias='EMBEDDING_DIMENSION')
    chunk_size: int = Field(700, alias='CHUNK_SIZE')
    chunk_overlap: int = Field(120, alias='CHUNK_OVERLAP')
    top_k: int = Field(12, alias='TOP_K')
    retrieve_top_k: int | None = Field(None, alias='RETRIEVE_TOP_K')
    max_context_chunks: int = Field(5, alias='MAX_CONTEXT_CHUNKS')
    min_score: float = Field(0.50, alias='MIN_SCORE')
    llm_provider: str = Field('openai', alias='LLM_PROVIDER')
    llm_base_url: str | None = Field(None, alias='LLM_BASE_URL')
    llm_api_key: str | None = Field(None, alias='LLM_API_KEY')
    llm_model: str | None = Field(None, alias='LLM_MODEL')
    llm_fallback_model: str | None = Field(None, alias='LLM_FALLBACK_MODEL')
    openai_api_key: str | None = Field(None, alias='OPENAI_API_KEY')
    openai_model: str = Field('gpt-4o-mini', alias='OPENAI_MODEL')
    storage_path: str = Field('/app/storage/uploads', alias='STORAGE_PATH')
    debug_report_path: str = Field('/app/storage/debug', alias='DEBUG_REPORT_PATH')
    fast_test_mode: bool = Field(False, alias='FAST_TEST_MODE')

    def model_post_init(self, __context) -> None:
        if self.retrieve_top_k is not None:
            self.top_k = self.retrieve_top_k

    @property
    def mysql_config(self) -> dict:
        return {
            'host': self.db_host,
            'port': self.db_port,
            'user': self.db_username,
            'password': self.db_password,
            'database': self.db_database,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
