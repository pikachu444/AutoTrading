import logging
import pandas as pd
import FinanceDataReader as fdr
from screening.screener_kr import Screener

class ScreenerUS(Screener):
    """
    [미국 주도주 스캐너]
    S&P 500 종목을 대상으로 미너비니 콤보와 RS 스코어를 측정합니다.
    (핵심 알고리즘은 부모 클래스인 Screener 로직을 상속받아 재사용합니다.)
    """
    
    def get_market_tickers(self) -> pd.DataFrame:
        """S&P 500 종목 데이터 리스트 수집"""
        try:
            logging.info("[ScreenerUS] 미국 S&P500 상장 종목 기초 수집 중...")
            # 미국 S&P500 기업 리스트 전체 반환
            sp500 = fdr.StockListing('S&P500')
            
            # FDR의 S&P500 컬럼은 'Symbol', 'Name' 이므로 부모 클래스와 호환되게 'Code'로 변환
            tickers_df = sp500[['Symbol', 'Name']].copy()
            tickers_df.rename(columns={'Symbol': 'Code'}, inplace=True)
            
            logging.info(f"[ScreenerUS] 스캔 대상 미국 우량주 수: {len(tickers_df)}개")
            return tickers_df
        except Exception as e:
            logging.error(f"[ScreenerUS] 종목 리스트 수집 에러: {e}")
            return pd.DataFrame(columns=['Code', 'Name'])
