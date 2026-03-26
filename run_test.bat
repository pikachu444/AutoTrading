@echo off
echo.
echo ===================================================
echo [텔레그램 봇 단독 테스트 실행]
echo 가상 환경(.venv)에 설치된 파이썬으로 안전하게 실행합니다...
echo ===================================================
echo.
set PYTHONPATH=.
.\.venv\Scripts\python -m tests.test_telegram_only
pause
