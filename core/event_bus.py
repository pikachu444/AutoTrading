class EventBus:
    """
    [이벤트 버스]
    메인 트레이딩 엔진(BotEngine)에서 매매, 스캔 등의 동작이 발생했을 때
    알림 서비스(Telegram, Discord, DB 로깅 등)에 결합되지 않고
    오직 "이벤트" 자체만 허공(Bus)에 뿌려주는 역할을 합니다.
    """
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_type: str, callback):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, data=None):
        if data is None:
            data = {}
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    # 이벤트 수신자 측의 에러가 다른 수신자나 코어 엔진을 멈추게 하지 않도록 보호합니다.
                    pass
