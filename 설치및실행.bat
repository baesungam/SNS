@echo off
chcp 65001 > nul
echo ========================================
echo  내돈내산 블로그 자동 포스팅 - 설치
echo ========================================

echo.
echo [1/3] 패키지 설치 중...
pip install -r requirements.txt

echo.
echo [2/3] Playwright 브라우저 설치 중...
playwright install chromium

echo.
echo [3/3] .env 파일 확인...
if not exist .env (
    copy .env.example .env
    echo .env 파일이 생성되었습니다. 메모장으로 열어서 API 키를 입력해주세요.
    notepad .env
) else (
    echo .env 파일이 이미 존재합니다.
)

echo.
echo ========================================
echo  설치 완료! 앱을 실행합니다...
echo ========================================
streamlit run app.py
pause
