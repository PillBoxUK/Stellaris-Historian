@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
title Stellaris Historian v0.0.50.4

cls
if exist "assets\stellaris_banner.txt" (
    type "assets\stellaris_banner.txt"
) else (
    echo.
    echo                     STELLARIS
    echo                    H I S T O R I A N
    echo                      by PillBoxUK
    echo.
)
echo ==========================================
echo        STELLARIS HISTORIAN v0.0.50.4
echo ==========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python environment...
    py -3 -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create Python environment.
        echo Make sure Python 3 is installed.
        echo.
        pause
        exit /b 1
    )
)

if not exist "data\.migration_v0_0_33_complete" (
    echo Running one-time v0.0.33 combat evidence foundation migration...
    ".venv\Scripts\python.exe" migrate_v0_0_33.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.33 migration failed.
        echo No campaign data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.33.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_34_complete" (
    echo Running one-time v0.0.34 combat activity evidence migration...
    ".venv\Scripts\python.exe" migrate_v0_0_34.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.34 migration failed.
        echo No campaign data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.34.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_35_complete" (
    echo Running one-time v0.0.35 Scribes View validation...
    ".venv\Scripts\python.exe" migrate_v0_0_35.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.35 validation failed.
        echo No campaign data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.35.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_36_complete" (
    echo Running one-time v0.0.36 timeline and chronicle export validation...
    ".venv\Scripts\python.exe" migrate_v0_0_36.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.36 validation failed.
        echo No campaign data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.36.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_37_complete" (
    echo Running one-time v0.0.37 chronicle and technology evidence validation...
    ".venv\Scripts\python.exe" migrate_v0_0_37.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.37 validation failed.
        echo No campaign data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.37.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_38_complete" (
    echo Running one-time v0.0.38 combat reconstruction and historical event validation...
    ".venv\Scripts\python.exe" migrate_v0_0_38.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.38 validation failed.
        echo No campaign data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.38.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_39_complete" (
    echo Running one-time v0.0.39 diagnostics housekeeping and launcher validation...
    ".venv\Scripts\python.exe" migrate_v0_0_39.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.39 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.39.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_40_complete" (
    echo Running one-time v0.0.40 combat episode and event-layer validation...
    ".venv\Scripts\python.exe" migrate_v0_0_40.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.40 validation failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.40.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_40_1_complete" (
    echo Running one-time v0.0.40.1 combat telemetry and folder-shortcut validation...
    ".venv\Scripts\python.exe" migrate_v0_0_40_1.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.40.1 validation failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.40.1.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_41_complete" (
    echo Running one-time v0.0.41 timeline and Scribes episode-renderer validation...
    ".venv\Scripts\python.exe" migrate_v0_0_41.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.41 validation failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.41.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_42_complete" (
    echo Running one-time v0.0.42 character deep-evidence migration...
    ".venv\Scripts\python.exe" migrate_v0_0_42.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.42 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.42.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_43_complete" (
    echo Running one-time v0.0.43 event and character deep-probe validation...
    ".venv\Scripts\python.exe" migrate_v0_0_43.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.43 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.43.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_44_complete" (
    echo Running one-time v0.0.44 notification and event object decoder validation...
    ".venv\Scripts\python.exe" migrate_v0_0_44.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.44 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.44.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_45_complete" (
    echo Running one-time v0.0.45 notification-derived leader death migration...
    ".venv\Scripts\python.exe" migrate_v0_0_45.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.45 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.45.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_46_complete" (
    echo Running one-time v0.0.46 politics and diplomacy deep-probe migration...
    ".venv\Scripts\python.exe" migrate_v0_0_46.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.46 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.46.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_47_complete" (
    echo Running one-time v0.0.47 Live History and structured politics/diplomacy migration...
    ".venv\Scripts\python.exe" migrate_v0_0_47.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.47 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.47.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_47_1_complete" (
    echo Running one-time v0.0.47.1 durable incremental-history hotfix...
    ".venv\Scripts\python.exe" migrate_v0_0_47_1.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.47.1 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.47.1.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_48_complete" (
    echo Running one-time v0.0.48 politics publication and refresh-progress migration...
    ".venv\Scripts\python.exe" migrate_v0_0_48.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.48 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.48.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_48_1_complete" (
    echo Running one-time v0.0.48.1 Live History route hotfix...
    ".venv\Scripts\python.exe" migrate_v0_0_48_1.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.48.1 hotfix failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.48.1.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_49_complete" (
    echo Running one-time v0.0.49 campaign navigation and First Contact foundation migration...
    ".venv\Scripts\python.exe" migrate_v0_0_49.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.49 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.49.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_50_complete" (
    echo Running one-time v0.0.50 structured First Contact decoder migration...
    ".venv\Scripts\python.exe" migrate_v0_0_50.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.50 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.50.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_50_1_complete" (
    echo Running one-time v0.0.50.1 First Contact resolution hotfix...
    ".venv\Scripts\python.exe" migrate_v0_0_50_1.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.50.1 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.50.1.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_50_2_complete" (
    echo Running one-time v0.0.50.2 First Contact name-resolution hotfix...
    ".venv\Scripts\python.exe" migrate_v0_0_50_2.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.50.2 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.50.2.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_50_3_complete" (
    echo Running one-time v0.0.50.3 First Contact name-grammar hotfix...
    ".venv\Scripts\python.exe" migrate_v0_0_50_3.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.50.3 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.50.3.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

if not exist "data\.migration_v0_0_50_4_complete" (
    echo Running one-time v0.0.50.4 First Contact adjective-inflection hotfix...
    ".venv\Scripts\python.exe" migrate_v0_0_50_4.py
    if errorlevel 1 (
        echo.
        echo ERROR: v0.0.50.4 migration failed.
        echo No campaign save data was intentionally deleted.
        echo Check logs\MIGRATION_v0.0.50.4.log for details.
        echo.
        pause
        exit /b 1
    )
    echo.
)

echo Checking dependencies...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting Stellaris Historian...
echo Dashboard: http://127.0.0.1:8766
echo.

".venv\Scripts\python.exe" app.py
set APP_EXIT_CODE=%errorlevel%

if "%APP_EXIT_CODE%"=="0" (
    endlocal
    exit /b 0
)

echo.
echo ==========================================
echo STELLARIS HISTORIAN STOPPED WITH AN ERROR
echo ==========================================
echo Exit code: %APP_EXIT_CODE%
echo.
echo The window is being left open so the error can be read.
echo.
pause

endlocal
exit /b %APP_EXIT_CODE%
