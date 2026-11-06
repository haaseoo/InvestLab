"""KIS 가짜 서버(httpx.MockTransport). 실제 KIS에 접속하지 않는다.

값은 테스트용 임의 숫자이며 실제 계좌·시세가 아니다. 필드 이름과 형태(문자열 숫자, 소수 자릿수)는
2026-11-02 실제 응답 구조를 따른다.
"""

import json
from dataclasses import dataclass, field

import httpx

APP_KEY = "PStestappkey0000000000000000000000000"
APP_SECRET = "testsecret" + "x" * 170
ACCOUNT = "12345678-01"
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.fake-kis-token.signature"


def domestic_row(**over):
    row = {
        "pdno": "005930",
        "prdt_name": "테스트전자",
        "hldg_qty": "10",
        "pchs_avg_pric": "70000.0000",
        "prpr": "75000",
        "evlu_amt": "750000",
    }
    return {**row, **over}


def overseas_row(**over):
    row = {
        "pdno": "AAAA",
        "prdt_name": "테스트 주식",
        "cblc_qty13": "1.00000000",
        "ccld_qty_smtl1": "2.00000000",
        "avg_unpr3": "100.00000000",
        "ovrs_now_pric1": "110.00000",
        "frcr_evlu_amt2": "220.00000",
        "frcr_pchs_amt": "200.00000",
        "buy_crcy_cd": "USD",
        "ovrs_excg_cd": "NASD",
        "bass_exrt": "1400.00000000",
    }
    return {**row, **over}


@dataclass
class FakeKis:
    domestic_rows: list = field(default_factory=lambda: [domestic_row()])
    overseas_rows: list = field(
        default_factory=lambda: [
            overseas_row(),
            overseas_row(
                pdno="BBBB",
                ovrs_excg_cd="AMEX",
                ccld_qty_smtl1="3.00000000",
                avg_unpr3="50.00000000",
                ovrs_now_pric1="60.00000",
                frcr_evlu_amt2="180.00000",
            ),
        ]
    )
    fx_rate: str = "1400.00000000"
    domestic_kind: dict = field(default_factory=lambda: {"005930": "ST"})
    # 응답을 바꾸고 싶을 때: (path) -> httpx.Response | None
    override: object = None
    token_status: int = 200
    # 업종별코드조회 응답(거래소 → 행). 이름은 테스트용 값이다.
    industries: dict = field(
        default_factory=lambda: {"NAS": [{"icod": "710", "name": "테스트반도체"}]}
    )
    calls: list = field(default_factory=list)
    seen_headers: list = field(default_factory=list)

    def count(self, path_part: str) -> int:
        return sum(1 for c in self.calls if path_part in c)

    def ok(self, body: dict, tr_cont: str = "D") -> httpx.Response:
        return httpx.Response(
            200,
            json={"rt_cd": "0", "msg_cd": "MCA00000", "msg1": "정상처리 되었습니다.", **body},
            headers={"tr_cont": tr_cont},
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append(path)
        self.seen_headers.append(dict(request.headers))
        if self.override is not None:
            res = self.override(request)
            if res is not None:
                return res
        if path == "/oauth2/tokenP":
            if self.token_status != 200:
                return httpx.Response(
                    self.token_status,
                    json={"error_description": "fail", "error_code": "EGW00103"},
                )
            body = json.loads(request.content)
            assert body["appkey"] == APP_KEY and body["appsecret"] == APP_SECRET
            return httpx.Response(
                200,
                json={
                    "access_token": TOKEN,
                    "access_token_token_expired": "2099-01-01 00:00:00",
                    "token_type": "Bearer",
                    "expires_in": 86400,
                },
            )
        if request.headers.get("authorization") != f"Bearer {TOKEN}":
            return httpx.Response(
                500,
                json={"rt_cd": "1", "msg_cd": "EGW00123", "msg1": "기간이 만료된 token 입니다."},
            )
        assert request.headers["custtype"] == "P"
        if path.endswith("/trading/inquire-balance"):
            assert request.headers["tr_id"] == "TTTC8434R"
            assert request.url.params["CANO"] == "12345678"
            assert request.url.params["ACNT_PRDT_CD"] == "01"
            return self.ok(
                {
                    "output1": self.domestic_rows,
                    "output2": [{"dnca_tot_amt": "500000"}],
                    "ctx_area_fk100": "",
                    "ctx_area_nk100": "",
                }
            )
        if path.endswith("/trading/inquire-present-balance"):
            assert request.headers["tr_id"] == "CTRP6504R"
            return self.ok(
                {
                    "output1": self.overseas_rows,
                    "output2": [
                        {
                            "crcy_cd": "USD",
                            "frst_bltn_exrt": self.fx_rate,
                            "frcr_dncl_amt_2": "12.34000",
                        }
                    ],
                    "output3": {},
                }
            )
        if path.endswith("/quotations/industry-price"):
            exchange = request.url.params["EXCD"]
            rows = self.industries.get(exchange, [])
            return self.ok({"output1": {"nrec": str(len(rows))}, "output2": rows})
        if path.endswith("/quotations/search-stock-info"):
            code = request.url.params["PDNO"]
            return self.ok({"output": {"scty_grp_id_cd": self.domestic_kind.get(code, "")}})
        return httpx.Response(404, json={"rt_cd": "1", "msg_cd": "NOTFOUND"})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


class FakeMaster:
    """공식 마스터 파일 대신 쓰는 판별기."""

    def __init__(
        self,
        kinds: dict[str, str | None] | None = None,
        sectors: dict[str, tuple[str, str]] | None = None,
    ):
        self.kinds = kinds or {"AAAA": "stock", "BBBB": "etf"}
        self.sectors = {"AAAA": ("NAS", "710")} if sectors is None else sectors

    async def kind(self, exchange: str, symbol: str) -> str | None:
        return self.kinds.get(symbol)

    async def sector_code(self, exchange: str, symbol: str) -> tuple[str, str] | None:
        return self.sectors.get(symbol)
