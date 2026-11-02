"""API 공통 오류. 모든 오류 응답은 {"error": {code, message, details}} 형태다."""

from typing import Any


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "서버 오류가 발생했습니다."

    def __init__(self, message: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.details = details or {}


class AuthRequiredError(AppError):
    status_code = 401
    code = "AUTH_REQUIRED"
    message = "LIVE 데이터는 로그인한 사용자만 조회할 수 있습니다."


class InvalidTokenError(AppError):
    status_code = 401
    code = "INVALID_TOKEN"
    message = "인증 토큰이 유효하지 않습니다."


class LiveForbiddenError(AppError):
    status_code = 403
    code = "LIVE_FORBIDDEN"
    message = "이 계정은 연결된 증권 계좌를 조회할 권한이 없습니다."


class AuthNotConfiguredError(AppError):
    status_code = 503
    code = "AUTH_NOT_CONFIGURED"
    message = "사용자 인증이 아직 구성되지 않아 LIVE 데이터를 조회할 수 없습니다."


class LiveOwnerNotConfiguredError(AppError):
    status_code = 503
    code = "LIVE_OWNER_NOT_CONFIGURED"
    message = "LIVE 계좌 소유자가 지정되지 않아 LIVE 데이터를 조회할 수 없습니다."


class LiveNotImplementedError(AppError):
    status_code = 503
    code = "LIVE_NOT_IMPLEMENTED"
    message = "한국투자증권 연동이 아직 구현되지 않았습니다."


class MockDataError(AppError):
    status_code = 500
    code = "MOCK_DATA_UNAVAILABLE"
    message = "Mock 데이터를 읽을 수 없습니다."


class HoldingNotFoundError(AppError):
    status_code = 404
    code = "HOLDING_NOT_FOUND"
    message = "보유 종목에서 찾을 수 없습니다."


class SimulationInputError(AppError):
    status_code = 422
    code = "INVALID_SIMULATION_INPUT"
    message = "시뮬레이션 입력값이 올바르지 않습니다."
