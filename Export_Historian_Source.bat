@echo off
setlocal
cd /d "%~dp0"
echo ==========================================
echo  STELLARIS HISTORIAN - SOURCE EXPORT
 echo ==========================================
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Export_Historian_Source.ps1"
if errorlevel 1 (
 echo.
 echo Export failed. Read the error above.
 pause
 exit /b 1
)
echo.
echo Export complete. Upload the ZIP shown above.
pause
