# Installed applications always use the complete pinned CPython payload.
function Resolve-AppLocalPython {
  $directory = Join-Path $Root 'runtime\python312'
  $manifestPath = Join-Path $directory 'runtime-manifest.json'
  if (!(Test-Path -LiteralPath $manifestPath)) { throw 'Runtime Python do instalador ausente.' }
  $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.version -ne '3.12.10' -or $manifest.architecture -ne 'x64' -or
      $manifest.sha256 -ne '0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8') {
    throw 'Manifesto Python do instalador invalido.'
  }
  $prefix = [IO.Path]::GetFullPath($directory).TrimEnd('\') + '\'
  $checked = 0
  $hasher = [Security.Cryptography.SHA256]::Create()
  try {
  foreach ($entry in $manifest.files.PSObject.Properties) {
    $path = [IO.Path]::GetFullPath((Join-Path $directory $entry.Name))
    if (!$path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
        ![IO.File]::Exists($path)) {
      throw 'Arquivos do runtime Python incompletos ou alterados. Reinstale este pacote.'
    }
    $stream = [IO.File]::OpenRead($path)
    try { $hash = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose() }
    if ($hash -ne $entry.Value) { throw 'Integridade do runtime Python invalida.' }
    $checked++
    if (($checked % 200) -eq 0) { Write-Host "Verificando Python local: $checked arquivos..." }
  }
  } finally { $hasher.Dispose() }
  $candidate = Join-Path $directory 'python.exe'
  if (!(Test-PythonBaseReady $candidate)) { throw 'Python/pip do aplicativo nao respondeu.' }
  return $candidate
}

function Assert-InstalledOfflineInputs {
  if (!(Test-Path -LiteralPath $WheelhouseDir) -or
      !(Get-ChildItem -LiteralPath $WheelhouseDir -Filter '*.whl' -File)) {
    throw 'Dependencias offline ausentes no instalador.'
  }
  if (!(Test-Path -LiteralPath (Join-Path $Root 'FRONTEND-HUB\dist-desktop\index.html'))) {
    throw 'Interface compilada ausente no instalador.'
  }
}
