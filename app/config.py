from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Shopee MCP"
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    SHOPEE_PARTNER_ID: int = 0
    SHOPEE_PARTNER_KEY: str = ""

    SHOPEE_LIVE_PARTNER_ID: int = 0
    SHOPEE_LIVE_PARTNER_KEY: str = ""

    SHOPEE_REDIRECT_URL: str = ""

    SHOPEE_SANDBOX_URL: str = "https://openplatform.sandbox.test-stable.shopee.sg"
    SHOPEE_PRODUCTION_URL: str = "https://partner.shopeemobile.com"

    MCP_API_KEY: str = ""

    DEFAULT_TIMEOUT: int = 30
    TOKEN_REFRESH_BEFORE_SECONDS: int = 600

    # Google Sheets (for sheets_tools)
    GOOGLE_SERVICE_ACCOUNT_FILE: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    SHEETS_MAX_ROWS: int = 500
    SHEETS_RAW_TAB_THRESHOLD: int = 1000

    DATA_DIR: str = "./data"
    LOG_DIR: str = "./logs"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def get_base_url(self, environment: str = "sandbox") -> str:
        if environment == "production":
            return self.SHOPEE_PRODUCTION_URL
        return self.SHOPEE_SANDBOX_URL

    def get_partner_credentials(self, environment: str = "sandbox") -> tuple[int, str]:
        if environment == "production" and self.SHOPEE_LIVE_PARTNER_ID:
            return self.SHOPEE_LIVE_PARTNER_ID, self.SHOPEE_LIVE_PARTNER_KEY
        return self.SHOPEE_PARTNER_ID, self.SHOPEE_PARTNER_KEY


settings = Settings()
