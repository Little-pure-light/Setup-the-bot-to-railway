$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-True([bool] $cond, [string] $msg) {
    if (-not $cond) { throw "ASSERT FAILED: $msg" }
}

function New-TextFile([string] $path, [string] $text) {
    $dir = Split-Path -Parent $path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
    Set-Content -LiteralPath $path -Value $text -Encoding UTF8
}

function Snapshot-Tree([string] $root) {
    if (-not (Test-Path -LiteralPath $root)) { return @() }
    return @(
        Get-ChildItem -LiteralPath $root -Recurse -Force |
            Sort-Object FullName |
            ForEach-Object {
                $type = if ($_.PSIsContainer) { 'D' } else { 'F' }
                $len = if ($_.PSIsContainer) { 0 } else { $_.Length }
                "{0}|{1}|{2}" -f $type, $_.FullName.Substring($root.Length), $len
            }
    )
}

function Get-ValidBackups([string] $backupRoot, [string] $label) {
    return @(
        Get-ChildItem -LiteralPath $backupRoot -Directory |
            Where-Object { $_.Name -match ('^{0}_\d{{8}}_\d{{6}}(_\d{{3}})?$' -f [regex]::Escape($label)) } |
            Where-Object {
                $mPath = Join-Path $_.FullName 'manifest.json'
                if (-not (Test-Path -LiteralPath $mPath -PathType Leaf)) { return $false }
                try {
                    $m = Get-Content -LiteralPath $mPath -Raw | ConvertFrom-Json
                    return ($m.backup_state -eq 'completed' -and $m.dry_run -eq $false -and $m.label -eq $label)
                }
                catch {
                    return $false
                }
            }
    )
}

$pwshCmd = Get-Command pwsh -ErrorAction SilentlyContinue
$powershellCmd = Get-Command powershell -ErrorAction SilentlyContinue
if ($pwshCmd) {
    $Pwsh = $pwshCmd.Source
}
elseif ($powershellCmd) {
    $Pwsh = $powershellCmd.Source
}
else {
    throw 'No PowerShell executable found (pwsh/powershell).'
}
$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$BackupScript = Join-Path $RepoRoot 'scripts/backup/task009_backup.ps1'
$ManifestCheckScript = Join-Path $RepoRoot 'scripts/backup/task009_manifest_check.ps1'
$RestoreScript = Join-Path $RepoRoot 'scripts/backup/task009_restore_drill.ps1'

function Invoke-ChildPwsh([string] $scriptPath, [string[]] $scriptArgs, [hashtable] $envSet) {
    $saved = @{}
    foreach ($k in $envSet.Keys) {
        $saved[$k] = [Environment]::GetEnvironmentVariable($k)
        [Environment]::SetEnvironmentVariable($k, [string]$envSet[$k])
    }

    try {
        $stdoutFile = Join-Path ([System.IO.Path]::GetTempPath()) ("task009_ps_out_" + [guid]::NewGuid().ToString('N') + ".log")
        $stderrFile = Join-Path ([System.IO.Path]::GetTempPath()) ("task009_ps_err_" + [guid]::NewGuid().ToString('N') + ".log")
        try {
            $argList = @('-NoProfile', '-File', $scriptPath) + $scriptArgs
            $argString = @($argList | ForEach-Object { '"' + ([string]$_).Replace('"', '\"') + '"' }) -join ' '
            $p = Start-Process -FilePath $Pwsh -ArgumentList $argString -Wait -PassThru -NoNewWindow -RedirectStandardOutput $stdoutFile -RedirectStandardError $stderrFile
            $stdout = if (Test-Path -LiteralPath $stdoutFile) { Get-Content -LiteralPath $stdoutFile -Raw } else { '' }
            $stderr = if (Test-Path -LiteralPath $stderrFile) { Get-Content -LiteralPath $stderrFile -Raw } else { '' }
            return [pscustomobject]@{ ExitCode = $p.ExitCode; Output = (($stdout + "`n" + $stderr).Trim()) }
        }
        finally {
            if (Test-Path -LiteralPath $stdoutFile) { Remove-Item -LiteralPath $stdoutFile -Force }
            if (Test-Path -LiteralPath $stderrFile) { Remove-Item -LiteralPath $stderrFile -Force }
        }
    }
    finally {
        foreach ($k in $envSet.Keys) {
            [Environment]::SetEnvironmentVariable($k, $saved[$k])
        }
    }
}

function New-FakeTools([string] $toolsDir) {
    New-Item -ItemType Directory -Path $toolsDir | Out-Null

    $fakeDump = Join-Path $toolsDir 'fake_pg_dump.ps1'
    New-TextFile $fakeDump @'
param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Args)
$target = $null
foreach ($a in $Args) {
    if ($a -like '--file=*') { $target = $a.Substring(7) }
}
if (-not $target) {
    for ($i=0; $i -lt $Args.Count; $i++) {
        if ($Args[$i] -eq '--file' -and $i + 1 -lt $Args.Count) { $target = $Args[$i+1]; break }
    }
}
if (-not $target) { Write-Error 'missing --file'; exit 2 }
Set-Content -LiteralPath $target -Value 'DUMP-DATA' -Encoding UTF8
exit 0
'@

    $fakeRestore = Join-Path $toolsDir 'fake_pg_restore.ps1'
    New-TextFile $fakeRestore @'
param([Parameter(ValueFromRemainingArguments = $true)] [string[]]$Args)
if ($Args -contains '--list') {
  Write-Output '1; 0 0 DUMMY'
  Write-Output '2; 0 0 DUMMY'
  exit 0
}
exit 0
'@

    $fakePsql = Join-Path $toolsDir 'fake_psql.ps1'
    New-TextFile $fakePsql @'
param(
    [switch]$t,
    [switch]$A,
    [string]$v,
    [string]$c,
    [Parameter(ValueFromRemainingArguments = $true)] [string[]]$Rest
)
$q = [string]$c
if ($env:TASK009_FAKE_PSQL_MODE -eq 'fail_owner_cols' -and $q -match 'COUNT\(\*\) = 2') { Write-Output 'f'; exit 0 }
if ($env:TASK009_FAKE_PSQL_MODE -eq 'fail_embedding' -and $q -match "column_name='embedding'") { Write-Output 'f'; exit 0 }
if ($env:TASK009_FAKE_PSQL_MODE -eq 'fail_vector_ext' -and $q -match "extname='vector'") { Write-Output 'f'; exit 0 }
if ($env:TASK009_FAKE_PSQL_MODE -eq 'fail_row_count' -and $q -match 'COUNT\(\*\)::text FROM public\.xiaochenguang_memories') { Write-Output '999'; exit 0 }
if ($q -match 'to_regclass') { Write-Output 't'; exit 0 }
if ($q -match 'COUNT\(\*\) = 2') { Write-Output 't'; exit 0 }
if ($q -match "column_name='embedding'") { Write-Output 't'; exit 0 }
if ($q -match "extname='vector'") { Write-Output 't'; exit 0 }
if ($q -match 'COUNT\(\*\)::text FROM public\.xiaochenguang_memories') { Write-Output '1'; exit 0 }
if ($q -match 'COUNT\(\*\)::text FROM public\.emotional_states') { Write-Output '0'; exit 0 }
if ($q -match 'COUNT\(\*\)::text FROM public\.user_preferences') { Write-Output '0'; exit 0 }
if ($q -match 'COUNT\(\*\)::text FROM public\.xiaochenguang_reflections') { Write-Output '0'; exit 0 }
Write-Output 't'
exit 0
'@

    return [pscustomobject]@{
        Dump = $fakeDump
        Restore = $fakeRestore
        Psql = $fakePsql
    }
}

$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("task009_ps_tests_" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TempRoot | Out-Null

try {
    $tools = New-FakeTools -toolsDir (Join-Path $TempRoot 'tools')
    $backupRoot = Join-Path $TempRoot 'backups'
    New-Item -ItemType Directory -Path $backupRoot | Out-Null

    $commonEnv = @{
        'PGHOST' = 'isolated.db.local'
        'PGPORT' = '5432'
        'PGDATABASE' = 'xcg'
        'PGUSER' = 'tester'
        'PGPASSWORD' = 'dummy'
        'PG_DUMP_PATH' = $tools.Dump
        'PG_RESTORE_PATH' = $tools.Restore
        'PSQL_PATH' = $tools.Psql
    }

    # 1) Dry-run must be non-mutating
    $before = Snapshot-Tree $backupRoot
    $res = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '2', '-Label', 'task009safe', '-DryRun') $commonEnv
    Assert-True ($res.ExitCode -eq 0) ("dry-run should succeed. output=" + $res.Output)
    $after = Snapshot-Tree $backupRoot
    $treeDiff = @(Compare-Object @($before) @($after))
    Assert-True ($treeDiff.Count -eq 0) 'dry-run must not mutate filesystem'

    # 2) Retention exact + ignore unrelated/incomplete + same-second collision safe
    New-Item -ItemType Directory -Path (Join-Path $backupRoot 'unrelated_dir') | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $backupRoot 'task009safe_20000101_000000') | Out-Null
    $r1 = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '2', '-Label', 'task009safe', '-TimestampOverride', '20260802_120000') $commonEnv
    Assert-True ($r1.ExitCode -eq 0) 'backup run #1 should succeed'
    $r2 = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '2', '-Label', 'task009safe', '-TimestampOverride', '20260802_120000') $commonEnv
    Assert-True ($r2.ExitCode -eq 0) 'backup run #2 should succeed with collision suffix'
    $r3 = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '2', '-Label', 'task009safe', '-TimestampOverride', '20260802_120100') $commonEnv
    Assert-True ($r3.ExitCode -eq 0) 'backup run #3 should succeed and trigger retention'

    $validNow = Get-ValidBackups -backupRoot $backupRoot -label 'task009safe'
    Assert-True ($validNow.Count -eq 2) 'retention should keep exactly 2 valid backups'
    Assert-True (Test-Path -LiteralPath (Join-Path $backupRoot 'unrelated_dir')) 'retention must not delete unrelated directory'
    Assert-True (Test-Path -LiteralPath (Join-Path $backupRoot 'task009safe_20000101_000000')) 'retention must ignore incomplete backup folder'

    # 3) Retention count <1 must fail
    $rBadRet = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '0', '-Label', 'task009safe') $commonEnv
    Assert-True ($rBadRet.ExitCode -ne 0) 'RetentionCount < 1 should fail'

    # 3b) Invalid schema and metadata should fail closed without filesystem mutation
    $beforeInvalidSchema = Snapshot-Tree $backupRoot
    $rInvalidSchema = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '2', '-Label', 'task009safe', '-Schemas', 'public', 'bad/schema') $commonEnv
    Assert-True ($rInvalidSchema.ExitCode -ne 0) 'invalid schema input must fail'
    $afterInvalidSchema = Snapshot-Tree $backupRoot
    Assert-True (@(Compare-Object @($beforeInvalidSchema) @($afterInvalidSchema)).Count -eq 0) 'invalid schema must not mutate filesystem'

    $beforeInvalidMeta = Snapshot-Tree $backupRoot
    $rInvalidMeta = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '2', '-Label', 'task009safe', '-EnvironmentLabel', 'prod/main') $commonEnv
    Assert-True ($rInvalidMeta.ExitCode -ne 0) 'invalid environment label must fail'
    $afterInvalidMeta = Snapshot-Tree $backupRoot
    Assert-True (@(Compare-Object @($beforeInvalidMeta) @($afterInvalidMeta)).Count -eq 0) 'invalid metadata must not mutate filesystem'

    # Prepare a valid backup dir for manifest/restore checks
    $validDir = $validNow | Sort-Object Name -Descending | Select-Object -First 1
    $validDirPath = $validDir.FullName

    # 4) Manifest pass
    $mPass = Invoke-ChildPwsh $ManifestCheckScript @('-BackupDir', $validDirPath) @{}
    Assert-True ($mPass.ExitCode -eq 0) 'manifest check should pass for valid backup'

    # 5) Manifest tamper fail
    $manifestPath = Join-Path $validDirPath 'manifest.json'
    $manifestObj = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    $firstFile = $manifestObj.files[0].name
    Add-Content -LiteralPath (Join-Path $validDirPath $firstFile) -Value 'tamper'
    $mTamper = Invoke-ChildPwsh $ManifestCheckScript @('-BackupDir', $validDirPath) @{}
    Assert-True ($mTamper.ExitCode -ne 0) 'manifest check must fail on tampered file'

    # restore tampered file for next tests by re-running backup once
    $rFix = Invoke-ChildPwsh $BackupScript @('-BackupRoot', $backupRoot, '-RetentionCount', '2', '-Label', 'task009safe', '-TimestampOverride', '20260802_120200') $commonEnv
    Assert-True ($rFix.ExitCode -eq 0) 'backup run to restore valid fixture should succeed'
    $validNow = Get-ValidBackups -backupRoot $backupRoot -label 'task009safe'
    $validDirPath = ($validNow | Sort-Object Name -Descending | Select-Object -First 1).FullName

    # 6) Manifest path traversal fail
    $trvDir = Join-Path $TempRoot 'traversal_case'
    New-Item -ItemType Directory -Path $trvDir | Out-Null
    New-TextFile (Join-Path $trvDir 'ok.dump') 'data'
    $trv = [ordered]@{
        backup_state = 'completed'
        label = 'task009safe'
        dry_run = $false
        files = @(
            @{ name = '../escape.dump'; size_bytes = 4; sha256 = ('0' * 64) },
            @{ name = 'ok.dump'; size_bytes = 4; sha256 = ((Get-FileHash -LiteralPath (Join-Path $trvDir 'ok.dump') -Algorithm SHA256).Hash) }
        )
    }
    ($trv | ConvertTo-Json -Depth 5) | Set-Content -LiteralPath (Join-Path $trvDir 'manifest.json') -Encoding UTF8
    $mTrv = Invoke-ChildPwsh $ManifestCheckScript @('-BackupDir', $trvDir) @{}
    Assert-True ($mTrv.ExitCode -ne 0) 'manifest check must fail on path traversal'

    $restoreBaseEnv = @{
        'RESTORE_ALLOW_ISOLATED' = '1'
        'RESTORE_PGHOST' = 'localhost'
        'RESTORE_PGPORT' = '5432'
        'RESTORE_PGDATABASE' = 'restore_db'
        'RESTORE_PGUSER' = 'tester'
        'RESTORE_PGPASSWORD' = 'dummy'
        'PG_RESTORE_PATH' = $tools.Restore
        'PSQL_PATH' = $tools.Psql
    }

    # 7) Restore missing authorization fail
    $noAuthEnv = @{} + $restoreBaseEnv
    $noAuthEnv.Remove('RESTORE_ALLOW_ISOLATED')
    $rrNoAuth = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated') $noAuthEnv
    Assert-True ($rrNoAuth.ExitCode -ne 0) 'restore must fail without RESTORE_ALLOW_ISOLATED=1'

    # 8) Restore source=target fail
    $sameEnv = @{} + $restoreBaseEnv
    $sameEnv['PGHOST'] = 'localhost'
    $sameEnv['PGPORT'] = '5432'
    $sameEnv['PGDATABASE'] = 'restore_db'
    $rrSame = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated') $sameEnv
    Assert-True ($rrSame.ExitCode -ne 0) 'restore must fail when source identity equals target'

    # 9) Restore supabase direct/pooler host fail
    $supaDirEnv = @{} + $restoreBaseEnv
    $supaDirEnv['RESTORE_PGHOST'] = 'db.abcd.supabase.co'
    $rrSupaCo = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated') $supaDirEnv
    Assert-True ($rrSupaCo.ExitCode -ne 0) 'restore must fail for supabase.co host'

    $supaPoolEnv = @{} + $restoreBaseEnv
    $supaPoolEnv['RESTORE_PGHOST'] = 'aws-0-ap-northeast-2.pooler.supabase.com'
    $rrSupaPool = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated') $supaPoolEnv
    Assert-True ($rrSupaPool.ExitCode -ne 0) 'restore must fail for pooler.supabase.com host'

    # 10) Non-dry-run missing dump must fail (no downgrade to dry-run success)
    $missingDumpDir = Join-Path $TempRoot 'missing_dump_case'
    New-Item -ItemType Directory -Path $missingDumpDir | Out-Null
    $missingManifest = [ordered]@{
        backup_state = 'completed'
        label = 'task009safe'
        dry_run = $false
        files = @()
    }
    ($missingManifest | ConvertTo-Json -Depth 4) | Set-Content -LiteralPath (Join-Path $missingDumpDir 'manifest.json') -Encoding UTF8
    $rrMissing = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $missingDumpDir, '-ConfirmIsolated', '-DryRun', '0') $restoreBaseEnv
    Assert-True ($rrMissing.ExitCode -ne 0) 'non-dry-run must fail when dump files are missing'

    # 11) Positive restore dry-run should succeed with explicit marker
    $rrDryRunPass = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated') $restoreBaseEnv
    Assert-True ($rrDryRunPass.ExitCode -eq 0) 'restore dry-run should succeed for valid backup'
    Assert-True ($rrDryRunPass.Output -match 'TASK009_RESTORE_DRILL_DRYRUN_OK') 'dry-run success marker must exist'

    # 12) Positive non-dry-run with fake tools should execute full flow
    $manifestRaw = Get-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Raw | ConvertFrom-Json
    if (-not $manifestRaw.source_contract) {
        $manifestRaw | Add-Member -MemberType NoteProperty -Name source_contract -Value ([ordered]@{})
    }
    $manifestRaw.source_contract.source_row_counts = [ordered]@{
        'public.xiaochenguang_memories' = 1
        'public.xiaochenguang_reflections' = 0
        'public.emotional_states' = 0
        'public.user_preferences' = 0
    }
    ($manifestRaw | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Encoding UTF8

    $rrRealPass = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated', '-DryRun', '0') $restoreBaseEnv
    Assert-True ($rrRealPass.ExitCode -eq 0) ('non-dry-run restore should pass with valid fixture and fake tools. output=' + $rrRealPass.Output)
    Assert-True ($rrRealPass.Output -match 'TASK009_RESTORE_DRILL_OK') 'non-dry-run success marker must exist'

    # 13) Post-contract failure must fail
    $contractFailEnv = @{} + $restoreBaseEnv
    $contractFailEnv['TASK009_FAKE_PSQL_MODE'] = 'fail_vector_ext'
    $rrContractFail = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated', '-DryRun', '0') $contractFailEnv
    Assert-True ($rrContractFail.ExitCode -ne 0) 'restore must fail when post-contract check fails'

    # 14) source count mismatch must fail
    $countMismatchEnv = @{} + $restoreBaseEnv
    $countMismatchEnv['TASK009_FAKE_PSQL_MODE'] = 'fail_row_count'
    $rrCountMismatch = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated', '-DryRun', '0') $countMismatchEnv
    Assert-True ($rrCountMismatch.ExitCode -ne 0) 'restore must fail when source_row_counts mismatch'

    # 15) unknown source_row_counts key must fail
    $manifestUnknown = Get-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Raw | ConvertFrom-Json
    $manifestUnknown.source_contract.source_row_counts = [ordered]@{
        'public.xiaochenguang_memories' = 1
        'public.xiaochenguang_reflections' = 0
        'public.emotional_states' = 0
        'public.user_preferences' = 0
        'public.unknown_table' = 123
    }
    ($manifestUnknown | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Encoding UTF8
    $rrUnknownKey = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated', '-DryRun', '0') $restoreBaseEnv
    Assert-True ($rrUnknownKey.ExitCode -ne 0) 'restore must fail on unknown source_row_counts key'

    # 16) malicious source_row_counts key must fail and never be executed as SQL structure
    $manifestMal = Get-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Raw | ConvertFrom-Json
    $manifestMal.source_contract.source_row_counts = [ordered]@{
        'public.xiaochenguang_memories' = 1
        'public.xiaochenguang_reflections' = 0
        'public.emotional_states' = 0
        'public.user_preferences' = 0
        'public.xiaochenguang_memories;DROP TABLE public.user_preferences;--' = 1
    }
    ($manifestMal | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Encoding UTF8
    $rrMalKey = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated', '-DryRun', '0') $restoreBaseEnv
    Assert-True ($rrMalKey.ExitCode -ne 0) 'restore must fail on malicious source_row_counts key'

    # 17) missing required source_row_counts key must fail
    $manifestMissing = Get-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Raw | ConvertFrom-Json
    $manifestMissing.source_contract.source_row_counts = [ordered]@{
        'public.xiaochenguang_memories' = 1
        'public.emotional_states' = 0
    }
    ($manifestMissing | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath (Join-Path $validDirPath 'manifest.json') -Encoding UTF8
    $rrMissingKey = Invoke-ChildPwsh $RestoreScript @('-BackupDir', $validDirPath, '-ConfirmIsolated', '-DryRun', '0') $restoreBaseEnv
    Assert-True ($rrMissingKey.ExitCode -ne 0) 'restore must fail when required source_row_counts key is missing'

    Write-Host 'TASK009_POWERSHELL_SAFETY_TESTS_PASS'
}
finally {
    if (Test-Path -LiteralPath $TempRoot) {
        Remove-Item -LiteralPath $TempRoot -Recurse -Force
    }
}
