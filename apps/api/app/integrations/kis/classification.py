"""KIS가 제공하지 않는 분류(ETF 유형, 투자 대상 국가, 섹터, 추종 지수)를 사용자가 직접 지정하는 파일.

파일: data/live/classifications.json (.gitignore 대상. 보유 종목이 드러나므로 커밋하지 않는다)
형식은 data/live/classifications.example.json 참고. 파일이 없으면 해당 값은 미분류로 둔다.
"""

import json
import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from app.schemas.portfolio import AssetClass

logger = logging.getLogger("investlab.kis")


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_class: AssetClass | None = None
    exposure_country: str | None = None
    sector: str | None = None
    benchmark: str | None = None


class ClassificationFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    holdings: dict[str, Classification] = {}


def load_classifications(path: Path | None) -> dict[str, Classification]:
    """파일 오류는 조회를 막지 않는다. 경고만 남기고 분류 없이 진행한다."""
    if path is None or not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return ClassificationFile.model_validate(raw).holdings
    except (OSError, ValueError, ValidationError):
        logger.warning("Live classification file is invalid and was ignored")
        return {}
