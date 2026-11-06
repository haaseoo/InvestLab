"""사용자 KIS 키 암호화(AES-256-GCM).

- 마스터 키는 서버 환경변수(KIS_CREDENTIAL_KEY)에만 있다. DB에는 암호문만 저장한다.
- 연관 데이터(AAD)에 사용자 id와 용도를 넣는다. 다른 사용자의 행이나 다른 열로 암호문을
  옮겨 붙이면 복호화가 실패한다.
- 저장 형식: 버전(1바이트) + nonce(12바이트) + 암호문·태그. 버전은 키 교체에 대비해 둔다.
"""

import base64
import binascii
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

FORMAT_VERSION = 1
NONCE_BYTES = 12


class CredentialKeyError(ValueError):
    """마스터 키 형식이 잘못됐다."""


class DecryptionError(Exception):
    """암호문이 손상됐거나, 다른 키·사용자·용도로 만든 것이다."""


def generate_key() -> str:
    return base64.b64encode(AESGCM.generate_key(bit_length=256)).decode()


class CredentialCipher:
    def __init__(self, key_b64: str):
        try:
            key = base64.b64decode(key_b64, validate=True)
        except (binascii.Error, ValueError):
            raise CredentialKeyError("KIS_CREDENTIAL_KEY는 base64 문자열이어야 합니다.") from None
        if len(key) != 32:
            raise CredentialKeyError("KIS_CREDENTIAL_KEY는 32바이트(AES-256) 키여야 합니다.")
        self._aead = AESGCM(key)

    @staticmethod
    def _aad(user_id: str, purpose: str) -> bytes:
        return f"investlab:kis:{purpose}:{user_id}".encode()

    def encrypt(self, plaintext: bytes, *, user_id: str, purpose: str) -> bytes:
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._aead.encrypt(nonce, plaintext, self._aad(user_id, purpose))
        return bytes([FORMAT_VERSION]) + nonce + sealed

    def decrypt(self, blob: bytes, *, user_id: str, purpose: str) -> bytes:
        if len(blob) < 1 + NONCE_BYTES + 16 or blob[0] != FORMAT_VERSION:
            raise DecryptionError()
        nonce, sealed = blob[1 : 1 + NONCE_BYTES], blob[1 + NONCE_BYTES :]
        try:
            return self._aead.decrypt(nonce, sealed, self._aad(user_id, purpose))
        except InvalidTag:
            raise DecryptionError() from None
