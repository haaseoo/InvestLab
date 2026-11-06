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


class AuthNotConfiguredError(AppError):
    status_code = 503
    code = "AUTH_NOT_CONFIGURED"
    message = "사용자 인증이 아직 구성되지 않아 LIVE 데이터를 조회할 수 없습니다."


class KisNotConfiguredError(AppError):
    status_code = 409
    code = "KIS_NOT_CONFIGURED"
    message = (
        "한국투자증권 키가 등록되지 않았습니다. 설정에서 App Key·Secret·계좌번호를 등록해 주세요."
    )


class KisCredentialStoreNotConfiguredError(AppError):
    status_code = 503
    code = "KIS_CREDENTIAL_STORE_NOT_CONFIGURED"
    message = "서버에 키 암호화 설정(KIS_CREDENTIAL_KEY)이 없어 한국투자증권 키를 저장·사용할 수 없습니다."


class KisCredentialsUnreadableError(AppError):
    status_code = 409
    code = "KIS_CREDENTIALS_UNREADABLE"
    message = "저장된 한국투자증권 키를 읽을 수 없습니다. 설정에서 다시 등록해 주세요."


class KisCredentialsInputError(AppError):
    status_code = 422
    code = "INVALID_KIS_CREDENTIALS"
    message = "한국투자증권 키 입력값이 올바르지 않습니다."


class KisAuthError(AppError):
    status_code = 503
    code = "KIS_AUTH_FAILED"
    message = "한국투자증권 접근 토큰을 발급받지 못했습니다. App Key·Secret을 확인해 주세요."


class KisRateLimitedError(AppError):
    status_code = 503
    code = "KIS_RATE_LIMITED"
    message = "한국투자증권 호출 한도에 걸렸습니다. 잠시 후 다시 시도해 주세요."


class KisUnavailableError(AppError):
    status_code = 503
    code = "KIS_UNAVAILABLE"
    message = "한국투자증권 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."


class KisApiError(AppError):
    status_code = 502
    code = "KIS_API_ERROR"
    message = "한국투자증권이 오류를 반환했습니다."


class KisResponseError(AppError):
    status_code = 502
    code = "KIS_RESPONSE_INVALID"
    message = "한국투자증권 응답 형식이 예상과 달라 데이터를 사용하지 않았습니다."


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


class AuthUnavailableError(AppError):
    status_code = 503
    code = "AUTH_UNAVAILABLE"
    message = "인증 서버의 공개 키를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요."


class DatabaseNotConfiguredError(AppError):
    status_code = 503
    code = "DB_NOT_CONFIGURED"
    message = "데이터베이스가 연결되지 않아 저장 기능을 사용할 수 없습니다."


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "DB_UNAVAILABLE"
    message = "데이터베이스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "요청한 데이터를 찾을 수 없습니다."


class MockSnapshotForbiddenError(AppError):
    status_code = 422
    code = "MOCK_SNAPSHOT_FORBIDDEN"
    message = "Mock 데이터는 가상 데이터라 투자 실적 스냅샷으로 저장할 수 없습니다."


class SnapshotIntegrityError(AppError):
    status_code = 422
    code = "SNAPSHOT_INTEGRITY"
    message = "스냅샷 데이터가 일관되지 않아 저장하지 않았습니다."


class SnapshotExistsError(AppError):
    status_code = 409
    code = "SNAPSHOT_EXISTS"
    message = "같은 기준 시각의 스냅샷이 이미 저장되어 있습니다."
