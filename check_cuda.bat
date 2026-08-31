@echo off
setlocal

echo ============================================
echo   People Counter - GPU / CUDA check
echo ============================================
echo.
echo Copy this single file to any PC and double-click it.
echo No installation or project folder needed.
echo.

where nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo [X] No NVIDIA driver found on this PC.
    echo     Either there is no NVIDIA GPU, or the driver is not installed.
    echo     Result: the app will run on CPU only - very slow.
    echo.
    pause
    exit /b 1
)

echo [OK] NVIDIA GPU detected:
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
echo.

echo Rule: the app needs driver version 525 or newer for CUDA acceleration.
echo If the driver number above is lower than 525, the app silently falls
echo back to CPU - update the NVIDIA driver from nvidia.com/geforce/drivers
echo.

echo Final proof: after installing the app, open exe_diag.txt located next
echo to PeopleCounter.exe - the line must say ^(CUDA active^).
echo.
pause
