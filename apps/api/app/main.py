import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.logging import install_log_masking
from app.providers.kis import KISPortfolioProvider
from app.providers.mock import MockPortfolioProvider
from app.routers import analytics, portfolio, simulations
from app.schemas.portfolio import Source

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
    # 토큰 검증기는 Phase 3에서 연결한다. None인 동안 LIVE 접근은 모두 거부된다.
    app.state.token_verifier = None
    app.state.providers = {
        Source.MOCK: MockPortfolioProvider(settings.mock_data_dir),
        Source.LIVE: KISPortfolioProvider(settings, auth_available=False),
    }

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST"],
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
    return app


app = create_app()
