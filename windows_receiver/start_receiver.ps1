# PhoneMic Windows Receiver - One-Click PowerShell Launcher
$Host.UI.RawUI.WindowTitle = "PhoneMic Windows Receiver v0.6.1"
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "                  PhoneMic Windows Receiver v0.6.1 Launcher                    " -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Download Python from https://www.python.org and check 'Add Python to PATH'." -ForegroundColor Yellow
    Read-Host "Press Enter to exit..."
    exit 1
}

# Check Packages
Write-Host "[*] Checking audio libraries (sounddevice, numpy)..." -ForegroundColor Gray
$check = python -c "import sounddevice, numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] Installing required packages..." -ForegroundColor Yellow
    pip install sounddevice numpy
}

# Run Receiver
$scriptPath = Join-Path $PSScriptRoot "phonemic_receiver.py"
Write-Host "[*] Starting PhoneMic Receiver..." -ForegroundColor Green
python $scriptPath
