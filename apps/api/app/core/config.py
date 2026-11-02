"""환경변수 기반 설정. 민감 값은 SecretStr로 보관해 repr/로그에 노출되지 않게 한다."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    valuation_currency: str = Field(default="KRW", pattern=r"^[A-Z]{3}$")
    mock_data_dir: Path = REPO_ROOT / "data" / "mock"

    # LIVE 접근 제어 (Phase 3에서 토큰 검증기를 연결한다)
    supabase_url: str | None = None
    supabase_jwt_secret: SecretStr | None = None
    live_owner_user_id: str | None = None

    # 한국투자증권 (Phase 4)
    kis_app_key: SecretStr | None = None
    kis_app_secret: SecretStr | None = None
    kis_account_no: SecretStr | None = None

    # OpenAI (Phase 5)
    openai_api_key: SecretStr | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
