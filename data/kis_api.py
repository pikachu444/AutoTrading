import requests
import json
from core.config import APP_KEY, APP_SECRET, URL_BASE, CANO, PRDT_CD

class KoreaInvestmentAPI:
    """한국투자증권 Open API 연동 클래스"""
    
    def __init__(self):
        """클래스 초기화: 설정값 로드 및 인증 토큰 발급"""
        self.url_base = URL_BASE
        self.app_key = APP_KEY
        self.app_secret = APP_SECRET
        self.cano = CANO
        self.prdt_cd = PRDT_CD
        
        # 1. 객체 생성과 동시에 Access Token을 발급받아 저장합니다.
        self.access_token = self._issue_token()

    def _issue_token(self):
        """
        [OAuth 인증 토큰 발급]
        사용자의 App Key와 App Secret을 이용해 API 사용을 위한 임시 토큰(일반적으로 1일 유지)을 발급받습니다.
        """
        path = "oauth2/tokenP"
        url = f"{self.url_base}/{path}"
        
        # 헤더 설정
        headers = {"content-type": "application/json"}
        
        # 요청 바디 (Data)
        data = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
        
        # POST 요청으로 토큰 발급 시도
        res = requests.post(url, headers=headers, data=json.dumps(data))
        res.raise_for_status() # HTTP 200 정상 응답이 아닐 경우 예외 발생
        
        result = res.json()
        token = result.get("access_token")
        
        print("[System] API 인증 토큰 발급 성공!")
        return f"Bearer {token}"
        
    def get_account_balance(self):
        """
        [계좌 잔고 및 주문 가능 금액 조회]
        현재 보유하고 있는 주식 리스트와 예수금(현금) 및 당일 매수 가능 금액을 확인합니다.
        """
        path = "uapi/domestic-stock/v1/trading/inquire-balance"
        url = f"{self.url_base}/{path}"
        
        # 실전 투자와 모의 투자의 TR_ID(거래 아이디)가 다릅니다.
        # 모의투자는 "VTTC8434R", 실전투자는 "TTTC8434R"를 사용해야 합니다.
        tr_id = "VTTC8434R" if "vts" in self.url_base else "TTTC8434R"
        
        headers = {
            "Content-Type": "application/json",
            "authorization": self.access_token,
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P", # Personal (개인)
        }
        
        params = {
            "CANO": self.cano,
            "PRDT_ABRV_NAME": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "01",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        # GET 요청으로 잔고 조회
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()
        
        result = res.json()
        
        # output1: 보유 주식 종목 리스트
        holdings = result.get("output1", [])
        
        # output2: 계좌 전반의 잔고 상태 (예수금, D+2 추정예수금, 매수 가능 금액 등)
        account_status = result.get("output2", [])
        
        if account_status:
            # dnca_tot_amt: 예수금 총액
            # prvs_rcdl_excc_amt: 매수 가능 현금
            total_cash = int(account_status[0].get("dnca_tot_amt", 0))
            available_buy = int(account_status[0].get("prvs_rcdl_excc_amt", 0))
            
            print(f"\n[계좌 상태]")
            print(f"- 예수금 총액: {total_cash:,} 원")
            print(f"- 매수 가능 금액: {available_buy:,} 원")
            print(f"- 보유 종목 수: {len(holdings)} 개")
            
            return {
                "holdings": holdings,
                "total_cash": total_cash,
                "available_buy": available_buy
            }
        else:
            print("[Error] 잔고 정보를 불러오지 못했습니다.")
            print(f"응답 메시지: {result.get('msg1')}")
            return None

    def place_order(self, symbol: str, is_buy: bool, qty: int, prc: str = "0", ord_type: str = "01"):
        """
        [주식 주문 전송]
        주어진 종목코드, 매수/매도 구분, 수량, 가격, 주문 단가 구분에 따라 주문을 전송합니다.
        ord_type "01": 시장가 (이 경우 가격은 "0"으로 설정), "00": 지정가
        """
        path = "uapi/domestic-stock/v1/trading/order-cash"
        url = f"{self.url_base}/{path}"
        
        # TR_ID 결정
        # 매수(buy): 실전은 "TTTC0802U", 모의투자는 "VTTC0802U"
        # 매도(sell): 실전은 "TTTC0801U", 모의투자는 "VTTC0801U"
        is_mock = "vts" in self.url_base
        
        if is_buy:
            tr_id = "VTTC0802U" if is_mock else "TTTC0802U"
        else:
            tr_id = "VTTC0801U" if is_mock else "TTTC0801U"
            
        headers = {
            "Content-Type": "application/json",
            "authorization": self.access_token,
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "tr_id": tr_id,
            "custtype": "P"
        }
        
        data = {
            "CANO": self.cano,
            "PRDT_CD": self.prdt_cd,
            "PDNO": symbol,
            "ORD_DVSN": ord_type,
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(prc)
        }
        
        res = requests.post(url, headers=headers, data=json.dumps(data))
        res.raise_for_status()
        result = res.json()
        
        # rt_cd가 "0"이면 정상 처리
        if result.get("rt_cd") == "0":
            print(f"[{'매수' if is_buy else '매도'} 주문 성공] {result.get('msg1')}")
            return True, result
        else:
            print(f"[{'매수' if is_buy else '매도'} 주문 실패] {result.get('msg1')}")
            return False, result

if __name__ == "__main__":
    # --- [실행/테스트 부분] ---
    # config.py 에 본인의 키를 입력한 후 이 스크립트를 직접 실행해보세요.
    print("=== 한국투자증권 API 연결 테스트 시작 ===")
    try:
        api = KoreaInvestmentAPI()
        balance_info = api.get_account_balance()
        print("=== 테스트 완료 ===")
    except Exception as e:
        print(f"[Error] API 연결 실패: {e}")
