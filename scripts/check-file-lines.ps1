param(
  [int]$MaxLines = 500
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$IgnoredParts = @(
  "\node_modules\",
  "\.venv\",
  "\dist\",
  "\runtime\",
  "\captures\",
  "\ms-playwright\",
  "\app\data\templates\"
)

$Files = Get-ChildItem -Path $Root -Recurse -File |
  Where-Object {
    $path = $_.FullName
    $ignored = $false
    foreach ($part in $IgnoredParts) {
      if ($path.Contains($part)) {
        $ignored = $true
        break
      }
    }
    $ignoredFiles = @("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    $ignoredExtensions = @(".exe", ".dll", ".pyd", ".zip", ".whl", ".pdf", ".xlsx")
    (-not $ignored) -and
      (-not $ignoredFiles.Contains($_.Name)) -and
      (-not $ignoredExtensions.Contains($_.Extension.ToLowerInvariant()))
  }

$TooLarge = foreach ($file in $Files) {
  $lines = (Get-Content -LiteralPath $file.FullName | Measure-Object -Line).Lines
  if ($lines -gt $MaxLines) {
    [PSCustomObject]@{
      Lines = $lines
      Path = $file.FullName.Substring($Root.Length + 1)
    }
  }
}

if ($TooLarge) {
  $TooLarge | Sort-Object Lines -Descending | Format-Table -AutoSize
  exit 1
}

Write-Host "OK: nenhum arquivo acima de $MaxLines linhas."
