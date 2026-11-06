"""사용자 한 명의 KIS 인증정보. repr·로그에 값이 나오지 않게 한다."""

import json
import re
from dataclasses import dataclass

from app.core.errors import KisCredentialsInputError
from app.core.logging import mask_account

# 공식 발급 형식은 영숫자 App Key(36자)와 base64 형태 App Secret(180자)이다. 길이는 여유를 둔다.
_APP_KEY = re.compile(r"[A-Za-z0-9]{16,64}")
_APP_SECRET = re.compile(r"[A-Za-z0-9+/=]{32,512}")
_ACCOUNT = re.compile(r"(\d{8})-?(\d{2})")


@dataclass(frozen=True, repr=False)
class KisCredentials:
    app_key: str
    app_secret: str
    cano: str  # 계좌 8자리
    product: str  # 상품코드 2자리

    @classmethod
    def parse(cls, app_key: str, app_secret: str, account_no: str) -> "KisCredentials":
        """입력값 검증. 실패 사유에 입력값 자체는 싣지 않는다."""
        reasons = []
        app_key, app_secret, account_no = app_key.strip(), app_secret.strip(), account_no.strip()
        if not _APP_KEY.fullmatch(app_key):
            reasons.append("App Key 형식이 올바르지 않습니다.")
        if not _APP_SECRET.fullmatch(app_secret):
            reasons.append("App Secret 형식이 올바르지 않습니다.")
        account = _ACCOUNT.fullmatch(account_no)
        if not account:
            reasons.append("계좌번호는 8자리-2자리 형식이어야 합니다(예: 12345678-01).")
        if reasons or account is None:
            raise KisCredentialsInputError(details={"reasons": reasons})
        return cls(app_key, app_secret, account.group(1), account.group(2))

    @property
    def account_masked(self) -> str:
        return mask_account(self.cano + self.product)

    def to_json(self) -> bytes:
        return json.dumps(
            {
                "app_key": self.app_key,
                "app_secret": self.app_secret,
                "account_no": f"{self.cano}-{self.product}",
            }
        ).encode()

    @classmethod
    def from_json(cls, raw: bytes) -> "KisCredentials":
        data = json.loads(raw)
        return cls.parse(data["app_key"], data["app_secret"], data["account_no"])

    def __repr__(self) -> str:
        return f"KisCredentials(account={self.account_masked})"
