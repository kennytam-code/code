@echo off
REM Double-click on the Bloomberg terminal PC, with Outlook open.
REM Two drafts land in Outlook's Drafts folder, addressed and formatted.
title Daily calendar email
cd /d "%~dp0"

where python >nul 2>nul
if %errorlevel%==0 (
    python daily_email.py %*
    goto done
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 daily_email.py %*
    goto done
)

echo.
echo   No Python found on the PATH.
echo.
echo   Use the Python the desk notebooks run on - the one that has blpapi -
echo   open that prompt (Anaconda Prompt, or the one you launch Jupyter from),
echo   change to this folder, and run:
echo.
echo       python daily_email.py
echo.

:done
echo.
pause
