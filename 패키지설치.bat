@echo off
set PYTHON=C:\Users\sds46\AppData\Local\Programs\Python\Python312\python.exe

echo Installing packages...
"%PYTHON%" -m pip install streamlit anthropic playwright beautifulsoup4 requests python-dotenv Pillow

echo Installing Playwright browser...
"%PYTHON%" -m playwright install chromium

echo Done! Run the app with run.bat
pause
