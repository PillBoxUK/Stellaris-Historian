# One-click source-only export. Does not change the application, saves, or database.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$important = @('app.py', 'start.bat', 'historian_manifest.json', 'requirements.txt')
foreach ($name in $important) {
    if (-not (Test-Path -LiteralPath (Join-Path $root $name) -PathType Leaf)) {
        throw "Cannot locate $name in $root. Put BOTH export files in your StellarisHistorian application folder."
    }
}
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupDir = Join-Path $root 'autobackups'
if (-not (Test-Path -LiteralPath $backupDir -PathType Container)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}
$out = Join-Path $backupDir "Historian_Source_$stamp.zip"
$folders = @('historian','static','assets','docs','tests','test','scripts','migrations')
$allowedRootExtensions = @('.py','.bat','.cmd','.ps1','.md','.txt','.json','.toml','.ini','.cfg','.yaml','.yml','.css','.html','.js','.sql','.gitignore')
$blockedDirectories = @('__pycache__','.venv','venv','env','.git','.idea','.vscode','node_modules','backups','backup','autobackups','data','logs','payload','updates and source','dist','build','exports','output','cache','.pytest_cache','.mypy_cache')
$blockedExt = @('.sav','.db','.sqlite','.sqlite3','.zip','.7z','.rar','.pyc','.pyo','.log','.bak','.tmp','.key','.pem','.p12','.pfx','.env')
$blockedFileNames = @('config.json','.env','.env.local','.env.production','credentials.json','token.json','secrets.json')
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($out, [System.IO.Compression.ZipArchiveMode]::Create)
$filesCount = 0
try {
  # Include top-level source/config examples/documentation only.
  $fileList = New-Object 'System.Collections.Generic.List[System.IO.FileInfo]'
  foreach ($f in Get-ChildItem -LiteralPath $root -File -Force) {
    $name = $f.Name.ToLowerInvariant()
    if ($blockedFileNames -contains $name -or $blockedExt -contains $f.Extension.ToLowerInvariant()) { continue }
    if ($name -match '(?i)(secret|private|password|credential|token|apikey|api_key)') { continue }
    if ($allowedRootExtensions -contains $f.Extension.ToLowerInvariant() -or $name -eq '.gitignore') { $fileList.Add($f) }
  }
  foreach ($folderName in $folders) {
    $dir = Join-Path $root $folderName
    if (-not (Test-Path -LiteralPath $dir -PathType Container)) { continue }
    foreach ($f in Get-ChildItem -LiteralPath $dir -File -Recurse -Force) {
      $rel = $f.FullName.Substring($root.Length).TrimStart([char]'\',[char]'/')
      $parts = $rel -split '[\\/]'
      $segments = @($parts | Select-Object -SkipLast 1)
      if (@($segments | Where-Object { $blockedDirectories -contains $_.ToLowerInvariant() }).Count -gt 0) { continue }
      if ($blockedFileNames -contains $f.Name.ToLowerInvariant() -or $blockedExt -contains $f.Extension.ToLowerInvariant()) { continue }
      if ($f.Name -match '(?i)(secret|private|password|credential|token|apikey|api_key)') { continue }
      $fileList.Add($f)
    }
  }
  foreach ($f in $fileList) {
    $rel = $f.FullName.Substring($root.Length).TrimStart([char]'\',[char]'/').Replace('\','/')
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, $rel, [System.IO.Compression.CompressionLevel]::Optimal) | Out-Null
    $filesCount++
  }
} catch {
  $zip.Dispose()
  Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue
  throw
} finally { $zip.Dispose() }
if ($filesCount -eq 0) { Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue; throw 'No source files found.' }
Write-Host "Included files: $filesCount"
Write-Host "ZIP: $out"
Write-Host ('ZIP size: {0:N2} MB' -f ((Get-Item -LiteralPath $out).Length / 1MB))
Write-Host 'Excluded: saves, databases, backups, virtual environments, logs, archived patches, local config and credentials.'
Write-Host 'NOTE: Review the ZIP before sharing; custom source files might still contain secrets.'
