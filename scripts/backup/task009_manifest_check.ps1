<#
.SYNOPSIS
  驗證 Task009 備份：依 manifest.json 重新計算 SHA-256 並比對，確認檔案存在、大小與雜湊一致。

.PARAMETER BackupDir
  含 manifest.json 的備份目錄。

.NOTES
  dry-run manifest（dry_run=true 且無 files）視為 SKIP（無真實 dump 可驗），退出碼 0 並標記 skipped。
  任一檔案缺失/大小不符/雜湊不符 → 退出碼 1。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $BackupDir
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Write-Info([string] $m) { Write-Host "[task009-check] $m" }

function Get-NormalizedPath([string] $p) {
  return [System.IO.Path]::GetFullPath($p).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
}

function Test-PathWithin([string] $child, [string] $parent) {
  $childN = Get-NormalizedPath $child
  $parentN = Get-NormalizedPath $parent
  if ($childN.Length -lt $parentN.Length) { return $false }
  if ($childN -eq $parentN) { return $true }
  return $childN.StartsWith($parentN + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

try {
  $backupRoot = Get-NormalizedPath $BackupDir
  $manifestPath = Join-Path $backupRoot 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "找不到 manifest：$manifestPath" }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json

    if ($manifest.backup_state -ne 'completed') { throw 'manifest backup_state 必須為 completed' }
    if ($manifest.dry_run -ne $false) { throw 'manifest dry_run 必須為 false' }
    if (-not [regex]::IsMatch([string]$manifest.label, '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')) { throw 'manifest label 不合法' }
    if ([string]$manifest.tool -ne 'task009_backup.ps1') { throw 'manifest tool 不合法' }
    if (-not [regex]::IsMatch([string]$manifest.tool_version, '^\d+\.\d+\.\d+$')) { throw 'manifest tool_version 不合法' }

    $files = @()
    if ($manifest.PSObject.Properties.Name -contains 'files' -and $manifest.files) { $files = @($manifest.files) }
    if ($files.Count -eq 0) { throw 'manifest 未列任何檔案，無法驗證' }

    $seenNames = @{}
    $schemaCandidates = 0
    $dataCandidates = 0
    $unknownDumpCandidates = 0

    $fail = 0
    foreach ($f in $files) {
      $name = [string] $f.name
      if (-not $name) { Write-Info 'FAIL 檔名為空'; $fail++; continue }
      if ($name -ne [System.IO.Path]::GetFileName($name)) { Write-Info ("FAIL 非 leaf 檔名：{0}" -f $name); $fail++; continue }
      if ($seenNames.ContainsKey($name)) { Write-Info ("FAIL 重複檔名：{0}" -f $name); $fail++; continue }
      $seenNames[$name] = $true

      if ($name -like 'schema_*.dump') { $schemaCandidates++ }
  elseif ($name -like 'data_*.dump') { $dataCandidates++ }
  elseif ($name -like '*.dump') { $unknownDumpCandidates++ }

      $p = Join-Path $backupRoot $name
      if (-not (Test-PathWithin -child $p -parent $backupRoot)) { Write-Info ("FAIL 檔案路徑越界：{0}" -f $name); $fail++; continue }
      if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { Write-Info ("FAIL 缺檔：{0}" -f $name); $fail++; continue }
        $len = (Get-Item -LiteralPath $p).Length
        $hash = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
        if ($len -ne $f.size_bytes) { Write-Info ("FAIL 大小不符：{0}（{1} != {2}）" -f $f.name, $len, $f.size_bytes); $fail++; continue }
      if (-not [regex]::IsMatch([string]$f.sha256, '^[A-Fa-f0-9]{64}$')) { Write-Info ("FAIL 雜湊格式不合法：{0}" -f $f.name); $fail++; continue }
      if ($hash -ne $f.sha256) { Write-Info ("FAIL 雜湊不符：{0}" -f $f.name); $fail++; continue }
        Write-Info ("PASS {0} size={1} sha256=OK" -f $f.name, $len)
    }

  if ($schemaCandidates -ne 1) { Write-Info ("FAIL schema 候選必須恰好 1（目前 {0}）" -f $schemaCandidates); $fail++ }
  if ($dataCandidates -ne 1) { Write-Info ("FAIL data 候選必須恰好 1（目前 {0}）" -f $dataCandidates); $fail++ }
  if ($unknownDumpCandidates -ne 0) { Write-Info ("FAIL 不允許未知 dump 候選（目前 {0}）" -f $unknownDumpCandidates); $fail++ }

    if ($fail -gt 0) { throw ("驗證失敗項目數：{0}" -f $fail) }
    Write-Info 'TASK009_MANIFEST_CHECK_PASS'
    exit 0
}
catch {
    Write-Error ("TASK009_MANIFEST_CHECK_FAILED: {0}" -f $_.Exception.Message)
    exit 1
}
