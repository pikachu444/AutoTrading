from abc import ABC, abstractmethod
import pandas as pd

# ==============================================================================
# 1. Base Strategy (추상 클래스 기반)
# ==============================================================================
class BaseStrategy(ABC):
    """
    [OOP 아키텍처] 모든 트레이딩 전략(Strategy)이 공통적으로 준수해야 하는 인터페이스입니다.
    이 구조를 통해 추후 다른 알고리즘(예: 데이트레이딩 전용, 배당주 포트폴리오 등)을 
    손쉽게 확장(플러그인 형태로 추가)할 수 있습니다.
    """
    
    @abstractmethod
    def get_signal(self, df: pd.DataFrame) -> str:
        """
        데이터프레임을 받아 BUY(매수) / SELL(매도) / HOLD(관망) 신호를 반환해야 합니다.
        """
        pass


# ==============================================================================
# 2. Hybrid Momentum Strategy (결합형 타점 전략)
# ==============================================================================
class HybridMomentumStrategy(BaseStrategy):
    """
    [결합형 모멘텀 알고리즘]
    심야 시간대 'Screener' 모듈에 의해 마크 미너비니 콤보(150일/200일 정배열 및 RS 고득점)를
    통과한 최우량 '주도주(엘리트)'들만을 대상(Watchlist)으로,
    단기적인 진입 타점(비상하는 초입, 눌림목 돌파)과 이탈 타점(모멘텀 상실)을 포착하는 것에
    초점을 맞춘 단기 전략입니다.
    """
    
    def __init__(self):
        pass

    def get_signal(self, df: pd.DataFrame) -> str:
        if df is None or len(df) < 2:
            return "HOLD"
            
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # pandas-ta 버전별 컬럼명 차이(예: MACD_12_26_9, BBL_20_2.0_2.0 등) 동적 탐색
        try:
            macd_col = [c for c in df.columns if c.startswith('MACD_')][0]
            macd_sig_col = [c for c in df.columns if c.startswith('MACDs_')][0]
            bbl_col = [c for c in df.columns if c.startswith('BBL_')][0]
            bbu_col = [c for c in df.columns if c.startswith('BBU_')][0]
        except IndexError:
            # 보조 지표가 제대로 생성되어 있지 않은 경우 (예컨대 데이터 부족)
            return "HOLD"
            
        # 1. MACD (초단기 추세 돌파)
        macd = current[macd_col]
        macd_sig = current[macd_sig_col]
        prev_macd = prev[macd_col]
        prev_macd_sig = prev[macd_sig_col]
        
        macd_golden_cross = (prev_macd <= prev_macd_sig) and (macd > macd_sig)
        macd_dead_cross = (prev_macd >= prev_macd_sig) and (macd < macd_sig)
        
        # 2. Bollinger Bands (박스권 하단/상단 터치)
        close = current['Close']
        bb_lower = current[bbl_col]
        bb_upper = current[bbu_col]
        
        bb_near_lower = close <= (bb_lower * 1.01)
        bb_near_upper = close >= (bb_upper * 0.99)
        
        # 3. RSI (과매수/과매도)
        rsi = current.get('RSI_14', 50)
        # 이미 1차 필터링된 초우량주이므로, RSI가 심하게 빠지지 않는다는 점을 감안해 매수존을 35로 상향 타협
        rsi_buy_zone = rsi <= 35  
        rsi_sell_zone = rsi >= 70
        
        # 4. Volume (초단기 수급 모멘텀)
        vol = current['Volume']
        if 'Volume_MA20' in current:
            vol_ma20 = current['Volume_MA20']
            vol_surge = vol >= (vol_ma20 * 1.2) # 거래량이 20일 평균 대비 20% 이상 증가할 때
        else:
            vol_surge = True
            
        # ====================================================
        # 하이브리드 시그널 판단 (Rule-based)
        # ====================================================
        buy_signal = False
        sell_signal = False
        
        # [매수 로직]
        # 대상 종목 전체가 이미 미너비니 '트렌드 우상향' 중이므로, 장기 이평선 역배열 걱정이 없습니다.
        # 따라서 단기 눌림목(RSI 과매도, BB 바닥)이 발생하거나 모멘텀 돌파(MACD 골든크로스)가 발생하면,
        # 살짝만 수급(Volume)이 받쳐줘도 적극적으로 매수에 들어갑니다.
        if (macd_golden_cross or rsi_buy_zone or bb_near_lower) and vol_surge:
            buy_signal = True

        # [매도 로직]
        # 반대로, 단기 지표상 추세가 한 번 꺾이는 기미(MACD 데드크로스, RSI 과매수, BB 천장 돌파)가 보이면,
        # 즉각 이탈합니다. (기존 종목 발굴에서 중장기를 보더라도 매매 집행은 단기로 끊어먹어 회전율을 올립니다)
        # * 추가로 이 로직 외에도 PortfolioManager 에서 -8% 손실 시 기계적 손절매를 책임집니다.
        if macd_dead_cross or rsi_sell_zone or bb_near_upper:
            sell_signal = True
            
        if buy_signal and not sell_signal:
            return "BUY"
        elif sell_signal:
            return "SELL"
        else:
            return "HOLD"
