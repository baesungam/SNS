$PYTHON = "C:\Users\sds46\AppData\Local\Programs\Python\Python312\python.exe"
Set-Location $PSScriptRoot

Write-Host "Starting app... go to http://localhost:8501" -ForegroundColor Green
& $PYTHON -m streamlit run app.py
