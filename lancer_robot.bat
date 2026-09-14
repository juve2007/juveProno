@echo off
cd /d "%~dp0"
echo Mise a jour des matchs et des pronostics...
python build_dashboard.py
echo.
pause
