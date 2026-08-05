# Task009-006 remote backup pipeline safety tests (deterministic; fake tools; no real connections/uploads).
# Reuses the REAL task009_backup.ps1 + REAL task009_manifest_check.ps1 (Phase A contract) with fake
# pg_dump/pg_restore/psql/age/aws. Covers: fixed 4-table set (subset/unknown/duplicate fail-closed),
# real manifest tamper + real dump corruption caught by the REAL checker, desensitized external output,
# and cleanup out-of-bounds safety (sibling + files outside runner temp are never deleted).
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Assert-True([bool] $c, [string] $m) { if (-not $c) { throw "ASSERT FAILED: $m" } }

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$Script = Join-Path $RepoRoot 'scripts/backup/task009_remote_backup.ps1'
$BackupScript = Join-Path $RepoRoot 'scripts/backup/task009_backup.ps1'
$ManifestCheckScript = Join-Path $RepoRoot 'scripts/backup/task009_manifest_check.ps1'
$pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $pwsh) { $pwsh = Get-Command powershell -ErrorAction SilentlyContinue }
if (-not $pwsh) { throw 'No PowerShell executable found.' }

function Write-Fakes([string] $dir) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Set-Content -LiteralPath (Join-Path $dir 'fake_pg_dump.ps1') -Encoding UTF8 -Value @'
$file = $args | Where-Object { $_ -like '--file=*' } | Select-Object -First 1
if ($file) { ($file -replace '^--file=','') | ForEach-Object { Set-Content -LiteralPath $_ -Value ("FAKEDUMP " + [guid]::NewGuid()) -Encoding ASCII } }
if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }
exit 0
'@
    Set-Content -LiteralPath (Join-Path $dir 'fake_pg_restore.ps1') -Encoding UTF8 -Value @'
# emulate --list output (entry lines)
Write-Output "; Archive created"; Write-Output "1; 0 0 TABLE public foo owner"
exit 0
'@
    Set-Content -LiteralPath (Join-Path $dir 'fake_psql.ps1') -Encoding UTF8 -Value @'
if ($env:FAKE_QUERY_LOG) { ($args -join ' ') | Add-Content -LiteralPath $env:FAKE_QUERY_LOG }
if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }
$c = if ($env:FAKE_PSQL_COUNT) { $env:FAKE_PSQL_COUNT } else { '42' }
Write-Output $c
exit 0
'@
    Set-Content -LiteralPath (Join-Path $dir 'fake_age.ps1') -Encoding UTF8 -Value @'
$mode = if ($env:FAKE_AGE_MODE) { $env:FAKE_AGE_MODE } else { 'ok' }
$out = $null; for ($i=0;$i -lt $args.Count;$i++){ if ($args[$i] -eq '-o'){ $out=$args[$i+1] } }
if ($mode -eq 'fail') { if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }; [Console]::Error.WriteLine('age boom'); exit 1 }
if ($out) { if ($mode -eq 'empty') { Set-Content -LiteralPath $out -Value '' -NoNewline -Encoding ASCII } else { Set-Content -LiteralPath $out -Value ('AGE-ENC ' + [guid]::NewGuid()) -Encoding ASCII } }
exit 0
'@
    Set-Content -LiteralPath (Join-Path $dir 'fake_aws.ps1') -Encoding UTF8 -Value @'
$mode = if ($env:FAKE_S3_MODE) { $env:FAKE_S3_MODE } else { 'ok' }
if ($args[0] -eq 's3' -and $args[1] -eq 'cp') {
  $src = $args[2]; $dst = $args[3]
  $meta = $null; for ($i=0;$i -lt $args.Count;$i++){ if ($args[$i] -eq '--metadata'){ $meta=$args[$i+1] } }
  if ($env:FAKE_S3_KEYS) { $dst | Add-Content -LiteralPath $env:FAKE_S3_KEYS }
  if ($dst -like '*backup.tar.age') {
    if ($env:FAKE_S3_STATE) { (Get-Item -LiteralPath $src).Length | Set-Content -LiteralPath $env:FAKE_S3_STATE }
    if ($meta -and $meta -like 'sha256=*' -and $env:FAKE_S3_META) { ($meta -replace '^sha256=','') | Set-Content -LiteralPath $env:FAKE_S3_META }
  }
  if ($mode -eq 'upload_fail') { if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }; [Console]::Error.WriteLine('upload boom'); exit 1 }
  exit 0
}
if ($args[0] -eq 's3api' -and $args[1] -eq 'head-object') {
  if ($env:FAKE_S3_HEADLOG) { 'head' | Add-Content -LiteralPath $env:FAKE_S3_HEADLOG }
  if ($mode -eq 'head_missing') { if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }; [Console]::Error.WriteLine('404'); exit 1 }
  $len = 123; if ($env:FAKE_S3_STATE -and (Test-Path -LiteralPath $env:FAKE_S3_STATE)) { $len = [int](Get-Content -LiteralPath $env:FAKE_S3_STATE -Raw) }
  if ($mode -eq 'head_mismatch') { $len = $len + 1 }
  $sha = 'deadbeef'; if ($env:FAKE_S3_META -and (Test-Path -LiteralPath $env:FAKE_S3_META)) { $sha = (Get-Content -LiteralPath $env:FAKE_S3_META -Raw).Trim() }
  if ($mode -eq 'head_checksum_mismatch') { $sha = 'ffffffffffffffff' }
  Write-Output ('{"ContentLength": ' + $len + ', "Metadata": {"sha256": "' + $sha + '"}}')
  exit 0
}
exit 0
'@
    return @{
        pg = (Join-Path $dir 'fake_pg_dump.ps1'); pgr = (Join-Path $dir 'fake_pg_restore.ps1')
        psql = (Join-Path $dir 'fake_psql.ps1'); age = (Join-Path $dir 'fake_age.ps1'); aws = (Join-Path $dir 'fake_aws.ps1')
    }
}

function Set-EnvSet([hashtable] $envSet) {
    $saved = @{}
    foreach ($k in $envSet.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, [string]$envSet[$k]) }
    return $saved
}
function Restore-EnvSet([hashtable] $saved) { foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) } }

# Run a script; return only exit code (output inherited to console).
function Run-Script([string] $scriptPath, [hashtable] $envSet, [string[]] $argList) {
    $saved = Set-EnvSet $envSet
    try {
        $p = Start-Process -FilePath $pwsh.Source -ArgumentList (@('-NoProfile','-File',$scriptPath) + $argList) -Wait -PassThru -NoNewWindow
        return $p.ExitCode
    } finally { Restore-EnvSet $saved }
}

# Run a script capturing BOTH stdout and stderr; return @{ ExitCode; Output }.
function Run-Capture([string] $scriptPath, [hashtable] $envSet, [string[]] $argList) {
    $saved = Set-EnvSet $envSet
    $o = [System.IO.Path]::GetTempFileName(); $e = [System.IO.Path]::GetTempFileName()
    try {
        $p = Start-Process -FilePath $pwsh.Source -ArgumentList (@('-NoProfile','-File',$scriptPath) + $argList) -Wait -PassThru -NoNewWindow -RedirectStandardOutput $o -RedirectStandardError $e
        $out = ''
        if (Test-Path -LiteralPath $o) { $out += (Get-Content -LiteralPath $o -Raw) }
        if (Test-Path -LiteralPath $e) { $out += "`n" + (Get-Content -LiteralPath $e -Raw) }
        return @{ ExitCode = $p.ExitCode; Output = [string]$out }
    } finally { Restore-EnvSet $saved; Remove-Item -LiteralPath $o,$e -Force -ErrorAction SilentlyContinue }
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('t009_006_' + [guid]::NewGuid().ToString('N').Substring(0,8))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$fakes = Write-Fakes (Join-Path $tmp 'bin')
$runnerTemp = Join-Path $tmp 'runner'; New-Item -ItemType Directory -Force -Path $runnerTemp | Out-Null
$keys = Join-Path $tmp 'keys.txt'; $qlog = Join-Path $tmp 'q.txt'; $headlog = Join-Path $tmp 'head.txt'

function Base-Env() {
    return @{
        RUNNER_TEMP = $runnerTemp
        PG_DUMP_PATH=$fakes.pg; PG_RESTORE_PATH=$fakes.pgr; PSQL_PATH=$fakes.psql; AGE_PATH=$fakes.age; S3_CLIENT_PATH=$fakes.aws
        PGHOST='h'; PGDATABASE='d'; PGUSER='u'; PGPASSWORD='p'
        AGE_RECIPIENT='age1fakerecipient'; R2_BUCKET='b'; R2_ENDPOINT='https://example.invalid'; R2_ACCESS_KEY_ID='k'; R2_SECRET_ACCESS_KEY='s'
        FAKE_PSQL_COUNT='42'; FAKE_AGE_MODE='ok'; FAKE_S3_MODE='ok'
        FAKE_S3_KEYS=$keys; FAKE_S3_STATE=(Join-Path $tmp 'size.txt'); FAKE_S3_META=(Join-Path $tmp 'meta.txt'); FAKE_S3_HEADLOG=$headlog
        FAKE_QUERY_LOG=$qlog; MANIFEST_CHECK_PATH=''; TASK009_ROWCOUNT_SET_OVERRIDE=''; FAKE_SENSITIVE=''
    }
}
$args0 = @('-WorkRoot',$runnerTemp,'-RunId','test')
$RequiredTables = @('public.xiaochenguang_memories','public.xiaochenguang_reflections','public.emotional_states','public.user_preferences')
function Reset() { Remove-Item -LiteralPath $keys,$qlog,$headlog -ErrorAction SilentlyContinue }
function Run-Backup([hashtable] $e, [string[]] $a) { return (Run-Script $Script $e $a) }

try {
    # 1) positive full pipeline (real backup.ps1 + real manifest_check + fakes)
    Reset
    $sibling = Join-Path $runnerTemp 'keep_me_dir'; New-Item -ItemType Directory -Force -Path $sibling | Out-Null
    Set-Content -LiteralPath (Join-Path $sibling 'x') -Value 'keep'
    $outsideSentinel = Join-Path $tmp 'OUTSIDE_RUNNER_TEMP.txt'; Set-Content -LiteralPath $outsideSentinel -Value 'must survive'
    $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH')
    $rc = Run-Backup $e $args0
    Assert-True ($rc -eq 0) "positive should exit 0 (got $rc)"
    $k = Get-Content -LiteralPath $keys -ErrorAction SilentlyContinue
    Assert-True (($k | Where-Object { $_ -like '*backup.tar.age' }).Count -ge 1) 'must upload .age (upload executed)'
    Assert-True (($k | Where-Object { $_ -like '*/manifest.json' }).Count -ge 1) 'must upload manifest'
    Assert-True (($k | Where-Object { $_ -like '*.dump' -or $_ -like '*backup.tar' }).Count -eq 0) 'must NOT upload plaintext'
    Assert-True ((Test-Path -LiteralPath $headlog) -and ((Get-Content -LiteralPath $headlog).Count -ge 1)) 'HEAD must be executed'
    $q = Get-Content -LiteralPath $qlog -Raw
    foreach ($a in $RequiredTables) { Assert-True ($q -like "*$a*") "row-count must query $a" }
    Assert-True (Test-Path -LiteralPath $sibling) 'precise cleanup must NOT delete sibling dir'
    Assert-True (Test-Path -LiteralPath $outsideSentinel) 'cleanup must NOT delete files outside runner temp'
    Assert-True ((@(Get-ChildItem -LiteralPath $runnerTemp -Directory -Filter 't009_remote_*')).Count -eq 0) 'run dir must be cleaned up'
    Write-Host 'OK positive: reuse Phase A, upload+HEAD executed, no plaintext, precise cleanup, external file safe'

    # 2) dry-run: no connection/upload
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $rc = Run-Backup $e ($args0 + '-DryRun')
    Assert-True ($rc -eq 0) 'dry-run exit 0'
    Assert-True (-not (Test-Path -LiteralPath $keys)) 'dry-run no upload'
    Assert-True (-not (Test-Path -LiteralPath $qlog)) 'dry-run no query'
    Write-Host 'OK dry-run zero connection/write'

    # 3) fixed 4-table set: subset / unknown / duplicate must fail BEFORE any query (via test-only override seam)
    foreach ($case in @(
        @{ name='subset';    val='public.user_preferences' },
        @{ name='unknown';   val=($RequiredTables -join ',') + ',public.evil_table' },
        @{ name='duplicate'; val=($RequiredTables -join ',') + ',public.user_preferences' }
    )) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.TASK009_ROWCOUNT_SET_OVERRIDE=$case.val
        $rc = Run-Backup $e $args0
        Assert-True ($rc -ne 0) ("row-count set {0} must fail" -f $case.name)
        Assert-True (-not (Test-Path -LiteralPath $qlog)) ("row-count set {0} must fail before any psql query" -f $case.name)
        Write-Host ("OK fixed-set {0} pre-query fail" -f $case.name)
    }

    # 4) non-integer row count
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_PSQL_COUNT='NaN'; $rc = Run-Backup $e $args0
    Assert-True ($rc -ne 0) 'non-integer count should fail'; Write-Host 'OK non-integer count fail'

    # 5) manifest_check failure -> abort before upload (seam)
    Reset; $fail = Join-Path $tmp 'fail_check.ps1'; Set-Content -LiteralPath $fail -Value 'exit 1' -Encoding UTF8
    $e = Base-Env; $e.MANIFEST_CHECK_PATH=$fail; $rc = Run-Backup $e $args0
    Assert-True ($rc -ne 0) 'manifest_check failure should fail'
    Assert-True (-not (Test-Path -LiteralPath $keys)) 'no upload when manifest verification fails'
    Write-Host 'OK manifest-verify-failure aborts before upload'

    # 6) age failure / 7) empty ciphertext
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_AGE_MODE='fail'; $rc = Run-Backup $e $args0
    Assert-True ($rc -ne 0) 'age failure fail'; Assert-True (-not (Test-Path -LiteralPath $keys)) 'no upload on age failure'; Write-Host 'OK age-failure'
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_AGE_MODE='empty'; $rc = Run-Backup $e $args0
    Assert-True ($rc -ne 0) 'empty ciphertext fail'; Write-Host 'OK empty-ciphertext'

    # 8) upload failure / HEAD missing / HEAD size mismatch / HEAD checksum mismatch
    foreach ($m in @('upload_fail','head_missing','head_mismatch','head_checksum_mismatch')) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_S3_MODE=$m; $rc = Run-Backup $e $args0
        Assert-True ($rc -ne 0) "$m should fail"; Write-Host "OK $m fail"
    }

    # 9) unsafe WorkRoot
    $bad = Join-Path ([System.IO.Path]::GetTempPath()) ('outside_' + [guid]::NewGuid().ToString('N').Substring(0,6)); New-Item -ItemType Directory -Force -Path $bad | Out-Null
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $rc = Run-Backup $e @('-WorkRoot',$bad,'-RunId','test')
    Assert-True ($rc -ne 0) 'unsafe WorkRoot should fail'; Write-Host 'OK unsafe-temp-path fail'

    # 10) DESENSITIZATION: fake tools emit a sensitive marker on stderr; orchestrator output must NEVER contain it.
    $marker = 'SENSITIVE_MARKER_db-host_9f3a2b1c'
    foreach ($case in @(
        @{ name='age_fail';      env=@{ FAKE_AGE_MODE='fail' } },
        @{ name='s3_upload_fail';env=@{ FAKE_S3_MODE='upload_fail' } },
        @{ name='s3_head_missing';env=@{ FAKE_S3_MODE='head_missing' } }
    )) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_SENSITIVE=$marker
        foreach ($kk in $case.env.Keys) { $e[$kk] = $case.env[$kk] }
        $r = Run-Capture $Script $e $args0
        Assert-True ($r.ExitCode -ne 0) ("desensitization case {0} should fail" -f $case.name)
        Assert-True (-not ($r.Output -like "*$marker*")) ("desensitization: marker must be absent from output ({0})" -f $case.name)
        Write-Host ("OK desensitization {0}: sensitive stderr not leaked" -f $case.name)
    }
    # also prove positive-path psql stderr marker is not leaked
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_SENSITIVE=$marker
    $r = Run-Capture $Script $e $args0
    Assert-True ($r.ExitCode -eq 0) 'positive with sensitive-marker tools should still succeed'
    Assert-True (-not ($r.Output -like "*$marker*")) 'desensitization: positive-path tool stderr must not leak'
    Write-Host 'OK desensitization positive: tool stderr captured, not leaked'

    # 11) REAL Phase A artifacts + REAL manifest_check: untouched PASS, manifest tamper FAIL, dump corruption FAIL
    $realEnv = @{ PG_DUMP_PATH=$fakes.pg; PG_RESTORE_PATH=$fakes.pgr; PGHOST='h'; PGDATABASE='d'; PGUSER='u'; PGPASSWORD='p' }
    function New-RealBackupDir([string] $label) {
        $root = Join-Path $runnerTemp ('real_' + [guid]::NewGuid().ToString('N').Substring(0,8)); New-Item -ItemType Directory -Force -Path $root | Out-Null
        $rc = Run-Script $BackupScript $realEnv @('-BackupRoot',$root,'-Label',$label,'-RetentionCount','9999','-Schemas','public','-EnvironmentLabel','production')
        Assert-True ($rc -eq 0) "real backup.ps1 should produce artifacts (exit $rc)"
        $dir = @(Get-ChildItem -LiteralPath $root -Directory -Filter ("{0}_*" -f $label) | Select-Object -First 1)
        Assert-True ($dir.Count -ge 1) 'real backup dir must exist'
        return $dir[0].FullName
    }
    # (a) untouched -> real checker PASS (sanity that the checker accepts genuine artifacts)
    $bd = New-RealBackupDir 'task009'
    $rc = Run-Script $ManifestCheckScript @{} @('-BackupDir',$bd)
    Assert-True ($rc -eq 0) "real checker must PASS on untouched real artifacts (exit $rc)"
    Write-Host 'OK real-checker PASS on genuine artifacts'
    # (b) tamper manifest (flip a recorded sha256) -> real checker FAIL
    $bd2 = New-RealBackupDir 'task009'
    $mp = Join-Path $bd2 'manifest.json'
    $mo = Get-Content -LiteralPath $mp -Raw | ConvertFrom-Json
    $mo.files[0].sha256 = ('0' * 64)
    ($mo | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $mp -Encoding UTF8
    $rc = Run-Script $ManifestCheckScript @{} @('-BackupDir',$bd2)
    Assert-True ($rc -ne 0) 'real checker must FAIL on tampered manifest sha256'
    Write-Host 'OK real-checker FAIL on manifest tamper'
    # (c) corrupt a real dump file (append bytes) -> real checker FAIL (size/hash mismatch)
    $bd3 = New-RealBackupDir 'task009'
    $dump = @(Get-ChildItem -LiteralPath $bd3 -Filter 'schema_*.dump' | Select-Object -First 1)[0].FullName
    Add-Content -LiteralPath $dump -Value 'CORRUPTION' -Encoding ASCII
    $rc = Run-Script $ManifestCheckScript @{} @('-BackupDir',$bd3)
    Assert-True ($rc -ne 0) 'real checker must FAIL on corrupted dump bytes'
    Write-Host 'OK real-checker FAIL on dump corruption'

    Write-Host ''
    Write-Host 'TASK009_REMOTE_BACKUP_TESTS_PASS'
}
finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
