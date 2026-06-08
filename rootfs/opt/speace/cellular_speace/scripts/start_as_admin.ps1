# SPEACE - Avvio con privilegi di Amministratore

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Split-Path -Parent $scriptPath
$pythonPath = (Get-Command python).Source

if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Host "SPEACE: Richiedo privilegi di amministratore..." -ForegroundColor Yellow
    $startArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Start-Process powershell -Verb RunAs -ArgumentList $startArgs
    exit
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SPEACE - Avvio con privilegi elevati" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "User:          $([Environment]::UserName)"
Write-Host "Host:          $env:COMPUTERNAME"
Write-Host "Root:          $projectRoot"
Write-Host "Python:        $pythonPath"

# Verifica link simbolico
if (-not (Test-Path -LiteralPath "$projectRoot\root_link")) {
    Write-Host "Creazione link simbolico root_link..." -ForegroundColor Yellow
    cmd /c "mklink /D $projectRoot\root_link C:\" 2>&1 | Out-Null
}

# Aggiungi esclusione Windows Defender
Write-Host "Aggiunta esclusione Windows Defender per $projectRoot..." -ForegroundColor Yellow
try {
    Add-MpPreference -ExclusionPath "$projectRoot" -ErrorAction Stop
    Write-Host "  OK" -ForegroundColor Green
} catch {
    Write-Host "  Errore: $_" -ForegroundColor Yellow
}

# VFS index
Write-Host "Indicizzazione VFS..." -ForegroundColor Yellow
& $pythonPath -m speace_core.cli vfs-index

# System assimilation
Write-Host "Assimilazione sistema..." -ForegroundColor Yellow
& $pythonPath -m speace_core.cli assimilate

# Avvio runtime
Write-Host "Avvio SPEACE Runtime continuo..." -ForegroundColor Green
$runtimeScript = Join-Path (Join-Path $projectRoot "scripts") "start_runtime.py"
& $pythonPath $runtimeScript
