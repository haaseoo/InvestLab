"""로그 마스킹. LogRecord factory에 걸어 모든 로거의 메시지에 일괄 적용한다."""

import logging
import re
import traceback

_BEARER = re.compile(r"Bearer\s+[\w\-.~+/]+=*", re.IGNORECASE)
_SECRET_PAIR = re.compile(
    r"(app_?key|app_?secret|access_?token|api_?key|secret|token|password)"
    r"([\"'\s:=]+)([^\s\"',&]+)",
    re.IGNORECASE,
)
_ACCOUNT = re.compile(r"\b\d{8}-?\d{2}\b")
# postgresql://user:password@host 형태의 연결 문자열
_DSN = re.compile(r"\b(postgres(?:ql)?(?:\+\w+)?)://[^\s:/@]+:[^\s@]+@", re.IGNORECASE)
# JWT(header.payload.signature)
_JWT = re.compile(r"\beyJ[\w-]{5,}\.[\w-]{5,}\.[\w-]+")
_SUPABASE_KEY = re.compile(r"\bsb_(publishable|secret)_[\w-]+")


def mask_sensitive(text: str) -> str:
    text = _DSN.sub(r"\1://***:***@", text)
    text = _JWT.sub("<jwt>", text)
    text = _SUPABASE_KEY.sub(r"sb_\1_***", text)
    text = _BEARER.sub("Bearer ***", text)
    text = _SECRET_PAIR.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return _ACCOUNT.sub("********-**", text)


def mask_account(account_no: str) -> str:
    """계좌번호는 마지막 2자리만 남긴다. 화면·로그 표시용."""
    digits = re.sub(r"\D", "", account_no)
    return f"{'*' * max(len(digits) - 2, 0)}{digits[-2:]}"


def install_log_masking() -> None:
    """이미 설치되어 있으면 다시 감싸지 않는다."""
    factory = logging.getLogRecordFactory()
    if getattr(factory, "_investlab_masking", False):
        return

    def masking_factory(*args, **kwargs):
        record = factory(*args, **kwargs)
        if record.name == "uvicorn.access":
            # uvicorn의 접근 로그 포매터는 args 5개를 직접 풀어 쓰므로 구조를 유지해야 한다.
            record.args = tuple(
                mask_sensitive(arg) if isinstance(arg, str) else arg for arg in record.args or ()
            )
            return record
        if record.exc_info and record.exc_info[0] is not None:
            # 포매터는 exc_text가 있으면 다시 만들지 않으므로, 마스킹한 트레이스백을 미리 넣어 둔다.
            record.exc_text = mask_sensitive("".join(traceback.format_exception(*record.exc_info)))
        try:
            record.msg = mask_sensitive(record.getMessage())
            record.args = ()
        except (TypeError, ValueError):
            # 형식이 잘못된 로그 호출이 애플리케이션을 멈추게 하지 않는다. 원문은 남기지 않는다.
            record.msg, record.args = "<log message masked: invalid format>", ()
        return record

    masking_factory._investlab_masking = True  # type: ignore[attr-defined]
    logging.setLogRecordFactory(masking_factory)
