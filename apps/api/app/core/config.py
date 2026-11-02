"""환경변수 기반 설정. 민감 값은 SecretStr로 보관해 repr/로그에 노출되지 않게 한다."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    valuation_currency: str = Field(default="KRW", pattern=r"^[A-Z]{3}$")
    mock_data_dir: Path = REPO_ROOT / "data" / "mock"

    # Supabase Auth. 토큰은 {supabase_url}/auth/v1/.well-known/jwks.json의 공개 키로 검증한다.
    # 대칭키(JWT secret) 방식은 쓰지 않는다.
    supabase_url: str | None = None
    jwt_audience: str = "authenticated"
    jwt_leeway_seconds: int = Field(default=30, ge=0, le=120)
    # LIVE 계좌를 조회할 수 있는 유일한 사용자. 비어 있으면 LIVE 접근은 모두 거부된다.
    live_owner_user_id: str | None = None

    # PostgreSQL 연결 문자열(서버 전용). 사용자 데이터 조회 시에는 트랜잭션마다
    # authenticated 역할로 전환해 RLS를 적용받는다.
    database_url: SecretStr | None = None

    # 한국투자증권 (Phase 4)
    kis_app_key: SecretStr | None = None
    kis_app_secret: SecretStr | None = None
    kis_account_no: SecretStr | None = None

    # OpenAI (Phase 5)
    openai_api_key: SecretStr | None = None

    @field_validator(
        "supabase_url",
        "live_owner_user_id",
        "database_url",
        "kis_app_key",
        "kis_app_secret",
        "kis_account_no",
        "openai_api_key",
        mode="before",
    )
    @classmethod
    def _blank_is_unset(cls, value):
        # .env에 "KEY=" 처럼 비워 둔 값은 설정하지 않은 것으로 본다.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
