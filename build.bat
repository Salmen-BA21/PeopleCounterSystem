@echo off
setlocal

echo ============================================
echo   PeopleCounter Build Script
echo ============================================
echo.

set PYTHON=.venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Python not found at %PYTHON%
    echo Make sure the .venv folder exists in the project root.
    pause
    exit /b 1
)

echo [1/3] Installing pywebview and pyinstaller...
"%PYTHON%" -m pip install pywebview pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo [2/3] Building with PyInstaller...
"%PYTHON%" -m PyInstaller PeopleCounter.spec --noconfirm --clean
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo [3/3] Creating runtime folders...
if not exist "dist\PeopleCounter\uploads" mkdir "dist\PeopleCounter\uploads"
if not exist "dist\PeopleCounter\reports" mkdir "dist\PeopleCounter\reports"

echo.
echo ============================================
echo   Build complete!
echo ============================================
echo.
echo Output: dist\PeopleCounter\
echo.
echo To distribute:
echo   1. Zip or RAR the dist\PeopleCounter\ folder
echo   2. Send it to any Windows PC
echo   3. Extract and double-click PeopleCounter.exe
echo.
pause
