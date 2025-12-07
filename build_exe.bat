@echo off
echo Building Dofus Tracker Client V3...

REM Clean previous builds
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist DofusTracker.spec del DofusTracker.spec

REM Run PyInstaller
REM --onedir: Create a directory with the executable (faster startup)
REM --windowed: No console window
REM --add-data: Include dofus_data folder
REM --collect-all: Include all customtkinter files
python -m PyInstaller --noconfirm --onedir --windowed --name "DofusTracker" --add-data "dofus_data;dofus_data" --collect-all customtkinter main.py

echo Copying Npcap installer...
if exist redist\npcap-installer.exe copy redist\npcap-installer.exe dist\DofusTracker\

echo Build complete. Executable is in dist/DofusTracker/DofusTracker.exe
pause