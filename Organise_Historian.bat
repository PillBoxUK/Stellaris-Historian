@echo off
setlocal
cd /d "%~dp0"
echo =============================================
echo  STELLARIS HISTORIAN - SAFE FOLDER CLEANUP
echo =============================================
echo.
echo 1. Preview moves (recommended first)
echo 2. Apply moves (preserves all files)
echo 3. Exit
choice /c 123 /n /m "Select option [1/2/3]: "
if errorlevel 3 exit /b 0
if errorlevel 2 goto apply
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Organise_Historian.ps1" -Mode Preview
pause
exit /b
:apply
echo.
echo This moves only selected archive and documentation files.
echo No files are deleted or overwritten.
choice /c YN /n /m "Continue [Y/N]? "
if errorlevel 2 exit /b 0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Organise_Historian.ps1" -Mode Apply
pause
