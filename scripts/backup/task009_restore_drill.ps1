<#
.SYNOPSIS
  Task009 隔離還原演練：把指定備份還原到「非正式」目標並跑驗證查詢。嚴禁對正式資料庫執行。

.DESCRIPTION
  多重防呆：
  - 必須帶 -ConfirmIsolated，且環境變數 RESTORE_ALLOW_ISOLATED=1。
  - 還原目標連線只來自 RESTORE_PG* 環境變數（與備份來源 PG* 分離）。
  - 預設只允許 localhost/127.0.0.1/::1；遠端隔離目標必須在 RESTORE_ALLOWED_HOSTS 精確 allowlist。
  - 若 target 命中 Supabase 正式型態（*.supabase.co/*.supabase.com/pooler）一律拒絕。
  - source/target 以 host+port+database 比對，任一相同視為同一目標拒絕。
  - 預設 -DryRun：只列出將執行的步驟與驗證點，不連線、不還原。
  秘密僅來自環境變數，腳本不硬編。

.PARAMETER BackupDir
  含 schema/data dump 與 manifest.json 的備份目錄。

.PARAMETER DryRun
  只模擬（預設 true）。加 -DryRun:$false 才會實際還原（仍需通過所有隔離防呆）。

.NOTES
  還原目標環境變數：RESTORE_PGHOST, RESTORE_PGPORT, RESTORE_PGDATABASE, RESTORE_PGUSER, RESTORE_PGPASSWORD
  遠端 allowlist：RESTORE_ALLOWED_HOSTS（逗號分隔，精確比對）
  正式標記（拒絕還原）：固定內建 deny，不可由外部環境移除
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $BackupDir,
    [switch] $ConfirmIsolated,
  [string] $DryRun = 'true'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Write-Info([string] $m) { Write-Host "[task009-drill] $m" }
function Mask([string] $s) { if (-not $s) { return '<empty>' }; if ($s.Length -le 6) { return '***' }; return ('***' + $s.Substring($s.Length - 4)) }

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

function Normalize-Host([string] $h) {
  if (-not $h) { return '' }
  return $h.Trim().Trim('[', ']').ToLowerInvariant()
}

function Parse-BoolLike([string] $raw, [bool] $defaultValue) {
  if ($null -eq $raw -or $raw -eq '') { return $defaultValue }
  $v = $raw.Trim().ToLowerInvariant()
  if ($v -in @('true', '$true', '1', 'yes', 'y')) { return $true }
  if ($v -in @('false', '$false', '0', 'no', 'n')) { return $false }
  throw "DryRun 參數值不合法：$raw"
}

function Assert-HostAllowed([string] $targetHost) {
  $h = Normalize-Host $targetHost
  if (-not $h) { throw '缺少 RESTORE_PGHOST（隔離目標）' }

  if ($h -match '\.supabase\.co$' -or $h -match '\.supabase\.com$' -or $h -like '*pooler.supabase.com*') {
    throw '拒絕執行：目標命中 Supabase 正式網域型態'
  }

  $localAllowed = @('localhost', '127.0.0.1', '::1')
  if ($localAllowed -contains $h) { return }

  $allowRaw = @()
  if ($env:RESTORE_ALLOWED_HOSTS) {
    $allowRaw = @($env:RESTORE_ALLOWED_HOSTS.Split(',') | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ })
  }
  if ($allowRaw.Count -eq 0) {
    throw '拒絕執行：遠端隔離目標需明確設定 RESTORE_ALLOWED_HOSTS allowlist'
  }
  if (-not ($allowRaw -contains $h)) {
    throw '拒絕執行：目標不在 RESTORE_ALLOWED_HOSTS allowlist'
  }
}

function Assert-SourceTargetNotSame() {
  if (-not $env:PGHOST -or -not $env:PGDATABASE) { return }
  $srcHost = Normalize-Host $env:PGHOST
  $srcPort = if ($env:PGPORT) { $env:PGPORT.Trim() } else { '5432' }
  $srcDb = $env:PGDATABASE.Trim().ToLowerInvariant()

  $dstHost = Normalize-Host $env:RESTORE_PGHOST
  $dstPort = if ($env:RESTORE_PGPORT) { $env:RESTORE_PGPORT.Trim() } else { '5432' }
  $dstDb = if ($env:RESTORE_PGDATABASE) { $env:RESTORE_PGDATABASE.Trim().ToLowerInvariant() } else { '' }

  if ($srcHost -eq $dstHost -and $srcPort -eq $dstPort -and $srcDb -eq $dstDb) {
    throw '拒絕執行：source 與 target 的 host+port+database 相同'
  }
}

function Invoke-PsqlScalar([string] $query) {
  $psql = if ($env:PSQL_PATH) { $env:PSQL_PATH } else { 'psql' }
  $args = @('-t', '-A', '-v', 'ON_ERROR_STOP=1', '-c', $query)
  $raw = Invoke-ExternalTool -toolPath $psql -toolArgs $args
  if ($LASTEXITCODE -ne 0) { throw "psql 查詢失敗：$query" }
  return ($raw | Out-String).Trim()
}

function Assert-PostRestoreContracts([object] $manifest) {
  $requiredTables = @('public.xiaochenguang_memories', 'public.emotional_states', 'public.user_preferences')
  foreach ($t in $requiredTables) {
    $exists = Invoke-PsqlScalar "SELECT to_regclass('$t') IS NOT NULL;"
    if ($exists -ne 't') { throw "還原後缺少資料表：$t" }
  }

  $ownerCols = Invoke-PsqlScalar "SELECT (COUNT(*) = 2)::text FROM information_schema.columns WHERE table_schema='public' AND table_name='xiaochenguang_memories' AND column_name IN ('user_id','ai_id');"
  if ($ownerCols -ne 't') { throw '還原後 owner 欄位不完整（user_id/ai_id）' }

  $embeddingCol = Invoke-PsqlScalar "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='xiaochenguang_memories' AND column_name='embedding');"
  if ($embeddingCol -ne 't') { throw '還原後缺少 embedding 欄位' }

  $vectorExt = Invoke-PsqlScalar "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector');"
  if ($vectorExt -ne 't') { throw '還原後缺少 pgvector extension' }

  $sourceCounts = $null
  if ($manifest -and $manifest.PSObject.Properties.Name -contains 'source_contract' -and $manifest.source_contract) {
    if ($manifest.source_contract.PSObject.Properties.Name -contains 'source_row_counts') {
      $sourceCounts = $manifest.source_contract.source_row_counts
    }
  }

  if ($sourceCounts) {
    $rowCountQueryAllowlist = [ordered]@{
      'public.xiaochenguang_memories' = "SELECT COUNT(*)::text FROM public.xiaochenguang_memories;"
      'public.emotional_states'       = "SELECT COUNT(*)::text FROM public.emotional_states;"
      'public.user_preferences'       = "SELECT COUNT(*)::text FROM public.user_preferences;"
    }

    $expectedMap = @{}
    if ($sourceCounts -is [System.Collections.IDictionary]) {
      foreach ($k in $sourceCounts.Keys) {
        $expectedMap[[string]$k] = $sourceCounts[$k]
      }
    }
    else {
      foreach ($prop in $sourceCounts.PSObject.Properties) {
        $expectedMap[[string]$prop.Name] = $prop.Value
      }
    }

    foreach ($k in $expectedMap.Keys) {
      if (-not $rowCountQueryAllowlist.Contains($k)) {
        throw "source_row_counts 含未知 key：$k"
      }
    }
    foreach ($requiredKey in $rowCountQueryAllowlist.Keys) {
      if (-not $expectedMap.ContainsKey($requiredKey)) {
        throw "source_row_counts 缺少必要 key：$requiredKey"
      }
    }

    foreach ($tableName in $rowCountQueryAllowlist.Keys) {
      $expectedRaw = [string]$expectedMap[$tableName]
      [int]$expectedCount = 0
      if (-not [int]::TryParse($expectedRaw, [ref]$expectedCount)) {
        throw "manifest source_row_counts 不可解析：$tableName=$expectedRaw"
      }
      if ($expectedCount -lt 0) {
        throw "manifest source_row_counts 必須為非負整數：$tableName=$expectedCount"
      }
      $actualRaw = Invoke-PsqlScalar $rowCountQueryAllowlist[$tableName]
      [int]$actualCount = 0
      if (-not [int]::TryParse($actualRaw, [ref]$actualCount)) {
        throw "還原後 row_count 無法解析：$tableName=$actualRaw"
      }
      if ($actualCount -ne $expectedCount) {
        throw "還原後 row_count 不一致：$tableName expected=$expectedCount actual=$actualCount"
      }
    }
    Write-Info 'post_restore_data_verified=YES（已依 manifest source_row_counts 比對）'
  }
  else {
    Write-Info 'post_restore_data_verified=DEFERRED_TO_PHASE_B（manifest 無 source_row_counts，僅完成結構契約驗證）'
  }
}

try {
  $isDryRun = Parse-BoolLike -raw $DryRun -defaultValue $true

    if (-not $ConfirmIsolated) { throw '拒絕執行：缺少 -ConfirmIsolated（本腳本只允許對非正式目標演練）' }
    if ($env:RESTORE_ALLOW_ISOLATED -ne '1') { throw '拒絕執行：需環境變數 RESTORE_ALLOW_ISOLATED=1 明確授權隔離演練' }

  $backupRoot = Get-NormalizedPath $BackupDir
  $manifestPath = Join-Path $backupRoot 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "找不到 manifest：$manifestPath" }

  $restoreHost = $env:RESTORE_PGHOST
  Assert-HostAllowed -targetHost $restoreHost
  Assert-SourceTargetNotSame

    Write-Info ("還原目標（遮蔽）：host={0} db={1}" -f (Mask $restoreHost), (Mask $env:RESTORE_PGDATABASE))
  Write-Info ("備份目錄：{0}" -f $backupRoot)

  # 在任何 pg_restore 前都先做完整性驗證
  $manifestCheckScript = Join-Path $PSScriptRoot 'task009_manifest_check.ps1'
  & $manifestCheckScript -BackupDir $backupRoot
  if ($LASTEXITCODE -ne 0) { throw 'manifest/SHA 驗證未通過，拒絕還原' }

    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
  if ($manifest.backup_state -ne 'completed') { throw 'manifest backup_state 必須為 completed' }
  if ($manifest.dry_run -ne $false) { throw 'restore 僅接受 dry_run=false 的完整備份' }
  if ([string]$manifest.tool -ne 'task009_backup.ps1') { throw 'manifest tool 不合法' }
  if (-not [regex]::IsMatch([string]$manifest.tool_version, '^\d+\.\d+\.\d+$')) { throw 'manifest tool_version 不合法' }

  $files = @()
  if ($manifest.PSObject.Properties.Name -contains 'files' -and $manifest.files) { $files = @($manifest.files) }

  $seen = @{}
  $schemaCandidates = @()
  $dataCandidates = @()
  foreach ($f in $files) {
    $name = [string] $f.name
    if (-not $name) { throw 'manifest 含空檔名' }
    if ($name -ne [System.IO.Path]::GetFileName($name)) { throw 'manifest 檔名必須為 leaf name' }
    if ($seen.ContainsKey($name)) { throw "manifest 檔名重複：$name" }
    $seen[$name] = $true
    $resolved = Join-Path $backupRoot $name
    if (-not (Test-PathWithin -child $resolved -parent $backupRoot)) { throw "manifest 檔案越界：$name" }
    if ($name -like 'schema_*.dump') { $schemaCandidates += $resolved; continue }
    if ($name -like 'data_*.dump') { $dataCandidates += $resolved; continue }
    if ($name -like '*.dump') { throw "manifest 含未知 dump 類型：$name" }
  }

  if ($schemaCandidates.Count -ne 1) { throw 'manifest schema 候選必須恰好 1，拒絕歧義還原' }
  if ($dataCandidates.Count -ne 1) { throw 'manifest data 候選必須恰好 1，拒絕歧義還原' }

  $schemaPath = $schemaCandidates[0]
  $dataPath = $dataCandidates[0]

    Write-Info '還原順序：1) schema  2) data  3) 驗證查詢（row counts / 契約檢查）'

  if ($isDryRun) {
        Write-Info '[DRY-RUN] 將執行（不實際連線）：'
    Write-Info '[DRY-RUN] pg_restore --clean --if-exists --no-owner --no-privileges --dbname=<RESTORE target> <schema.dump>'
    Write-Info '[DRY-RUN] pg_restore --data-only --no-owner --no-privileges --dbname=<RESTORE target> <data.dump>'
    Write-Info '[DRY-RUN] psql SELECT-only 契約檢查：表、owner 欄位、embedding、pgvector、row_count'
        Write-Info 'TASK009_RESTORE_DRILL_DRYRUN_OK'
        exit 0
    }

  foreach ($req in @('RESTORE_PGHOST', 'RESTORE_PGPORT', 'RESTORE_PGDATABASE', 'RESTORE_PGUSER', 'RESTORE_PGPASSWORD')) {
    if (-not (Test-Path ("Env:{0}" -f $req)) -or -not (Get-Item ("Env:{0}" -f $req)).Value) {
      throw "非 dry-run 缺少必要環境變數：$req"
    }
  }

  if (-not $schemaPath -or -not (Test-Path -LiteralPath $schemaPath -PathType Leaf)) {
    throw '非 dry-run 缺少 schema dump，拒絕降級為 dry-run 成功'
  }
  if (-not $dataPath -or -not (Test-Path -LiteralPath $dataPath -PathType Leaf)) {
    throw '非 dry-run 缺少 data dump，拒絕降級為 dry-run 成功'
  }

  $pgRestore = if ($env:PG_RESTORE_PATH) { $env:PG_RESTORE_PATH } else { 'pg_restore' }

    # 實際隔離還原（僅在通過所有防呆且 -DryRun:$false 時）
    $env:PGHOST = $restoreHost
  $env:PGPORT = $env:RESTORE_PGPORT
    $env:PGDATABASE = $env:RESTORE_PGDATABASE
    $env:PGUSER = $env:RESTORE_PGUSER
    $env:PGPASSWORD = $env:RESTORE_PGPASSWORD

  $restoreSchemaArgs = @('--clean', '--if-exists', '--no-owner', '--no-privileges', "--dbname=$($env:PGDATABASE)", $schemaPath)
  Invoke-ExternalTool -toolPath $pgRestore -toolArgs $restoreSchemaArgs
    if ($LASTEXITCODE -ne 0) { throw "schema 還原失敗，代碼：$LASTEXITCODE" }
  $restoreDataArgs = @('--data-only', '--no-owner', '--no-privileges', "--dbname=$($env:PGDATABASE)", $dataPath)
  Invoke-ExternalTool -toolPath $pgRestore -toolArgs $restoreDataArgs
    if ($LASTEXITCODE -ne 0) { throw "data 還原失敗，代碼：$LASTEXITCODE" }

  Assert-PostRestoreContracts -manifest $manifest
  Write-Info '還原與契約驗證完成'
    Write-Info 'TASK009_RESTORE_DRILL_OK'
    exit 0
}
catch {
    Write-Error ("TASK009_RESTORE_DRILL_FAILED: {0}" -f $_.Exception.Message)
    exit 1
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
