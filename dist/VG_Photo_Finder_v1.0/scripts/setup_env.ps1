param(
    [string]$Python = "python",
    [string]$VenvDir = ".venv"
)

Write-Host "Creating virtual environment in $VenvDir using $Python"
& $Python -m venv $VenvDir
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create venv"; exit 1 }

$venvPython = Join-Path -Path $VenvDir -ChildPath "Scripts\python.exe"
if (-Not (Test-Path $venvPython)) {
    Write-Error "Virtualenv python not found at $venvPython"
    exit 1
}

Write-Host "Upgrading pip and installing requirements.txt"
& $venvPython -m pip install --upgrade pip setuptools wheel
& $venvPython -m pip install -r (Join-Path -Path $PSScriptRoot -ChildPath "..\requirements.txt")

Write-Host "Setup complete. To run the app (PowerShell):"
Write-Host "  & $venvPython ..\app.py"
