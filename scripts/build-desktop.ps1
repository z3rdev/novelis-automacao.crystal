param()

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $Root "BACKEND\.venv\Scripts\python.exe"
$RuntimeDir = Join-Path $Root "runtime"
$DistDir = Join-Path $Root "dist\desktop"

function Invoke-Checked {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
  )
  & $FilePath @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Comando falhou: $FilePath $($Arguments -join ' ')"
  }
}

if (-not (Test-Path $PythonExe)) {
  Write-Host "Backend nao tem .venv. Rode scripts\bootstrap.ps1 primeiro." -ForegroundColor Yellow
  exit 1
}

New-Item -ItemType Directory -Force $RuntimeDir | Out-Null
Remove-Item -LiteralPath (Join-Path $DistDir "AutomacaoNovelis") -Recurse -Force -ErrorAction SilentlyContinue
Invoke-Checked $PythonExe -m pip install -r (Join-Path $Root "DESKTOP\requirements-build.txt")
Invoke-Checked $PythonExe -m PyInstaller `
  --noconfirm `
  --onedir `
  --windowed `
  --name "AutomacaoNovelis" `
  --paths (Join-Path $Root "DESKTOP") `
  --distpath $DistDir `
  --workpath (Join-Path $RuntimeDir "pyinstaller-build") `
  --specpath $RuntimeDir `
  (Join-Path $Root "DESKTOP\run_app.py")

Write-Host "Executavel gerado em $(Join-Path $DistDir 'AutomacaoNovelis\AutomacaoNovelis.exe')"
