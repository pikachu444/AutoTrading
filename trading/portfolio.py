import logging

class PortfolioManager:
    """
    [포트폴리오 비중 조절 및 멘탈/리스크 관리 매니저]
    단순한 매수/매도 시그널을 넘어, '얼마나 살 것인가(Position Sizing)'와
    '언제 손절할 것인가(Risk Management)'를 기계적으로 통제하는 객체입니다.
    """
    
    def __init__(self, max_positions: int = 5, stop_loss_pct: float = 0.08):
        # 최대 편입 가능 종목 수 
        # 예: 5종목 제한이면 계좌 1,000만 원일 때 1종목당 200만 원(20%)까지만 배정
        self.max_positions = max_positions
        
        # 기계적 칼손절 기준선 (윌리엄 오닐 원칙: 절대 -8% 이하로 손실을 키우지 마라)
        self.stop_loss_pct = stop_loss_pct

    def allocate_capital(self, available_cash: int, total_equity: int, current_price: int, held_count: int) -> int:
        """
        [적정 매수 수량(비중) 산출]
        총 자산 대비 허용 비중을 넘지 않는 선에서, 안전하게 살 수 있는 최대 주식 수를 반환합니다.
        
        :param available_cash: 당장 쓸 수 있는 현금 예수금
        :param total_equity: 총 자산 (예수금 + 주식 평가금액 합산)
        :param current_price: 매수하려는 종목의 현재가
        :param held_count: 현재 내 계좌에 들어있는 총 종목 개수
        """
        # 1. 이미 포트폴리오 한도(예: 5개)가 꽉 찼으면, 시그널이 떠도 더 사지 않습니다.
        if held_count >= self.max_positions:
            logging.warning(f"[Portfolio 관리] 이미 최대 자산 분산 한도({self.max_positions}종목)가 꽉 차서 신규 매수를 보류합니다.")
            return 0
            
        # 2. 종목당 할당할 1회 진입 목표 금액 = (전체 자산 / 최대 종목 수)
        target_allocation = total_equity // self.max_positions
        
        # 3. 내 예수금과 목표 금액 중 작은 값을 실제 매력도로 사용해 몰빵을 방지합니다.
        investable_amount = min(available_cash, target_allocation)
        
        # 4. 현재가(current_price)로 나눈 몫이 내가 온전히 살 수 있는 주식 수량입니다.
        qty = investable_amount // current_price
        
        if qty == 0:
            logging.info("[Portfolio 관리] 예수금이 부족하거나 1주를 사기 위한 최소 배분 자금이 부족합니다.")
            
        return int(qty)
        
    def check_stop_loss(self, average_buy_price: float, current_price: float) -> bool:
        """
        [리스크 관리: -8% 하드 손절매 감시]
        매수 단가 대비 하락폭이 설정값을 넘어섰는지 검사합니다.
        전략 시그널(HOLD)에 상관없이, True가 반환되면 봇이 우선적으로 시장가 매도를 강제 집행합니다.
        """
        if average_buy_price <= 0:
            return False
            
        # 투자 수익률 (ROI)
        roi = (current_price / average_buy_price) - 1.0
        
        # -8% (즉 -0.08) 이하로 떨어졌다면 비상탈출 발동
        if roi <= -self.stop_loss_pct:
            logging.warning(f"[Portfolio 🚨] 기계적 칼 손절 방어선({-self.stop_loss_pct*100}%) 폭파!! (현재 손실률: {roi*100:.2f}%)")
            return True
            
        return False
        
    def check_trailing_stop(self, high_since_buy: float, current_price: float, trailing_pct: float = 0.15) -> bool:
        """
        [리스크 관리: 익절 트레일링 스탑] (확장 예비용)
        매수 이후 신고가를 갱신하다가, 최상단 꼭대기부터 15% 기세가 무너지면 수익을 지키기 위해 익절합니다.
        (현재 뼈대만 작성하였고, 향후 추세 추종 강화 시 즉각 켜서 활용할 수 있습니다.)
        """
        if high_since_buy <= 0:
            return False
            
        # 최고점 대비 하락폭
        drawdown_from_high = (high_since_buy - current_price) / high_since_buy
        return drawdown_from_high >= trailing_pct
