#!/bin/bash
# QMD-Python Setup Script for Linux/macOS
# Automatically creates virtual environment and installs dependencies

set -e  # Exit on error

echo "========================================"
echo "QMD-Python Setup Script"
echo "========================================"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found"
    echo "Please install Python 3.9+ from https://www.python.org"
    exit 1
fi

# Detect CUDA availability
echo "[1/4] Detecting CUDA..."
if python3 -c "import torch; exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
    VARIANT="cuda"
    echo "[INFO] CUDA detected, will install GPU-accelerated version"
else
    VARIANT="cpu"
    echo "[INFO] No CUDA detected, will install CPU version"
fi

# Create virtual environment
echo ""
echo "[2/4] Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "[SKIP] .venv already exists"
else
    python3 -m venv .venv
    echo "[OK] Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "[3/4] Activating virtual environment..."
source .venv/bin/activate
echo "[OK] Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
python -m pip install --upgrade pip --quiet

# Install dependencies
echo ""
echo "[4/4] Installing dependencies ($VARIANT variant)..."
echo "This may take several minutes..."
echo ""

pip install -e ".[$VARIANT]"
if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Installation failed"
    echo ""
    echo "Troubleshooting:"
    echo "1. Make sure you have internet connection"
    echo "2. Try: pip install -e .[$VARIANT] --verbose"
    echo "3. For CUDA version, ensure you have CUDA 12.1+ installed"
    exit 1
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Activate environment: source .venv/bin/activate"
echo "  2. Download models: python -m qmd.models.downloader"
echo "  3. Check system: qmd check"
echo "  4. Add collection: qmd collection add ./docs --name mydocs"
echo "  5. Index documents: qmd index"
echo ""
echo "To activate environment in new terminal:"
echo "  source .venv/bin/activate"
echo ""
