"""KIS 해외 업종명 → GICS 섹터(한글명과 영문명, 예: "정보기술 (Information Technology)").

KIS 업종분류는 40여 개로 잘게 나뉘어 있어 화면에는 GICS 11개 섹터로 묶어 보여 준다.
- 업종명 기준으로 묶는다(코드는 거래소마다 다를 수 있으나 업종명 표는 같다).
- 표에 없는 업종명은 추측하지 않고 None(섹터 정보 없음)으로 둔다.
- KIS 업종이 GICS와 다르거나 업종이 비어 있는(000) 대표 종목은 SYMBOL_SECTOR로 바로잡는다.
"""


class Sector:
    IT = "정보기술 (Information Technology)"
    FINANCIALS = "금융 (Financials)"
    HEALTH_CARE = "헬스케어 (Health Care)"
    CONSUMER_DISCRETIONARY = "임의소비재 (Consumer Discretionary)"
    COMMUNICATION = "커뮤니케이션 서비스 (Communication Services)"
    INDUSTRIALS = "산업재 (Industrials)"
    CONSUMER_STAPLES = "필수소비재 (Consumer Staples)"
    ENERGY = "에너지 (Energy)"
    MATERIALS = "소재 (Materials)"
    UTILITIES = "유틸리티 (Utilities)"
    REAL_ESTATE = "부동산 (Real Estate)"


INDUSTRY_SECTOR: dict[str, str] = {
    "에너지 및 관련 서비스": Sector.ENERGY,
    "화학": Sector.MATERIALS,
    "건축자재": Sector.MATERIALS,
    "금속&채광": Sector.MATERIALS,
    "소재산업": Sector.MATERIALS,
    "우주항공 및 국방": Sector.INDUSTRIALS,
    "건설 및 건축제품": Sector.INDUSTRIALS,
    "기계 및 전기장비": Sector.INDUSTRIALS,
    "복합기업": Sector.INDUSTRIALS,
    "무역회사": Sector.INDUSTRIALS,
    "상업 및 전문서비스": Sector.INDUSTRIALS,
    "항공사 및 항공운송": Sector.INDUSTRIALS,
    "해운": Sector.INDUSTRIALS,
    "운송인프라": Sector.INDUSTRIALS,
    "자동차": Sector.CONSUMER_DISCRETIONARY,
    "자동차관련부품": Sector.CONSUMER_DISCRETIONARY,
    "섬유의복 및 호화제품": Sector.CONSUMER_DISCRETIONARY,
    "가정용 내구재": Sector.CONSUMER_DISCRETIONARY,
    "여행서비스 및 제품": Sector.CONSUMER_DISCRETIONARY,
    "소비자 서비스": Sector.CONSUMER_DISCRETIONARY,
    "도/소매": Sector.CONSUMER_DISCRETIONARY,
    "미디어": Sector.COMMUNICATION,
    "음식료 및 담배생산": Sector.CONSUMER_STAPLES,
    "가정 및 개인용품": Sector.CONSUMER_STAPLES,
    "음식료 도매": Sector.CONSUMER_STAPLES,
    "건강관리장비 및 서비스": Sector.HEALTH_CARE,
    "제약": Sector.HEALTH_CARE,
    "바이오": Sector.HEALTH_CARE,
    "상업은행": Sector.FINANCIALS,
    "보험": Sector.FINANCIALS,
    "금융서비스": Sector.FINANCIALS,
    "REIT's 및 부동산관리개발": Sector.REAL_ESTATE,
    "반도체 및 반도체장비": Sector.IT,
    "인터넷소프트웨어 및 IT서비스": Sector.IT,
    "컴퓨터전자장비/기기": Sector.IT,
    "통신장비": Sector.IT,
    "유선 및 기타 통신": Sector.COMMUNICATION,
    "무선통신": Sector.COMMUNICATION,
    "전기": Sector.UTILITIES,
    "가스": Sector.UTILITIES,
    "공익사업": Sector.UTILITIES,
}

# KIS 업종이 GICS 분류와 다르거나(결제망은 KIS에서 IT서비스) 비어 있는(000) 종목
SYMBOL_SECTOR: dict[str, str] = {
    "V": Sector.FINANCIALS,
    "MA": Sector.FINANCIALS,
    "PYPL": Sector.FINANCIALS,
    "WMT": Sector.CONSUMER_STAPLES,
    "LIN": Sector.MATERIALS,
}


def sector_for_industry(name: str | None) -> str | None:
    return INDUSTRY_SECTOR.get(name.strip()) if name else None
