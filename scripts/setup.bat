@echo off
REM QMD-Python Setup Script for Windows
REM Automatically creates virtual environment and installs dependencies

echo ========================================
echo QMD-Python Setup Script
echo ========================================
echo.

REM Check Python version
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH
    echo Please install Python 3.9+ from https://www.python.org
    pause
    exit /b 1
)

REM Detect CUDA availability
echo [1/4] Detecting CUDA...
python -c "import torch; exit(0 if torch.cuda.is_available() else 1)" >nul 2>&1
if errorlevel 1 (
    set VARIANT=cpu
    echo [INFO] No CUDA detected, will install CPU version
) else (
    set VARIANT=cuda
    echo [INFO] CUDA detected, will install GPU-accelerated version
)

REM Create virtual environment
echo.
echo [2/4] Creating virtual environment...
if exist .venv (
    echo [SKIP] .venv already exists
) else (
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)

REM Activate virtual environment
echo.
echo [3/4] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated

REM Upgrade pip
echo.
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo.
echo [4/4] Installing dependencies (%VARIANT% variant)...
echo This may take several minutes...
echo.

pip install -e .[%VARIANT%]
if errorlevel 1 (
    echo.
    echo [ERROR] Installation failed
    echo.
    echo Troubleshooting:
    echo 1. Make sure you have internet connection
    echo 2. Try: pip install -e .[%VARIANT%] --verbose
    echo 3. For CUDA version, ensure you have CUDA 12.1+ installed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo   1. Activate environment: .venv\Scripts\activate.bat
echo   2. Download models: python -m qmd.models.downloader
echo   3. Check system: qmd check
echo   4. Add collection: qmd collection add ./docs --name mydocs
echo   5. Index documents: qmd index
echo.
echo To activate environment in new terminal:
echo   .venv\Scripts\activate.bat
echo.
pause
