param([ValidateSet('Preview','Apply','Undo')][string]$Mode='Preview', [string]$Manifest='')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$root=(Resolve-Path -LiteralPath $root).Path
$reportDir=Join-Path $root 'folder_reports'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$report=Join-Path $reportDir "Cleanup_${Mode}_$stamp.txt"
$items=New-Object System.Collections.Generic.List[object]
function AddPlan([string]$name,[string]$dest) {
 $source=Join-Path $root $name
 if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {return}
 $target=Join-Path $root $dest
 # Do not overwrite; report skipped collisions.
 $items.Add([pscustomobject]@{Source=$source;Destination=$target;RelativeSource=$name;RelativeDestination=$dest})
}
# Only root-level file candidates. The running application, migrations, and working folders are never moved.
Get-ChildItem -LiteralPath $root -File | ForEach-Object {
 $n=$_.Name
 if ($n -match '^README_v[0-9][0-9.]*\.md$') {AddPlan $n "documentation\release_notes\$n"}
 elseif ($n -match '^VALIDATION_v[0-9][0-9.]*\.txt$') {AddPlan $n "documentation\validation\$n"}
 elseif ($n -match '^INSTALL_v[0-9][0-9.]*\.txt$') {AddPlan $n "documentation\installation\$n"}
 elseif ($n -match '^Historian_Source_[0-9]{8}_[0-9]{6}\.zip$') {AddPlan $n "autobackups\$n"}
 elseif ($n -match '^(Historian_Source_Export_Utility|Historian_Autobackups_Exporter_Update)\.zip$') {AddPlan $n "archived_utilities\$n"}
 elseif ($n -match '^(HitorianUpload|Stellaris Backup)\.zip$') {AddPlan $n "archived_installers\$n"}
}
# Explicit old extracted utilities, never other directories.
foreach($n in @('Historian_Autobackups_Exporter_Update','Historian_Source_Export_Utility')) {
 $p=Join-Path $root $n
 if(Test-Path -LiteralPath $p -PathType Container) {
  $items.Add([pscustomobject]@{Source=$p;Destination=(Join-Path $root "archived_utilities\$n");RelativeSource=$n;RelativeDestination="archived_utilities\$n"})
 }
}
$notes=New-Object System.Collections.Generic.List[string]
$notes.Add("Stellaris Historian cleanup | $Mode | $stamp")
$notes.Add('Only allowlisted root-level support files. No deletes or overwrites.')
$notes.Add('App files, migrations, config, saves, databases, logs, .venv, backups and existing archive folders are untouched.')
$done=New-Object System.Collections.Generic.List[object]
if($Mode -eq 'Undo') {
 if (-not $Manifest) {throw 'Undo requires -Manifest pointing to a manifest JSON from Apply.'}
 $manifestPath=(Resolve-Path -LiteralPath $Manifest).Path
 if (-not $manifestPath.StartsWith($reportDir + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) {throw 'Manifest must be inside folder_reports.'}
 $records=@(Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json)
 foreach($record in $records) {
  $from=Join-Path $root ([string]$record.RelativeDestination)
  $to=Join-Path $root ([string]$record.RelativeSource)
  if((Test-Path -LiteralPath $from) -and -not (Test-Path -LiteralPath $to)) {
   Move-Item -LiteralPath $from -Destination $to -ErrorAction Stop
   $notes.Add("RESTORED $($record.RelativeDestination) -> $($record.RelativeSource)")
  } else {$notes.Add("SKIPPED restore $($record.RelativeDestination) (missing or destination occupied)")}
 }
} else {
 foreach($item in $items) {
  if(Test-Path -LiteralPath $item.Destination) {
   $notes.Add("SKIP (destination exists) $($item.RelativeSource) -> $($item.RelativeDestination)");continue
  }
  if($Mode -eq 'Preview') {$notes.Add("WOULD MOVE $($item.RelativeSource) -> $($item.RelativeDestination)");continue}
  try {
   $parent=Split-Path -Parent $item.Destination
   New-Item -ItemType Directory -Path $parent -Force | Out-Null
   Move-Item -LiteralPath $item.Source -Destination $item.Destination -ErrorAction Stop
   $done.Add([pscustomobject]@{RelativeSource=$item.RelativeSource;RelativeDestination=$item.RelativeDestination})
   $notes.Add("MOVED $($item.RelativeSource) -> $($item.RelativeDestination)")
  } catch {$notes.Add("ERROR $($item.RelativeSource): $($_.Exception.Message)")}
 }
 if($Mode -eq 'Apply') {
  $manifestOut=Join-Path $reportDir "Cleanup_Manifest_$stamp.json"
  ConvertTo-Json -InputObject @($done.ToArray()) -Depth 4 | Set-Content -LiteralPath $manifestOut -Encoding UTF8
  $notes.Add("UNDO MANIFEST: $manifestOut")
 }
}
$notes | Set-Content -LiteralPath $report -Encoding UTF8
$notes | ForEach-Object {Write-Host $_}
Write-Host "`nReport: $report"
if($Mode -eq 'Apply') {Write-Host "Successfully moved: $($done.Count)"}
