import pandas as pd
import pandas_ta as ta
import FinanceDataReader as fdr
import logging
import os
from datetime import datetime, timedelta

class Screener:
    """
    [마크 미너비니 & 윌리엄 오닐 스캐너]
    FinanceDataReader(fdr)를 활용해 거래소 전 종목의 52주 데이터를 고속 수집하고,
    미너비니의 주도주 템플릿과 상대강도(RS) 점수를 기반으로 타겟 종목을 걸러냅니다.
    """
    def __init__(self):
        pass
        
    def get_market_tickers(self, mode: str = "LARGE") -> pd.DataFrame:
        """
        [마켓 종목 수집 및 1차 필터링]
        mode="LARGE": 시총 상위 200위 (대형주)
        mode="GROWTH": 시총 500억~1조 사이 + 거래대금 상위 (중소형 성장주)
        """
        try:
            logging.info(f"[Screener] 한국 거래소(KRX) 상장 종목 수집 중 ({mode} 모드)...")
            krx = fdr.StockListing('KRX')
            
            if mode == "LARGE":
                # 시가총액 상위 200 종목 (안정적인 대장주 위주)
                tickers_df = krx.sort_values(by='Marcap', ascending=False).head(200)
            elif mode == "GROWTH":
                # 시총 500억 ~ 1조 사이 중 거래대금(Amount) 상위 300 종목 (탄력 있는 성장주)
                growth_pool = krx[(krx['Marcap'] >= 50_000_000_000) & (krx['Marcap'] <= 1_000_000_000_000)]
                tickers_df = growth_pool.sort_values(by='Amount', ascending=False).head(300)
            else:
                tickers_df = krx.head(300)

            tickers_df = tickers_df[['Code', 'Name']].copy()
            logging.info(f"[Screener] 1차 필터링 완료 ({mode}): {len(tickers_df)}개 종목")
            return tickers_df
        except Exception as e:
            logging.error(f"[Screener] 종목 리스트 수집 에러: {e}")
            return pd.DataFrame(columns=['Code', 'Name'])

    def calculate_rs_raw(self, df: pd.DataFrame) -> float:
        """[윌리엄 오닐 스타일 상대강도(RS) 계산]"""
        if len(df) < 252:
            return 0.0
        close = df['Close'].values
        ret_q1 = (close[-1] / close[-63]) - 1
        ret_q2 = (close[-1] / close[-126]) - 1
        ret_q3 = (close[-1] / close[-189]) - 1
        ret_q4 = (close[-1] / close[-252]) - 1
        return (ret_q1 * 0.4) + (ret_q2 * 0.2) + (ret_q3 * 0.2) + (ret_q4 * 0.2)
        
    def is_minervini_trend(self, df: pd.DataFrame) -> bool:
        """[마크 미너비니 트렌드 템플릿 검사 (8원칙)]"""
        # 데이터 정제
        df = df[~df.index.duplicated(keep='last')].dropna(subset=['Close'])
        if len(df) < 260: return False
        
        df_copy = df.copy()
        df_copy.ta.sma(length=50, append=True)
        df_copy.ta.sma(length=150, append=True)
        df_copy.ta.sma(length=200, append=True)
        
        current = df_copy.iloc[-1]
        past_1month = df_copy.iloc[-21]
        
        c = current['Close']
        sma50 = current['SMA_50']
        sma150 = current['SMA_150']
        sma200 = current['SMA_200']
        sma200_past = past_1month['SMA_200']
        
        high_52w = df_copy['High'].tail(252).max()
        low_52w = df_copy['Low'].tail(252).min()
        
        try:
            cond1 = (c > sma150) and (c > sma200)
            cond2 = sma150 > sma200
            cond3 = sma200 > sma200_past
            cond4 = (sma50 > sma150) and (sma50 > sma200)
            cond5 = c > sma50
            cond6 = c > (low_52w * 1.3)
            cond7 = c >= (high_52w * 0.75)
            return cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7
        except Exception as e:
            logging.debug(f"[Screener] 트렌드 필터 오류: {e}")
            return False

    def run_daily_scan(self, top_n: int = 10, mode: str = "LARGE") -> list:
        """[일간 스캔 실행 및 파일 저장]"""
        logging.info(f"========== [스캔 시작] 국내장 {mode} 모드 전수 조사 ==========")
        tickers_df = self.get_market_tickers(mode=mode)
        
        all_results = []
        start_date = (datetime.now() - timedelta(days=600)).strftime("%Y%m%d")
        
        for _, row in tickers_df.iterrows():
            symbol, name = row['Code'], row['Name']
            try:
                df = fdr.DataReader(symbol, start=start_date)
                if df.empty or len(df) < 250: continue
                if not self.is_minervini_trend(df): continue
                
                all_results.append({
                    'Symbol': symbol,
                    'Name': name,
                    'RS_Raw': self.calculate_rs_raw(df),
                    'Close': int(df['Close'].iloc[-1]),
                    'Change': float(df['Close'].pct_change().iloc[-1] * 100)
                })
            except Exception as e:
                logging.debug(f"[Screener] {name}({symbol}) 스캔 오류: {e}")
                continue

        if not all_results:
            self._save_results([], mode=mode)
            return []

        all_results.sort(key=lambda x: x['RS_Raw'], reverse=True)
        total_count = len(all_results)
        for i, res in enumerate(all_results):
            res['RS_Rating'] = round(((total_count - i) / total_count) * 99, 1)

        top_results = all_results[:top_n]
        self._save_results(top_results, mode=mode)
        return top_results

    def _save_results(self, results: list, mode: str):
        """결과를 CSV 파일로 저장 (마켓 및 모드 구분)"""
        os.makedirs("watchlists", exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 클래스명에 'US'가 포함되어 있으면 'us', 아니면 'kr'
        prefix = "us" if "US" in self.__class__.__name__ else "kr"
        
        # 한국장의 경우 모드(large, growth)를 파일명에 포함
        if prefix == "kr":
            path = f"watchlists/watchlist_kr_{mode.lower()}_{today}.csv"
        else:
            path = f"watchlists/watchlist_us_{today}.csv"
        
        df = pd.DataFrame(results)
        if df.empty:
            df = pd.DataFrame(columns=['Symbol', 'Name', 'RS_Rating', 'Close', 'Change'])
        df.to_csv(path, index=False, encoding='utf-8-sig')
        logging.info(f"[Screener] {prefix.upper()} {mode if prefix=='kr' else ''} 리스트 저장 완료: {path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    screener = Screener()
    screener.run_daily_scan(top_n=5, mode="LARGE")
    screener.run_daily_scan(top_n=5, mode="GROWTH")
