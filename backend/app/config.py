from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Blank locally -> SQLite. Injected on Render -> Postgres. (Same var both envs.)
    database_url: str = ""
    sqlite_path: str = "./data.sqlite"
    port: int = 3001
    node_env: str = "development"  # kept name for parity with the deploy config

    # Comma-separated CORS allow-list. Blank in prod (the API is same-origin —
    # nginx serves the SPA and proxies /api, so no cross-origin call is made).
    # Set e.g. "https://app.example.com" only if the SPA is ever hosted apart
    # from the API. Never use "*" here: that plus credentials is a known footgun.
    cors_allowed_origins: str = ""

    @property
    def is_production(self) -> bool:
        return self.node_env == "production"

    @property
    def allowed_origins(self) -> list[str]:
        """Resolved CORS allow-list.

        Explicit env override wins. Otherwise: localhost dev origins in
        development, and an empty list in production (same-origin deploy).
        """
        if self.cors_allowed_origins.strip():
            return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
        if not self.is_production:
            return ["http://localhost:5173", "http://127.0.0.1:5173"]
        return []


settings = Settings()
