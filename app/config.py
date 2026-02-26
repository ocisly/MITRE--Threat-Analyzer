from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database — sqlite for local dev, mssql+pyodbc for Azure SQL production
    database_url: str = "sqlite:///./data/mitre.db"

    # STIX data cache directory
    stix_data_dir: Path = Path("./data/stix")

    # MITRE sync
    mitre_domains: list[str] = ["enterprise-attack"]
    sync_interval_hours: int = 24

    # Azure OpenAI (required for Phase 2+)
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_key: str = ""  # local dev only; production uses Managed Identity

    # Application
    debug: bool = True
    frontend_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
