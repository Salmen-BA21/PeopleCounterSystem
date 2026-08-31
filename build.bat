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

echo [1/3] Installing dependencies...
if exist "requirements.lock.txt" (
    echo   Using pinned requirements.lock.txt ^(reproducible build^)
    "%PYTHON%" -m pip install -r requirements.lock.txt --quiet
) else (
    echo   WARNING: requirements.lock.txt missing - versions may drift between PCs
    "%PYTHON%" -m pip install -r requirements.txt pywebview pyinstaller --quiet
)
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
echo To verify GPU / run self-check:
echo   dist\PeopleCounter\PeopleCounter.exe --diag
echo   Then check dist\PeopleCounter\exe_diag.txt
echo If it does not say ^(CUDA active^), update the NVIDIA driver (needs 525+).
echo.
echo To distribute:
echo   1. Zip or RAR the dist\PeopleCounter\ folder
echo   2. Send it to any Windows PC
echo   3. Extract and double-click PeopleCounter.exe
echo.
pause
