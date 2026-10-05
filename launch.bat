@echo off
rem Launch SoftTimer with no console window.
rem %~dp0 is this script's own folder, so it works from wherever the repo is cloned.
cd /d "%~dp0"
start "" pyw -3 timer.py
exit