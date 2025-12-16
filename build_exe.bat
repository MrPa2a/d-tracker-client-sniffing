@echo off
echo Building Dofus Tracker Client V3...

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Run PyInstaller
REM --onedir: Create a directory with the executable (faster startup)
REM --windowed: No console window
REM --add-data: Include dofus_data folder
REM --collect-all: Include all customtkinter files
python -m PyInstaller --noconfirm DofusTracker.spec

echo Copying Npcap installer...
if exist redist\npcap-installer.exe copy redist\npcap-installer.exe dist\DofusTracker\

echo Copying config.example.json...
if exist config.example.json copy config.example.json dist\DofusTracker\

REM Ne PAS copier config.json pour eviter d'ecraser la config utilisateur lors des updates
REM if exist config.json copy config.json dist\DofusTracker\

echo Build complete. Executable is in dist/DofusTracker/DofusTracker.exe

echo === Creating ZIP archive ===
set "APP_NAME=DofusTracker"
set "DIST_DIR=dist\%APP_NAME%"

set "ZIP_NAME=%APP_NAME%.zip"

echo Compressing to dist\%ZIP_NAME%...
powershell -NoLogo -NoProfile -Command ^
 "Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath 'dist\%ZIP_NAME%' -Force"

if errorlevel 1 (
    echo [ERROR] Failed to create ZIP archive.
) else (
    echo ZIP archive created successfully: dist\%ZIP_NAME%
)
pause