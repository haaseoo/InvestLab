import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from app.core.auth import SupabaseTokenVerifier
from app.core.config import Settings, get_settings
from app.core.crypto import CredentialCipher
from app.core.errors import AppError, DatabaseUnavailableError
from app.core.logging import install_log_masking
from app.db.database import Database
from app.integrations.kis.master import OverseasMaster
from app.providers.mock import MockPortfolioProvider
from app.routers import account, analytics, kis, portfolio, simulations, snapshots
from app.services.live_accounts import LiveAccounts

logger = logging.getLogger("investlab")


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    install_log_masking()
    settings = settings or get_settings()

    app = FastAPI(title="InvestLab API", version="0.1.0")
    app.state.settings = settings
    # SUPABASE_URL이 없으면 검증기가 없고, 로그인이 필요한 요청은 모두 거부된다.
    app.state.token_verifier = (
        SupabaseTokenVerifier(
            settings.supabase_url,
            audience=settings.jwt_audience,
            leeway_seconds=settings.jwt_leeway_seconds,
        )
        if settings.supabase_url
        else None
    )
    # DATABASE_URL이 없으면 저장 기능만 비활성화된다. Mock 조회는 DB 없이 동작한다.
    app.state.db = (
        Database(settings.database_url.get_secret_value()) if settings.database_url else None
    )
    app.state.mock_provider = MockPortfolioProvider(settings.mock_data_dir)
    # LIVE는 사용자마다 본인 키로 만든 Provider를 쓴다. 키 형식이 잘못됐으면 시작하지 않는다.
    app.state.live_accounts = LiveAccounts(
        db=app.state.db,
        cipher=(
            CredentialCipher(settings.kis_credential_key.get_secret_value())
            if settings.kis_credential_key
            else None
        ),
        master=OverseasMaster(settings.kis_master_cache_dir),
        classification_file=settings.live_classification_file,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        # 금융 데이터가 브라우저·프록시 캐시에 남지 않게 한다.
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        fields = [".".join(str(p) for p in e["loc"]) for e in errors]
        # 입력값 자체는 응답에 다시 싣지 않는다. 항목과 사유만 돌려준다.
        reasons = [str(e["msg"]).removeprefix("Value error, ") for e in errors]
        return _error(
            422,
            "VALIDATION_ERROR",
            "요청 값이 올바르지 않습니다.",
            {"fields": fields, "reasons": reasons},
        )

    @app.exception_handler(DBAPIError)
    async def handle_db_error(_: Request, exc: DBAPIError) -> JSONResponse:
        # 원인 메시지에는 SQL이 들어갈 수 있으므로 응답에 싣지 않는다.
        logger.error(
            "Database error: %s", type(exc.orig).__name__ if exc.orig else type(exc).__name__
        )
        error = DatabaseUnavailableError()
        return _error(error.status_code, error.code, error.message)

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error", exc_info=exc)
        return _error(500, "INTERNAL_ERROR", "서버 오류가 발생했습니다.")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(portfolio.router)
    app.include_router(analytics.router)
    app.include_router(simulations.router)
    app.include_router(account.router)
    app.include_router(snapshots.router)
    app.include_router(kis.router)
    return app


app = create_app()
