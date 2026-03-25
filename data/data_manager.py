import pandas as pd
import pandas_ta as ta
import requests
from datetime import datetime, timedelta

# KIS API 모듈과 설정 파일에서 필요한 정보들을 가져옵니다.
from data.kis_api import KoreaInvestmentAPI
try:
    from core.config import (MA_SHORT, MA_MID, MA_LONG, 
                        RSI_PERIOD, 
                        MACD_FAST, MACD_SLOW, MACD_SIGNAL, 
                        BB_PERIOD, BB_STD_DEV)
except ImportError:
    # config.py 에 지표 설정이 없을 경우를 대비한 기본값 세팅입니다.
    MA_SHORT, MA_MID, MA_LONG = 5, 20, 60
    RSI_PERIOD = 14
    MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9
    BB_PERIOD, BB_STD_DEV = 20, 2.0


class DataManager:
    """한국투자증권 API를 이용해 시세 데이터를 수집하고 기술적 지표를 계산하는 클래스입니다."""
    
    def __init__(self, api: KoreaInvestmentAPI):
        # 1단계에서 만든 KoreaInvestmentAPI 인스턴스를 주입받아 사용합니다.
        self.api = api
        
    def get_historical_data(self, symbol_code: str, period: str = "D") -> pd.DataFrame:
        """
        [종목 시세 데이터 수집]
        지정한 종목의 일봉(D)/주봉(W)/월봉(M) 데이터를 약 200일치 조회하여 DataFrame으로 반환합니다.
        """
        path = "uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        url = f"{self.api.url_base}/{path}"
        
        headers = {
            "Content-Type": "application/json",
            "authorization": self.api.access_token,
            "appKey": self.api.app_key,
            "appSecret": self.api.app_secret,
            "tr_id": "FHKST03010100", # 주식 일별 차트 가격 조회용 TR_ID
            "custtype": "P"
        }
        
        # 오늘 날짜와 200일 전 날짜를 구하여 조회 범위로 설정합니다.
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=200)).strftime("%Y%m%d")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",      # J: 주식, ETF 등
            "FID_INPUT_ISCD": symbol_code,      # 6자리 종목코드 (예: 005930)
            "FID_INPUT_DATE_1": start_date,     # 조회 시작일 (YYYYMMDD)
            "FID_INPUT_DATE_2": end_date,       # 조회 종료일 (YYYYMMDD)
            "FID_PERIOD_DIV_CODE": period,      # D: 일봉, W: 주봉, M: 월봉
            "FID_ORG_ADJ_PRC": "0"              # 0: 수정주가 적용
        }
        
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()
        
        result = res.json()
        
        # API 응답에서 차트 배열 데이터(output2)를 가져옵니다.
        chart_data = result.get('output2', [])
        
        if not chart_data:
            print(f"[Error] {symbol_code} 시세 데이터를 가져오지 못했습니다. 응답: {result.get('msg1')}")
            return pd.DataFrame()
            
        # 데이터를 pandas DataFrame으로 변환합니다.
        df = pd.DataFrame(chart_data)
        
        # 필요한 주요 컬럼만 추출하여 명명합니다.
        df = df[['stck_bsop_date', 'stck_oprc', 'stck_hgpr', 'stck_lwpr', 'stck_clpr', 'acml_vol']]
        df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        
        # 문자열로 들어온 수치형 데이터를 숫자로 변환합니다.
        numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # 날짜를 인덱스로 변환하고, 가장 오래된 날짜부터 최신 날짜 순으로 정렬합니다. 
        # API는 최근 날짜가 위로 오는 순으로 반환하기 때문입니다.
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values(by='Date').reset_index(drop=True)
        
        return df
        
    def add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        [지표 계산 및 추가]
        pandas-ta 라이브러리를 사용해 5가지 핵심 기술적 지표를 계산하고 데이터프레임에 추가합니다.
        """
        if df.empty:
            return df
            
        # 1. 이동평균선 (Moving Average)
        df.ta.sma(length=MA_SHORT, append=True)         # 단기 (SMA_5)
        df.ta.sma(length=MA_MID, append=True)           # 중기 (SMA_20)
        df.ta.sma(length=MA_LONG, append=True)          # 장기 (SMA_60)
        
        # 2. RSI (Relative Strength Index)
        df.ta.rsi(length=RSI_PERIOD, append=True)       # RSI_14
        
        # 3. MACD (Moving Average Convergence Divergence)
        df.ta.macd(fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL, append=True)
        
        # 4. 볼린저 밴드 (Bollinger Bands)
        df.ta.bbands(length=BB_PERIOD, std=BB_STD_DEV, append=True)
        
        # 5. 거래량 (Volume) 필터링 기준: 직전 20일 거래량 이동평균 계산 (단순 롤링 윈도우)
        df['Volume_MA20'] = df['Volume'].rolling(window=20).mean()
        
        return df


if __name__ == "__main__":
    # --- [실행/테스트 부분] ---
    print("=== 데이터 수집 및 기술적 지표 계산 테스트 시작 ===")
    try:
        api = KoreaInvestmentAPI()
        data_manager = DataManager(api)
        
        # 테스트 타겟: 삼성전자 (005930)
        target_symbol = "005930"
        print(f"\n1. [{target_symbol}] 종목 차트 데이터를 KIS API로부터 수집합니다...")
        
        df_raw = data_manager.get_historical_data(target_symbol)
        
        if not df_raw.empty:
            print(f"-> 수집 완료! 데이터 개수: {len(df_raw)}개 행")
            
            print("\n2. 수집된 데이터에 'pandas-ta'를 이용해 5가지 기술적 지표를 계산합니다...")
            df_analyzed = data_manager.add_indicators(df_raw)
            print("-> 계산 완료!")
            
            print("\n3. 최종 완성된 데이터 프레임 데이터 (최근 5일치):")
            # 터미널에서 데이터가 잘리지 않도록 컬럼 출력 옵션 조정
            pd.set_option('display.max_columns', None)  
            pd.set_option('display.width', 150)
            
            print(df_analyzed.tail(5))
            
    except Exception as e:
        print(f"[Error] 모듈 실행 중 오류가 발생했습니다: {e}")
