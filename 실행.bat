@echo off
set PYTHON=C:\Users\sds46\AppData\Local\Programs\Python\Python312\python.exe
cd /d "%~dp0"

echo Starting app... Open browser at http://localhost:8501
echo.
"%PYTHON%" -m streamlit run app.py
pause
