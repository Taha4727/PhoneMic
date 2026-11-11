# PhoneMic Windows Receiver v1.2.0 - PowerShell launcher
$Host.UI.RawUI.WindowTitle = "PhoneMic Windows Receiver v1.2.0"

$exe = @("PhoneMicReceiver.exe", "dist\PhoneMicReceiver.exe", "dist\PhoneMicReceiver\PhoneMicReceiver.exe") |
    ForEach-Object { Join-Path $PSScriptRoot $_ } | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($exe) {
    Write-Host "[*] Starting $exe" -ForegroundColor Green
    Start-Process -FilePath $exe -ArgumentList $args
    exit 0
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "Download it from https://www.python.org and tick 'Add Python to PATH'." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

python -c "import numpy, sounddevice" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] Installing required packages (numpy, sounddevice)..." -ForegroundColor Yellow
    python -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
}

Write-Host "[*] Starting PhoneMic Receiver..." -ForegroundColor Green
python (Join-Path $PSScriptRoot "phonemic_receiver.py") @args
