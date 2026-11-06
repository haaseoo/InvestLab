"""본인 한국투자증권 키 등록·확인·삭제. 모두 로그인이 필요하다.

- 등록할 때 실제로 잔고를 한 번 조회해 키와 계좌가 맞는지 확인하고, 맞을 때만 암호화해 저장한다.
- 응답에는 등록 여부와 가린 계좌번호만 싣는다. 키는 어디에도 다시 내보내지 않는다.
"""

from fastapi import APIRouter, Response, status

from app.integrations.kis.credentials import KisCredentials
from app.routers.deps import LiveAccountsDep, UserDep
from app.schemas.user_data import KisCredentialsInput, KisCredentialsStatus
from app.services.live_accounts import CredentialStatus

router = APIRouter(prefix="/api/v1/kis/credentials")


def _status(s: CredentialStatus) -> KisCredentialsStatus:
    return KisCredentialsStatus(
        registered=s.registered, account_masked=s.account_masked, updated_at=s.updated_at
    )


@router.get("", response_model=KisCredentialsStatus)
async def get_credentials(user: UserDep, live_accounts: LiveAccountsDep) -> KisCredentialsStatus:
    return _status(await live_accounts.status(user))


@router.put("", response_model=KisCredentialsStatus)
async def put_credentials(
    body: KisCredentialsInput, user: UserDep, live_accounts: LiveAccountsDep
) -> KisCredentialsStatus:
    credentials = KisCredentials.parse(
        body.app_key.get_secret_value(),
        body.app_secret.get_secret_value(),
        body.account_no.get_secret_value(),
    )
    return _status(await live_accounts.register(user, credentials))


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credentials(user: UserDep, live_accounts: LiveAccountsDep) -> Response:
    await live_accounts.remove(user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
