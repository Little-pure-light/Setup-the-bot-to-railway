<#
.SYNOPSIS
  Task009 自動化備份（PostgreSQL schema+data）+ SHA-256 + 去敏 manifest + 精確 retention。

.DESCRIPTION
  Phase A 倉庫層腳本。秘密只來自環境變數。
  -DryRun 為真正非破壞模式：不建立/修改/刪除任何檔案或目錄。
  retention 僅刪除「同 label + 命名合法 + completed manifest 合法」的舊備份。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)] [string] $BackupRoot,
  [int] $RetentionCount = 7,
  [string] $Label = 'task009',
  [string[]] $Schemas = @('public'),
  [string] $EnvironmentLabel = 'unspecified',
  [string] $PgDump = $(if ($env:PG_DUMP_PATH) { $env:PG_DUMP_PATH } else { 'pg_dump' }),
  [string] $TimestampOverride,
  [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Write-Info([string] $m) { Write-Host "[task009] $m" }

function Invoke-ExternalTool([string] $toolPath, [string[]] $toolArgs) {
  if ($toolPath -match '\.ps1$') {
    $psCmd = Get-Command pwsh -ErrorAction SilentlyContinue
    if (-not $psCmd) { $psCmd = Get-Command powershell -ErrorAction SilentlyContinue }
    if (-not $psCmd) { throw '找不到可執行的 PowerShell（pwsh/powershell）' }
    & $psCmd.Source -NoProfile -ExecutionPolicy Bypass -File $toolPath @toolArgs
    return
  }
  & $toolPath @toolArgs
}

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

function Test-ManifestBasic([string] $dirPath, [string] $expectedLabel) {
  try {
    $manifestPath = Join-Path $dirPath 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { return $false }
    $m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($m.backup_state -ne 'completed') { return $false }
    if ($m.label -ne $expectedLabel) { return $false }
    if ($m.dry_run -eq $true) { return $false }
    if (-not $m.files) { return $false }

    $files = @($m.files)
    if ($files.Count -lt 2) { return $false }
    $seen = @{}
    foreach ($f in $files) {
      $name = [string] $f.name
      if (-not $name) { return $false }
      if ($name -ne [System.IO.Path]::GetFileName($name)) { return $false }
      if ($seen.ContainsKey($name)) { return $false }
      $seen[$name] = $true
      if ($f.size_bytes -le 0) { return $false }
      if (-not [regex]::IsMatch([string]$f.sha256, '^[A-Fa-f0-9]{64}$')) { return $false }
      $resolved = Join-Path $dirPath $name
      if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) { return $false }
      if ((Get-Item -LiteralPath $resolved).Length -le 0) { return $false }
    }
    return $true
  }
  catch {
    return $false
  }
}

function Get-RetentionCandidates([string] $backupRootResolved, [string] $labelSafe, [int] $keepCount) {
  $nameRegex = '^{0}_\d{{8}}_\d{{6}}(?:_\d{{3}})?$' -f [regex]::Escape($labelSafe)
  $dirs = @(
    Get-ChildItem -LiteralPath $backupRootResolved -Directory -ErrorAction SilentlyContinue |
      Where-Object { $_.Name -match $nameRegex } |
      Where-Object { Test-ManifestBasic -dirPath $_.FullName -expectedLabel $labelSafe } |
      Sort-Object Name -Descending
  )

  if ($dirs.Count -le $keepCount) {
    return @([pscustomobject]@{ Keep = $dirs; Delete = @() })
  }

  $keep = @($dirs | Select-Object -First $keepCount)
  $delete = @($dirs | Select-Object -Skip $keepCount)
  return @([pscustomobject]@{ Keep = $keep; Delete = $delete })
}

function Get-UniqueBackupDir([string] $backupRootResolved, [string] $baseName) {
  $candidate = Join-Path $backupRootResolved $baseName
  if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
  for ($i = 1; $i -le 999; $i++) {
    $suffix = ('_{0:D3}' -f $i)
    $candidate = Join-Path $backupRootResolved ($baseName + $suffix)
    if (-not (Test-Path -LiteralPath $candidate)) { return $candidate }
  }
  throw '無法建立唯一備份目錄（同秒碰撞超過 999 次）'
}

function Assert-SafeSchemaList([string[]] $schemaList) {
  if (-not $schemaList -or $schemaList.Count -ne 1) {
    throw 'Phase A 僅允許單一 schema=public'
  }
  $schema = [string]$schemaList[0]
  if (-not [regex]::IsMatch($schema, '^[A-Za-z_][A-Za-z0-9_]*$')) {
    throw "Schema 名稱不安全：$schema"
  }
  if ($schema -ne 'public') {
    throw 'Phase A 僅允許 schema=public'
  }
}

try {
  if ($RetentionCount -lt 1) {
    throw "RetentionCount 必須 >= 1（收到 $RetentionCount）"
  }

  if (-not [regex]::IsMatch($Label, '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')) {
    throw 'Label 格式不安全：僅允許英數、底線、連字號，且不得含路徑或 wildcard 字元'
  }

  if (-not [regex]::IsMatch($EnvironmentLabel, '^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')) {
    throw 'EnvironmentLabel 格式不安全：僅允許英數、底線、連字號'
  }

  Assert-SafeSchemaList -schemaList $Schemas

  if (-not (Test-Path -LiteralPath $BackupRoot -PathType Container)) {
    throw "BackupRoot 不存在或非目錄：$BackupRoot"
  }

  $backupRootResolved = Get-NormalizedPath $BackupRoot
  $driveRoot = [System.IO.Path]::GetPathRoot($backupRootResolved).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ($backupRootResolved -eq $driveRoot) {
    throw '拒絕使用磁碟根目錄作為 BackupRoot'
  }

  $homePathResolved = Get-NormalizedPath $HOME
  $dangerPaths = @($homePathResolved, (Join-Path $homePathResolved 'Desktop'), (Join-Path $homePathResolved 'Documents'), (Join-Path $homePathResolved 'Downloads'))
  foreach ($dp in $dangerPaths) {
    if ($backupRootResolved -eq (Get-NormalizedPath $dp)) {
      throw "拒絕使用寬廣危險目錄：$backupRootResolved"
    }
  }

  $repoRoot = Get-NormalizedPath (Join-Path $PSScriptRoot '..\..')
  if (Test-PathWithin -child $backupRootResolved -parent $repoRoot) {
    throw '拒絕使用 repository 內目錄作為實際 dump 目的地（避免私人資料進 repo）'
  }
  if ($backupRootResolved -match 'just_for_copilot[\\/]read_data[\\/]just_for_Grok') {
    throw '拒絕使用協作資料夾作為實際 dump 目的地'
  }

  $timestamp = if ($TimestampOverride) { $TimestampOverride } else { Get-Date -Format 'yyyyMMdd_HHmmss' }
  if (-not [regex]::IsMatch($timestamp, '^\d{8}_\d{6}$')) {
    throw "timestamp 格式錯誤：$timestamp"
  }

  $gitCommit = @($env:RAILWAY_GIT_COMMIT_SHA, $env:GIT_COMMIT, $env:GITHUB_SHA) |
    Where-Object { $_ } | Select-Object -First 1
  if (-not $gitCommit) { $gitCommit = 'unknown' }
  if ($gitCommit -ne 'unknown' -and -not [regex]::IsMatch($gitCommit, '^[A-Fa-f0-9]{7,40}$')) {
    $gitCommit = 'unknown'
  }
  $gitCommitShort = if ($gitCommit.Length -ge 12) { $gitCommit.Substring(0, 12) } else { $gitCommit }

  $baseName = ("{0}_{1}" -f $Label, $timestamp)
  $backupDir = Get-UniqueBackupDir -backupRootResolved $backupRootResolved -baseName $baseName

  $retention = Get-RetentionCandidates -backupRootResolved $backupRootResolved -labelSafe $Label -keepCount $RetentionCount
  $currentKeepCount = @($retention[0].Keep).Count
  $currentDeleteCount = @($retention[0].Delete).Count

  if ($DryRun) {
    Write-Info '[DRY-RUN] 非破壞模式：不建立/修改/刪除任何檔案。'
    Write-Info ("[DRY-RUN] 計畫建立目錄：{0}" -f $backupDir)
    Write-Info ("[DRY-RUN] 匯出 schema：{0} --schema-only --schema={1} --format=custom --file=<schema.dump>" -f $PgDump, $Schemas[0])
    Write-Info ("[DRY-RUN] 匯出 data  ：{0} --data-only --schema={1} --format=custom --file=<data.dump>" -f $PgDump, $Schemas[0])
    Write-Info ("[DRY-RUN] retention keep={0} delete_candidates={1}" -f $currentKeepCount, $currentDeleteCount)
    Write-Info 'TASK009_BACKUP_DRYRUN_OK'
    exit 0
  }

  foreach ($req in @('PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD')) {
    if (-not (Test-Path ("Env:{0}" -f $req))) {
      throw "缺少必要連線環境變數：$req（請於執行環境設定，勿硬編）"
    }
  }
  if (-not $env:PGPORT) { $env:PGPORT = '5432' }
  if (-not $env:PGSSLMODE) { $env:PGSSLMODE = 'require' }

  New-Item -ItemType Directory -Path $backupDir -ErrorAction Stop | Out-Null
  Write-Info ("建立備份目錄：{0}" -f $backupDir)

  $schemaDump = Join-Path $backupDir ("schema_{0}_{1}.dump" -f ($Schemas -join '-'), $timestamp)
  $dataDump = Join-Path $backupDir ("data_{0}_{1}.dump" -f ($Schemas -join '-'), $timestamp)
  $manifestPath = Join-Path $backupDir 'manifest.json'

  $schemaArgs = @()
  foreach ($s in $Schemas) {
    $schemaArgs += "--schema=$s"
  }

  $schemaOnlyArgs = @('--schema-only') + $schemaArgs + @('--no-owner', '--no-privileges', '--format=custom', "--file=$schemaDump")
  $dataOnlyArgs = @('--data-only') + $schemaArgs + @('--no-owner', '--no-privileges', '--format=custom', "--file=$dataDump")

  Invoke-ExternalTool -toolPath $PgDump -toolArgs $schemaOnlyArgs
  if ($LASTEXITCODE -ne 0) { throw "schema 匯出失敗，代碼：$LASTEXITCODE" }

  Invoke-ExternalTool -toolPath $PgDump -toolArgs $dataOnlyArgs
  if ($LASTEXITCODE -ne 0) { throw "data 匯出失敗，代碼：$LASTEXITCODE" }

  $files = @()
  foreach ($f in @($schemaDump, $dataDump)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { throw "預期備份檔不存在：$f" }
    $len = (Get-Item -LiteralPath $f).Length
    if ($len -le 0) { throw "備份檔是空的：$f" }
    $hash = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash
    $files += [ordered]@{ name = (Split-Path $f -Leaf); size_bytes = $len; sha256 = $hash }
  }

  $pgRestore = if ($env:PG_RESTORE_PATH) { $env:PG_RESTORE_PATH } else { 'pg_restore' }
  $schemaListArgs = @('--list', $schemaDump)
  $schemaEntryCount = @(Invoke-ExternalTool -toolPath $pgRestore -toolArgs $schemaListArgs).Count
  if ($LASTEXITCODE -ne 0) { throw 'schema 備份檔無法讀取' }
  $dataListArgs = @('--list', $dataDump)
  $dataEntryCount = @(Invoke-ExternalTool -toolPath $pgRestore -toolArgs $dataListArgs).Count
  if ($LASTEXITCODE -ne 0) { throw 'data 備份檔無法讀取' }

  $manifest = [ordered]@{
    backup_state       = 'completed'
    label              = $Label
    timestamp          = $timestamp
    environment_label  = $EnvironmentLabel
    git_commit_short   = $gitCommitShort
    schemas            = $Schemas
    dry_run            = $false
    files              = $files
    schema_entry_count = $schemaEntryCount
    data_entry_count   = $dataEntryCount
    created_utc        = (Get-Date).ToUniversalTime().ToString('o')
    tool               = 'task009_backup.ps1'
    tool_version       = '1.0.0'
    source_contract    = [ordered]@{
      source_row_counts          = $null
      post_restore_data_verified = 'DEFERRED_TO_PHASE_B'
      notes                      = 'Phase A 不執行 source row count 查詢；不得宣稱已完成資料恢復比對'
    }
  }
  ($manifest | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $manifestPath -Encoding UTF8
  Write-Info ("寫入去敏 manifest：{0}" -f $manifestPath)

  $retentionAfter = Get-RetentionCandidates -backupRootResolved $backupRootResolved -labelSafe $Label -keepCount $RetentionCount
  $toDelete = @($retentionAfter[0].Delete)
  foreach ($d in $toDelete) {
    if (-not (Test-PathWithin -child $d.FullName -parent $backupRootResolved)) {
      throw "拒絕刪除 BackupRoot 之外路徑：$($d.FullName)"
    }
    if ((Get-NormalizedPath $d.FullName) -eq (Get-NormalizedPath $backupDir)) {
      continue
    }
    Write-Info ("retention 刪除舊備份：{0}" -f $d.Name)
    Remove-Item -LiteralPath $d.FullName -Recurse -ErrorAction Stop
  }

  $kept = @($retentionAfter[0].Keep).Count
  Write-Info ("retention keep={0} deleted={1}" -f $kept, $toDelete.Count)
  Write-Info ("BACKUP_DIR={0}" -f $backupDir)
  Write-Info 'TASK009_BACKUP_OK'
  exit 0
}
catch {
  Write-Error ("TASK009_BACKUP_FAILED: {0}" -f $_.Exception.Message)
  exit 1
}
