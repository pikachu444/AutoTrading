import time
import pandas as pd
import pandas_ta as ta
import FinanceDataReader as fdr
import logging
import os
import threading
from datetime import datetime, timedelta

class Screener:
    """
    [마크 미너비니 & 윌리엄 오닐 스캐너]
    FinanceDataReader(fdr)를 활용해 거래소 전 종목의 52주 데이터를 고속 수집하고,
    미너비니의 주도주 텐플릿과 상대강도(RS) 점수를 기반으로 타겟 10종목을 걸러냅니다.
    """
    # 전역(클래스 단위) 캐시 메모리 탑재 -> 여러 스레드나 클래스가 각자 생성되더라도 단일 캐시를 공유합니다.
    _cached_results = None
    _last_scan_date = None
    _scan_lock = threading.Lock()
    
    def __init__(self):
        pass
        
    def get_market_tickers(self) -> list:
        """코스피, 코스닥 상장 종목 데이터 리스트 수집"""
        try:
            logging.info("[Screener] 한국 거래소(KRX) 상장 종목 기초 수집 중...")
            krx = fdr.StockListing('KRX')
            krx = krx[krx['Market'].isin(['KOSPI', 'KOSDAQ'])]
            
            # 스크리닝이 너무 오래 걸리지 않도록 시가총액/거래대금 필터 적용 추천
            # 현재 테스트에서는 시가총액 상위 300 종목만 타겟팅합니다.
            krx = krx.sort_values(by='Marcap', ascending=False).head(300)
            tickers_df = krx[['Code', 'Name']]
            
            logging.info(f"[Screener] 1차 필터링된 유동성 충분 종목 수: {len(tickers_df)}개")
            return tickers_df
        except Exception as e:
            logging.error(f"[Screener] 종목 리스트 수집 에러: {e}")
            # 대비책 (에러 시 빈 데이터프레임 반환)
            return pd.DataFrame(columns=['Code', 'Name'])
            
    def calculate_rs_raw(self, df: pd.DataFrame) -> float:
        """
        [윌리엄 오닐 스타일 상대강도(RS) 계산]
        최근 1년(252영업일) 수익률을 분기별로 나누어 
        가장 최근 3개월 성과에 압도적 가중치(40%)를 부여한 스코어를 냅니다.
        """
        if len(df) < 252:
            return 0.0
            
        close = df['Close'].values
        
        # 각 기간 전의 주가 대비 현재 주가 상승률 (분기 = 63영업일)
        ret_q1 = (close[-1] / close[-63]) - 1   # 최근 3개월 
        ret_q2 = (close[-1] / close[-126]) - 1  # 최근 6개월
        ret_q3 = (close[-1] / close[-189]) - 1  # 최근 9개월
        ret_q4 = (close[-1] / close[-252]) - 1  # 최근 12개월
        
        # 최근 분기에 가장 높은 가중치(2배 혹은 0.4) 부여
        rs_raw = (ret_q1 * 0.4) + (ret_q2 * 0.2) + (ret_q3 * 0.2) + (ret_q4 * 0.2)
        return rs_raw
        
    def is_minervini_trend(self, df: pd.DataFrame) -> bool:
        """[마크 미너비니 트렌드 템플릿 검사 (주도주 8원칙 적용)]"""
        # 1.5년(약 300영업일) 데이터가 없는 신규 상장주 등은 안전을 위해 제외
        if len(df) < 260:
            return False
            
        df_copy = df.copy()
        
        # 이동평균선(SMA) 50, 150, 200일선 계산
        df_copy.ta.sma(length=50, append=True)
        df_copy.ta.sma(length=150, append=True)
        df_copy.ta.sma(length=200, append=True)
        
        current = df_copy.iloc[-1]
        past_1month = df_copy.iloc[-21]  # 20영업일 전 (약 1개월)
        
        c = current['Close']
        sma50 = current['SMA_50']
        sma150 = current['SMA_150']
        sma200 = current['SMA_200']
        sma200_past = past_1month['SMA_200']
        
        # 52주 고점 저점 (1년)
        high_52w = df_copy['High'].tail(252).max()
        low_52w = df_copy['Low'].tail(252).min()
        
        try:
            # 원칙 1. 현재가가 150일, 200일 이평선 위에 있다 (초장기 상승추세)
            cond1 = (c > sma150) and (c > sma200)
            # 원칙 2. 150일선이 200일선 위에 있다 (정배열 형태)
            cond2 = sma150 > sma200
            # 원칙 3. 200일선 자체가 상승 중이어야 한다 (1개월 전 200일 선 보다 높아야 함)
            cond3 = sma200 > sma200_past
            # 원칙 4. 50일선이 150/200일선 위에 있다 (완벽한 정배열)
            cond4 = (sma50 > sma150) and (sma50 > sma200)
            # 원칙 5. 현재 주가가 50일선 위에 있다 (단기도 우상향)
            cond5 = c > sma50
            # 원칙 6. 주가가 52주 신저가에서 적어도 30% 이상 반등한 상태다 (바닥을 쳤음)
            cond6 = c > (low_52w * 1.3)
            # 원칙 7. 주가가 52주 신고가의 최소 25% 이내에 위치한다 (고점 근처에서 비싸게 노는 놈을 사라)
            cond7 = c >= (high_52w * 0.75)
            
            return cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7
        except Exception:
            return False
            
    def run_daily_scan(self, top_n: int = 10) -> list:
        """
        오늘 날짜(투데이) 확인 후 글로벌 클래스(Cache)에 결과물이 있다면 1초 내로 반환합니다.
        스레드 락(Lock)을 활용한 '이중 검증 패턴(Double-Checked Locking)'으로 병목 스레드를 안전하게 우회합니다.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 1. 락 체결 없이 1초 컷으로 패스 (대부분 여기 통과)
        if self.__class__._last_scan_date == today and self.__class__._cached_results is not None:
            logging.info("[Screener] 오늘 이미 발굴 스캔이 스케줄러로 완료되었습니다. 캐시를 확보해 즉시 반환합니다.")
            return self.__class__._cached_results
            
        # 2. 캐시가 비어있다면 락 체결! (누가 무거운 데이터 수집 문을 열고 들어감)
        self.__class__._scan_lock.acquire()
        
        # 3. 문을 따고 들어간 직후 다시 확인 (내가 대기열에 선 동안 나보다 앞에 섰던 애가 캐시를 채워넣었을 수 있음)
        if self.__class__._last_scan_date == today and self.__class__._cached_results is not None:
            logging.info("[Screener] 대기열 통과 직후 캐시 확인! 연산을 건너뜁니다.")
            self.__class__._scan_lock.release()
            return self.__class__._cached_results
            
        tickers_df = self.get_market_tickers()
        
        passed_stocks = []
        stock_names = []
        rs_scores = []
        
        start_date = (datetime.now() - timedelta(days=600)).strftime("%Y-%m-%d")
        
        logging.info("[Screener] 종목별 딥 스캔 시작 (이 작업은 보통 심야에 5~10분 소요됩니다)")
        
        for idx, row in tickers_df.iterrows():
            symbol = row['Code']
            name = row['Name']
            try:
                # KIS API 일봉은 개수 제한(100)이 있어 대량 백테스트는 fdr이 압도적으로 유리합니다.
                df = fdr.DataReader(symbol, start=start_date)
                
                if df.empty or len(df) < 260:
                    continue
                    
                if self.is_minervini_trend(df):
                    rs = self.calculate_rs_raw(df)
                    passed_stocks.append(symbol)
                    stock_names.append(name)
                    rs_scores.append(rs)
                    
            except Exception as e:
                pass
                
        # 판다스 데이터프레임으로 만들어 RS 랭킹화
        res_df = pd.DataFrame({
            'Symbol': passed_stocks, 
            'Name': stock_names,
            'RS_Raw': rs_scores
        })
        
        if res_df.empty:
            logging.info("[Screener] 오늘 미너비니 주도주 필터를 통과한 대장주가 0개입니다 (하락장)")
            self.__class__._scan_lock.release()
            return []
            
        # RS 점수를 1~99로 백분위(Percentile) 정규화
        res_df['RS_Rating'] = res_df['RS_Raw'].rank(pct=True) * 99
        res_df = res_df.sort_values(by='RS_Rating', ascending=False)
        
        # 상위 N개의 종목코드, 종목명, RS점수 사전(Dict) 리스트 배출
        top_targets_df = res_df.head(top_n)[['Symbol', 'Name', 'RS_Rating']]
        
        logging.info(f"[Screener] ✨오늘의 TOP {len(top_targets_df)} 주도주 발굴 완료 및 전역 메모리 캐싱 완료!")
        
        final_list = top_targets_df.to_dict('records')
        self.__class__._cached_results = final_list
        self.__class__._last_scan_date = today
        
        # 파일로 물리적 저장 (기록 아카이빙용)
        try:
            os.makedirs("watchlists", exist_ok=True)
            prefix = "us" if "US" in self.__class__.__name__ else "kr"
            path = f"watchlists/watchlist_{prefix}_{today}.csv"
            save_df = top_targets_df.copy()
            save_df['RS_Rating'] = save_df['RS_Rating'].round(2)
            save_df.to_csv(path, index=False, encoding='utf-8-sig')
            logging.info(f"[Screener] 스캔 결과가 '{path}' 에 체계적으로 보관되었습니다.")
        except Exception as e:
            logging.error(f"[Screener] 파일 저장 실패: {e}")
        
        self.__class__._scan_lock.release()
        return final_list

if __name__ == "__main__":
    # 스캐너 단독 실행 테스트
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    screener = Screener()
    # 테스트를 위해 300종목 중 최상위 5개를 빠르게 색출해봅니다.
    top_5_picks = screener.run_daily_scan(top_n=5)
