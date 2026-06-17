@echo off
cd /d "%~dp0"
echo ============================================
echo  Starting S^&P500 dashboard...
echo  Keep this window open. Close it to stop.
echo ============================================
echo.
python -m streamlit run app.py
echo.
echo App stopped. Press any key to close this window.
pause >nul
