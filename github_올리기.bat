@echo off
chcp 65001 > nul
echo.
echo ══════════════════════════════════════════════════
echo   GitHub에 올리고 APK 자동 빌드 시작
echo ══════════════════════════════════════════════════
echo.

:: Git 설치 확인
git --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [오류] Git이 설치되어 있지 않습니다.
    echo.
    echo Git 다운로드: https://git-scm.com/download/win
    echo 설치 후 이 스크립트를 다시 실행하세요.
    pause
    exit /b 1
)

echo [1단계] GitHub 저장소 주소를 입력하세요
echo   예시: https://github.com/아이디/저장소이름.git
echo.
set /p REPO_URL="GitHub URL: "

if "%REPO_URL%"=="" (
    echo [오류] URL을 입력하지 않았습니다.
    pause
    exit /b 1
)

echo.
echo [2단계] Git 초기화 중...
git init
git add .
git commit -m "초기 커밋: SNS 전문가 앱"

echo.
echo [3단계] GitHub에 업로드 중...
git branch -M main
git remote add origin "%REPO_URL%" 2>nul || git remote set-url origin "%REPO_URL%"
git push -u origin main

if %errorlevel% equ 0 (
    echo.
    echo ══════════════════════════════════════════════════
    echo   ✅ 업로드 완료!
    echo ══════════════════════════════════════════════════
    echo.
    echo 이제 GitHub Actions가 APK를 자동으로 빌드합니다.
    echo 약 5~10분 후:
    echo   1. GitHub 저장소 페이지 접속
    echo   2. 상단 "Actions" 탭 클릭
    echo   3. "APK 빌드" 워크플로우 클릭
    echo   4. 완료된 실행 클릭
    echo   5. 하단 "Artifacts" 섹션에서 APK 다운로드
    echo.
) else (
    echo.
    echo [오류] 업로드 실패
    echo.
    echo 확인사항:
    echo   - GitHub 저장소가 미리 생성되어 있는지 확인
    echo   - GitHub 로그인 정보가 올바른지 확인
    echo   - URL 형식이 맞는지 확인
    echo.
)

pause
