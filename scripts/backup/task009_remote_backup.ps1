<#
.SYNOPSIS
  Task009-006 加密遠端備份 orchestrator（repository 施工；正式啟用屬 Task009-007）。

.DESCRIPTION
  沿用 Phase A `task009_backup.ps1` 產物與 manifest 契約（不建立第二套格式）：
    固定四表 row-count -> task009_backup.ps1(schema_*/data_*/manifest, tool=task009_backup.ps1)
    -> 注入 source_contract.source_row_counts -> task009_manifest_check.ps1（隔離 subprocess，成功後繼續）
    -> tar -> age 公鑰加密 -> 私有 R2 上傳(含 SHA-256 object metadata)
    -> HEAD 驗證(size + metadata checksum) -> 精確清理。
  秘密只來自環境變數名稱；不硬編、不輸出值/連線字串/endpoint/私鑰。fail-closed；絕不上傳明文。
  外部工具（Phase A / psql / age / S3 client / tar）stdout+stderr 一律「捕捉不外流」：
    失敗時只回報安全階段名 + exit code + 去敏錯誤類別，避免 endpoint/bucket/host/user/secret 洩漏至 CI log。
  固定四表 row-count 集合為程式常數，production 無呼叫端輸入可縮減；subset/unknown/duplicate 皆於任何 SQL 查詢前 fail-closed。
  工具路徑由環境變數注入（CI 以 fake 工具測試）：PG_DUMP_PATH / PG_RESTORE_PATH / PSQL_PATH / AGE_PATH / S3_CLIENT_PATH。
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $WorkRoot,
    [string] $Label = 'task009',
    [string] $ObjectPrefix = 'xcg/pg/public',
    [string] $RunId = $(if ($env:GITHUB_RUN_ID) { $env:GITHUB_RUN_ID } else { 'local' }),
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Log([string] $m) { Write-Host "[t009-remote] $m" }

# 固定 schema（強制恰為 public）
$Schemas = @('public')

# 固定 row-count allowlist（table -> 固定 SQL）；key 為 public. 前綴以與 restore_drill 契約完全一致。
# SQL identifier 只來自此常數，非輸入/manifest/env。此為「完整且不可縮減」的四表集合。
$RowCountAllowlist = [ordered]@{
    'public.xiaochenguang_memories'    = 'select count(*) from public.xiaochenguang_memories;'
    'public.xiaochenguang_reflections' = 'select count(*) from public.xiaochenguang_reflections;'
    'public.emotional_states'          = 'select count(*) from public.emotional_states;'
    'public.user_preferences'          = 'select count(*) from public.user_preferences;'
}

$script:runDir = $null

function Tool([string] $n, [string] $d) { $v = [Environment]::GetEnvironmentVariable($n); if ($v) { $v } else { $d } }
function Require-Env([string[]] $names) { foreach ($n in $names) { if (-not [Environment]::GetEnvironmentVariable($n)) { throw "缺少必要環境變數：$n" } } }
function Get-PwshExe() {
    $c = Get-Command pwsh -ErrorAction SilentlyContinue
    if (-not $c) { $c = Get-Command powershell -ErrorAction SilentlyContinue }
    if (-not $c) { throw '找不到 PowerShell 執行檔' }
    return $c.Source
}
function Assert-SafeToken([string] $value, [string] $name, [string] $pattern) {
    if ([string]::IsNullOrWhiteSpace($value)) { throw "$name 不可為空" }
    if ($value -match '\.\.' -or $value -match '[\x00-\x1f]') { throw "$name 含非法字元（.. 或控制字元）" }
    if ($value -notmatch $pattern) { throw "$name 格式不合法" }
}
function Assert-UnderRunnerTemp([string] $path) {
    $tmp = @($env:RUNNER_TEMP, $env:TMPDIR, $env:TEMP, $env:TMP) | Where-Object { $_ } | Select-Object -First 1
    if (-not $tmp) { throw '找不到 runner 暫存根（RUNNER_TEMP/TMPDIR/TEMP）' }
    $tmpFull = [IO.Path]::GetFullPath($tmp).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $pFull = [IO.Path]::GetFullPath($path).TrimEnd([IO.Path]::DirectorySeparatorChar)
    if ($pFull -ne $tmpFull -and -not $pFull.StartsWith($tmpFull + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "路徑不在 runner 暫存根之下，拒絕：$pFull"
    }
    return $pFull
}

# 固定四表集合完整性驗證：subset(缺)/unknown(多)/duplicate(重) 於任何 SQL 查詢前 fail-closed。
function Assert-CompleteRowCountSet([string[]] $Declared, $Allowlist) {
    $required = @($Allowlist.Keys)
    $seen = @{}
    foreach ($d in $Declared) {
        if ($seen.ContainsKey($d)) { throw "row-count 集合含重複表（查詢前拒絕）：$d" }
        $seen[$d] = $true
    }
    foreach ($d in $Declared) {
        if (-not $Allowlist.Contains($d)) { throw "未知 row-count 表（查詢前拒絕）：$d" }
    }
    foreach ($r in $required) {
        if (-not $seen.ContainsKey($r)) { throw "row-count 集合缺少必要表（查詢前拒絕）：$r" }
    }
}

# 外部工具去敏執行：捕捉 stdout/stderr 至暫存檔，永不外流原始輸出；
# 失敗只 throw「external_tool_error stage=<階段> exit=<碼>」。需要 stdout 者（psql/HEAD）由回傳值取得，但不記錄。
function Invoke-Captured([string] $exe, [string[]] $argList, [string] $stage) {
    $capBase = if ($script:runDir -and (Test-Path -LiteralPath $script:runDir)) { $script:runDir } else { [IO.Path]::GetTempPath() }
    $o = Join-Path $capBase ('.cap_o_' + [guid]::NewGuid().ToString('N'))
    $e = Join-Path $capBase ('.cap_e_' + [guid]::NewGuid().ToString('N'))
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $code = $null
    try {
        if ($exe -like '*.ps1') {
            # 測試 fake 工具為 .ps1：以真正子行程執行，讓其 OS stderr（含 [Console]::Error）被 2> 捕捉，
            # 忠實對應 production 的原生二進位工具行為。
            & $script:pwshExe -NoProfile -File $exe @argList 1>$o 2>$e
        }
        else {
            & $exe @argList 1>$o 2>$e
        }
        $code = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $prev }
    $out = ''
    if (Test-Path -LiteralPath $o) { $out = Get-Content -LiteralPath $o -Raw }
    Remove-Item -LiteralPath $o, $e -Force -ErrorAction SilentlyContinue
    if ($null -eq $code) { $code = 0 }
    if ($code -ne 0) { throw ("external_tool_error stage={0} exit={1}" -f $stage, $code) }
    return $out
}

# 精確清理 helper：僅在 runner 暫存根之下才刪除；越界則拒絕刪除（fail-closed，不動 sibling/外部檔）。
function Remove-RunDirSafe([string] $path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return }
    $safe = Assert-UnderRunnerTemp $path   # 越界即 throw -> 不刪除
    if (Test-Path -LiteralPath $safe) { Remove-Item -LiteralPath $safe -Recurse -Force -ErrorAction SilentlyContinue }
}

# 輸入安全驗證（P1-4）
Assert-SafeToken $Label 'Label' '^[A-Za-z0-9_-]{1,40}$'
Assert-SafeToken $RunId 'RunId' '^[A-Za-z0-9_-]{1,40}$'
Assert-SafeToken $ObjectPrefix 'ObjectPrefix' '^[A-Za-z0-9][A-Za-z0-9/_-]{0,80}$'

# production 固定使用完整四表集合（無呼叫端輸入可縮減）。
# 測試專用 seam：TASK009_ROWCOUNT_SET_OVERRIDE 僅用來驗證 subset/unknown/duplicate 一律 fail-closed；
# 任何偏離完整集合都會在查詢前丟例外，因此永遠無法真正縮減 production 查詢。
$declaredKeys = @($RowCountAllowlist.Keys)
if ($env:TASK009_ROWCOUNT_SET_OVERRIDE) {
    $declaredKeys = @($env:TASK009_ROWCOUNT_SET_OVERRIDE -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}
Assert-CompleteRowCountSet -Declared $declaredKeys -Allowlist $RowCountAllowlist

$pgDump = Tool 'PG_DUMP_PATH' 'pg_dump'
$psql = Tool 'PSQL_PATH' 'psql'
$age = Tool 'AGE_PATH' 'age'
$s3 = Tool 'S3_CLIENT_PATH' 'aws'
$script:pwshExe = Get-PwshExe

$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMdd_HHmmssZ')

try {
    $workParent = Assert-UnderRunnerTemp $WorkRoot
    $script:runDir = Assert-UnderRunnerTemp (Join-Path $workParent ("t009_remote_{0}_{1}" -f $timestamp, $RunId))
    New-Item -ItemType Directory -Force -Path $script:runDir | Out-Null
    Log 'run 目錄建立 (runner temp)'

    if ($DryRun) {
        Log '[DRY-RUN] 不連線 DB、不加密、不上傳。計畫：rowcount(固定四表) -> task009_backup.ps1 -> inject source_contract -> manifest_check -> tar -> age -> R2 upload(+sha256 metadata) -> HEAD(size+checksum) -> cleanup'
        foreach ($t in $RowCountAllowlist.Keys) { Log ("[DRY-RUN] rowcount 目標(固定四表)：{0}" -f $t) }
        Log 'TASK009_REMOTE_BACKUP_DRYRUN_OK'
        return
    }

    Require-Env @('PGHOST', 'PGDATABASE', 'PGUSER', 'PGPASSWORD', 'AGE_RECIPIENT', 'R2_BUCKET', 'R2_ENDPOINT', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY')
    if (-not $env:PGPORT) { $env:PGPORT = '5432' }
    $env:PGSSLMODE = 'require'

    # 1) 固定四表 row counts（去敏：psql 輸出僅供整數解析，不記錄原始輸出）
    $rowCounts = [ordered]@{}
    foreach ($t in $RowCountAllowlist.Keys) {
        $raw = Invoke-Captured $psql @('-t', '-A', '-v', 'ON_ERROR_STOP=1', '-c', $RowCountAllowlist[$t]) 'rowcount'
        $val = ("$raw").Trim()
        if ($val -notmatch '^\d+$') { throw "row-count 非整數（去敏，不含原始輸出）：$t" }
        $rowCounts[$t] = [int64] $val
    }
    Log ("row-count 完成（{0} 表，去敏）" -f $rowCounts.Count)

    # 2) 沿用 Phase A task009_backup.ps1 產生 schema_*/data_*/manifest（隔離 subprocess，輸出捕捉不外流）
    $backupScript = Join-Path $PSScriptRoot 'task009_backup.ps1'
    [void](Invoke-Captured $script:pwshExe @('-NoProfile', '-File', $backupScript, '-BackupRoot', $script:runDir, '-Label', $Label, '-RetentionCount', '9999', '-Schemas', 'public', '-EnvironmentLabel', 'production') 'phaseA_backup')

    $backupDir = @(Get-ChildItem -LiteralPath $script:runDir -Directory -Filter ("{0}_*" -f $Label) | Sort-Object Name -Descending | Select-Object -First 1)
    if (-not $backupDir -or $backupDir.Count -eq 0) { throw 'Phase A backup 目錄不存在' }
    $backupDir = $backupDir[0].FullName
    $manifestPath = Join-Path $backupDir 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'manifest.json 不存在' }

    # 3) 安全注入 source_contract.source_row_counts（保留 Phase A 格式/tool/tool_version/files；key 與 restore_drill 契約一致）
    $mObj = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if (-not ($mObj.PSObject.Properties.Name -contains 'source_contract') -or -not $mObj.source_contract) {
        $mObj | Add-Member -NotePropertyName 'source_contract' -NotePropertyValue ([ordered]@{ post_restore_data_verified = 'DEFERRED_TO_PHASE_B' }) -Force
    }
    $countsObj = [ordered]@{}; foreach ($k in $rowCounts.Keys) { $countsObj[$k] = $rowCounts[$k] }
    $mObj.source_contract | Add-Member -NotePropertyName 'source_row_counts' -NotePropertyValue $countsObj -Force
    ($mObj | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    # 4) manifest/checksum 驗證（隔離 subprocess，輸出捕捉不外流；成功後必須繼續，不得提前 exit）
    $manifestCheck = if ($env:MANIFEST_CHECK_PATH) { $env:MANIFEST_CHECK_PATH } else { (Join-Path $PSScriptRoot 'task009_manifest_check.ps1') }
    [void](Invoke-Captured $script:pwshExe @('-NoProfile', '-File', $manifestCheck, '-BackupDir', $backupDir) 'manifest_check')
    Log 'manifest/checksum 驗證通過（subprocess），繼續加密流程'

    # 5) 打包 Phase A 產物（輸出捕捉不外流）
    $tarPath = Join-Path $script:runDir 'backup.tar'
    [void](Invoke-Captured 'tar' @('-cf', $tarPath, '-C', $backupDir, '.') 'tar')
    if (-not (Test-Path -LiteralPath $tarPath) -or (Get-Item -LiteralPath $tarPath).Length -le 0) { throw '打包失敗（tar 產物為空）' }

    # 6) age 公鑰加密（輸出捕捉不外流）
    $agePath = Join-Path $script:runDir 'backup.tar.age'
    [void](Invoke-Captured $age @('-r', $env:AGE_RECIPIENT, '-o', $agePath, $tarPath) 'age_encrypt')
    if (-not (Test-Path -LiteralPath $agePath -PathType Leaf) -or (Get-Item -LiteralPath $agePath).Length -le 0) { throw 'age 密文為空，拒絕上傳' }

    # 去敏 upload manifest 複本；刪除所有明文（dump 目錄 + tar）
    $uploadManifest = Join-Path $script:runDir 'manifest.json'
    Copy-Item -LiteralPath $manifestPath -Destination $uploadManifest -Force
    Remove-Item -LiteralPath $backupDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $tarPath -Force -ErrorAction SilentlyContinue

    $ageSize = (Get-Item -LiteralPath $agePath).Length
    $ageSha = (Get-FileHash -LiteralPath $agePath -Algorithm SHA256).Hash.ToLowerInvariant()
    $sumsPath = Join-Path $script:runDir 'SHA256SUMS'
    "$ageSha  backup.tar.age" | Set-Content -LiteralPath $sumsPath -Encoding ASCII

    # 7) 上傳私有 R2（密文附 sha256 object metadata；object key 僅固定 prefix+UTC+run id；輸出捕捉不外流）
    $keyBase = "$ObjectPrefix/$timestamp-$RunId"
    $env:AWS_ACCESS_KEY_ID = $env:R2_ACCESS_KEY_ID
    $env:AWS_SECRET_ACCESS_KEY = $env:R2_SECRET_ACCESS_KEY
    if (-not $env:AWS_DEFAULT_REGION) { $env:AWS_DEFAULT_REGION = 'auto' }
    $ageKey = "$keyBase/backup.tar.age"
    [void](Invoke-Captured $s3 @('s3', 'cp', $agePath, ("s3://{0}/{1}" -f $env:R2_BUCKET, $ageKey), '--endpoint-url', $env:R2_ENDPOINT, '--metadata', ("sha256={0}" -f $ageSha), '--only-show-errors') 's3_upload')
    foreach ($pair in @(@($uploadManifest, "$keyBase/manifest.json"), @($sumsPath, "$keyBase/SHA256SUMS"))) {
        [void](Invoke-Captured $s3 @('s3', 'cp', $pair[0], ("s3://{0}/{1}" -f $env:R2_BUCKET, $pair[1]), '--endpoint-url', $env:R2_ENDPOINT, '--only-show-errors') 's3_upload')
    }
    Log ("上傳完成（去敏；.age size={0} bytes, sha256={1}...）" -f $ageSize, $ageSha.Substring(0, 12))

    # 8) HEAD 驗證（不下載/解密）：size 一致 + metadata checksum 一致（HEAD 輸出捕捉不外流）
    $headJson = Invoke-Captured $s3 @('s3api', 'head-object', '--bucket', $env:R2_BUCKET, '--key', $ageKey, '--endpoint-url', $env:R2_ENDPOINT) 's3_head'
    $head = $null
    try { $head = ("$headJson") | ConvertFrom-Json } catch { throw 'HEAD 回傳無法解析' }
    $remoteLen = $null; try { $remoteLen = [int64] $head.ContentLength } catch { throw 'HEAD 無 ContentLength' }
    if ($remoteLen -ne $ageSize) { throw "HEAD size 不一致：remote=$remoteLen local=$ageSize" }
    $remoteSha = $null
    if ($head.PSObject.Properties.Name -contains 'Metadata' -and $head.Metadata) {
        if ($head.Metadata.PSObject.Properties.Name -contains 'sha256') { $remoteSha = [string]$head.Metadata.sha256 }
    }
    if (-not $remoteSha) { throw 'HEAD 缺少 sha256 metadata' }
    if ($remoteSha.ToLowerInvariant() -ne $ageSha) { throw 'HEAD metadata checksum 不一致' }
    Log 'HEAD size + metadata checksum 驗證通過'

    Log 'TASK009_REMOTE_BACKUP_OK'
}
catch {
    Write-Error ("TASK009_REMOTE_BACKUP_FAILED: {0}" -f $_.Exception.Message)
    exit 1
}
finally {
    if ($script:runDir) {
        try {
            Remove-RunDirSafe $script:runDir
            Log '清理完成（本 run 精確目錄已移除；越界一律拒刪）'
        }
        catch { Write-Warning ("清理略過（路徑驗證失敗，未刪除任何檔案）：{0}" -f $_.Exception.Message) }
    }
}
