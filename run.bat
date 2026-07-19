@echo off
cd /d "%~dp0"
pip install -r requirements.txt -q
python twitch_ntfy.py
pause
