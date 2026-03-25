import pandas as pd
import numpy as np
from datetime import datetime, timedelta
# api 종속성 없이 데이터 매니저 클래스의 add_indicators 만 가져옵니다.
from data.data_manager import DataManager

# 1. Mock Data (가상 데이터) 생성기
def create_mock_ohlcv(days=150):
    start_date = datetime.now() - timedelta(days=days)
    dates = [start_date + timedelta(days=i) for i in range(days)]
    
    # 랜덤 워크(Random Walk) 기반 가격 생성
    np.random.seed(42)
    returns = np.random.normal(0, 0.02, days)
    close_prices = 50000 * np.cumprod(1 + returns)
    
    high_prices = close_prices * (1 + np.random.uniform(0, 0.03, days))
    low_prices = close_prices * (1 - np.random.uniform(0, 0.03, days))
    open_prices = close_prices * (1 + np.random.uniform(-0.015, 0.015, days))
    
    vol = np.random.randint(100000, 5000000, days)
    
    df = pd.DataFrame({
        'Date': dates,
        'Open': open_prices,
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
        'Volume': vol
    })
    return df

if __name__ == "__main__":
    print("=== [가상 데이터 기반 2단계 로직 자체 검증 시작] ===")
    mock_df = create_mock_ohlcv(150) # 150일치 가상 데이터
    print(f"- 생성된 가상 차트 데이터(OHLCV) 크기: {len(mock_df)}행")
    
    # 2. DataManager 인스턴스는 api 객체를 필요로 하므로 임시로 None 주입
    dm = DataManager(None)
    
    print("- pandas-ta 기반 5대 지표 계산(add_indicators) 실행 중...")
    try:
        analyzed_df = dm.add_indicators(mock_df)
        print("================================")
        print("[성공] 계산된 마지막 2일치 지표 데이터 확인:\n")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', 150)
        print(analyzed_df.tail(2))
        print("================================")
        
        # 3단계: 전략 시그널 테스트
        from trading.strategy import Strategy
        print("\n=== [3단계: 전략 알고리즘 시그널 자체 검증 시작] ===")
        strat = Strategy()
        signal = strat.get_signal(analyzed_df)
        print(f"-> 최종 도출된 트레이딩 시그널: {signal}")
        print("==================================================")
        
    except Exception as e:
        print(f"[실패] 오류 발생: {e}")
