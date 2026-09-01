@echo off
REM Double-click this to start the price alarm on the Bloomberg terminal PC.
title Price Alarm
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python price_alarm.py %*
    goto done
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 price_alarm.py %*
    goto done
)

echo.
echo   No Python found on the PATH.
echo.
echo   The desk notebooks run on a Python that has blpapi installed - open
echo   that prompt (Anaconda Prompt, or the one you launch Jupyter from),
echo   change to this folder, and run:
echo.
echo       python price_alarm.py
echo.

:done
echo.
pause
