from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Blank locally -> SQLite. Injected on Render -> Postgres. (Same var both envs.)
    database_url: str = ""
    sqlite_path: str = "./data.sqlite"
    port: int = 3001
    node_env: str = "development"  # kept name for parity with the deploy config

    @property
    def is_production(self) -> bool:
        return self.node_env == "production"


settings = Settings()
