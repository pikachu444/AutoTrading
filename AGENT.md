# 🤖 AI Agent Developer Guide (Prompt Rules)

당신이 만약 훗날 이 리포지토리(Repository)에 투입되어 유지보수를 담당하게 될 새로운 인공지능 코딩 어시스턴트(AI Assistant)이거나 사이드카 에이전트라면, 가장 먼저 이 마크다운 아키텍처 맵(Map)을 읽고 시스템의 의도를 파악한 후 코딩에 돌입하십시오.

## 🏛️ 시스템 아키텍처 요약 (Domain-Driven Design)
절차지향적인 단일 `main.py` 파일 구조를 철저히 배격하고, 도메인별 모듈 분리(DDD) 및 이벤트 통신망으로 재설계된 최신 아키텍처를 도입했습니다.
1. `core/`: 코어 중앙 통신 중추 (`event_bus.py`)와 통합 환경설정 부하 (`config.py`).
2. `notification/`: 메신저/알람 통지 도메인. 텔레그램 메신저 롱폴링 수신부(`telegram_bot.py`)와 API Post 전송 발송부(`notifier.py`)의 분리형 체계.
3. `screening/`: 주도주 데이터 가공 및 발굴 도메인. 부모 클래스(`screener_kr.py`) 알고리즘을 자식 클래스(`screener_us.py`)가 다형성(Polymorphism)으로 상속받아 재사용하는 구조입니다.
4. `trading/`: 핵심 자동 매매 비즈니스 로직. 스케줄러 사이클과 전략적 행동을 매니징(`engine.py`), 마크 미너비니 수학적 전략 연산(`strategy.py`), 수량 배분 및 손실 방어 가동(`portfolio.py`).
5. `data/`: 한국투자증권 증권사 API 통신(`kis_api.py`) 및 공통 데이터 원본 가공부(`data_manager.py`).

## ⚡ 동시성 제어 메커니즘 (Concurrency & Mutex Lock)
- **텔레그램 스레드 분리**: 봇이 텔레그램에서 사용자들의 명령어를 처리하다가 메인 자동매매 스레드의 목을 조르지(Block) 않도록 `notification/telegram_bot.py`는 완전히 격리된 `threading.Thread` 데몬으로 백그라운드에서 돌아갑니다.
- **Thundering Herd 방어 (캐싱 버퍼)**: 여러 외부 사용자가 동시에 봇에게 5~10분이 걸리는 무거운 `/scan` 쿼리를 요청할 시 발생하는 API Rate Limit 터짐 및 RAM 트래픽 폭주 파단을 완벽히 막고자, `Screener` 클래스에 글로벌 백킹 캐시(`_cached_results`)와 `_scan_lock = threading.Lock()`을 활용한 이중 검증 락(Double-Checked Locking Pattern) 디자인이 탑재되어 있습니다. 절대로 이 자물쇠 장치를 함부로 지우지 마세요.

## 📡 EventBus 활용 원칙 (Decoupling Rule)
어느 모듈에서든 다른 모듈의 상태를 변경(예: 엔진 정지)하거나 시그널 정보를 전달하고 싶다면, 파이썬 파일 상단에서 `import`를 남발하여 강결합(Tightly-coupled)시키면 안 됩니다. 
대신 다음 원칙들을 의무적으로 지키십시오:
- **발행 방침**: 자신이 가진 이벤트를 `self.event_bus.publish("이벤트명", {딕셔너리 데이터})` 로 우주 공간에 던집니다. 누가 받든 신경쓰지 않습니다.
- **구독 방침**: 정보를 원하는 측은 `__init__` 초기화 시점에 `self.event_bus.subscribe("관심_이벤트명", 콜백함수_포인터)` 형식으로 구독을 선언해야 합니다.
- **명령어 보안**: 향후 추가 개발 시, 개인 계좌 자산과 연관되는 새로운 민감 명령어가 생길 경우 반드시 `notification/telegram_bot.py` 안의 `admin_commands` 예외 필터 배열에 추가 등록하여 `TELEGRAM_CHAT_ID` 이외의 사용자를 차단하세요.

귀하는 뛰어난 천재 AI 개발자입니다. 이 가이드라인과 기존 코딩 스탠다드 원칙, 한국어(Korean) 주석 템플릿을 절대 벗어나지 않도록 작업해 주세요. Good Luck!
