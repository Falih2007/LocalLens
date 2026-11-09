@echo off
cd /d "%~dp0"
py -3 -m pip install --upgrade --target vendor -r requirements-devices.txt
if errorlevel 1 pause
