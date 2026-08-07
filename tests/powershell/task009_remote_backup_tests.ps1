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
if ($args | Where-Object { $_ -eq '--version' }) {
  $v = if ($env:FAKE_PGDUMP_VERSION) { $env:FAKE_PGDUMP_VERSION } else { '16.14' }
  Write-Output ("pg_dump (PostgreSQL) " + $v)
  exit 0
}
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
$joined = ($args -join ' ')
if ($env:FAKE_QUERY_LOG) { $joined | Add-Content -LiteralPath $env:FAKE_QUERY_LOG }
# version preflight query: return server_version_num (not the row count)
if ($joined -match 'server_version_num') {
  if ($env:FAKE_SVQ_STDERR) { [Console]::Error.WriteLine($env:FAKE_SVQ_STDERR) }
  $sv = if ($env:FAKE_SVQ_EXIT) { [int]$env:FAKE_SVQ_EXIT } else { 0 }
  if ($sv -ne 0) { exit $sv }
  $num = if ($null -ne $env:FAKE_SERVER_VERSION_NUM) { $env:FAKE_SERVER_VERSION_NUM } else { '160014' }
  Write-Output $num
  exit 0
}
if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }
if ($env:FAKE_PSQL_STDERR) { [Console]::Error.WriteLine($env:FAKE_PSQL_STDERR) }
$exit = if ($env:FAKE_PSQL_EXIT) { [int]$env:FAKE_PSQL_EXIT } else { 0 }
if ($exit -ne 0) { exit $exit }
$c = if ($env:FAKE_PSQL_COUNT) { $env:FAKE_PSQL_COUNT } else { '42' }
Write-Output $c
exit 0
'@
    Set-Content -LiteralPath (Join-Path $dir 'fake_age.ps1') -Encoding UTF8 -Value @'
$mode = if ($env:FAKE_AGE_MODE) { $env:FAKE_AGE_MODE } else { 'ok' }
$out = $null; for ($i=0;$i -lt $args.Count;$i++){ if ($args[$i] -eq '-o'){ $out=$args[$i+1] } }
if ($mode -eq 'fail') { if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }; if ($env:FAKE_AGE_STDERR) { [Console]::Error.WriteLine($env:FAKE_AGE_STDERR) } else { [Console]::Error.WriteLine('age boom') }; exit 1 }
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
  if ($mode -eq 'upload_fail') { if ($env:FAKE_SENSITIVE) { [Console]::Error.WriteLine($env:FAKE_SENSITIVE) }; if ($env:FAKE_S3_STDERR) { [Console]::Error.WriteLine($env:FAKE_S3_STDERR) } else { [Console]::Error.WriteLine('upload boom') }; $xc = if ($env:FAKE_S3_EXIT) { [int]$env:FAKE_S3_EXIT } else { 1 }; exit $xc }
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
        AGE_RECIPIENT='age1fakerecipient'; R2_BUCKET='ci-test-bucket'; R2_ENDPOINT='https://example.invalid'; R2_ACCESS_KEY_ID='k'; R2_SECRET_ACCESS_KEY='s'
        FAKE_PSQL_COUNT='42'; FAKE_AGE_MODE='ok'; FAKE_S3_MODE='ok'
        FAKE_S3_KEYS=$keys; FAKE_S3_STATE=(Join-Path $tmp 'size.txt'); FAKE_S3_META=(Join-Path $tmp 'meta.txt'); FAKE_S3_HEADLOG=$headlog
        FAKE_QUERY_LOG=$qlog; MANIFEST_CHECK_PATH=''; TASK009_ROWCOUNT_SET_OVERRIDE=''; FAKE_SENSITIVE=''
        FAKE_PSQL_STDERR=''; FAKE_PSQL_EXIT=''
        FAKE_SERVER_VERSION_NUM='160014'; FAKE_PGDUMP_VERSION='16.14'; FAKE_SVQ_EXIT=''; FAKE_SVQ_STDERR=''
        TASK009_PHASEA_BACKUP_PATH=''; FAKE_AGE_STDERR=''; FAKE_S3_STDERR=''; FAKE_S3_EXIT=''
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
    Assert-True (@($k | Where-Object { $_ -like '*backup.tar.age' }).Count -ge 1) 'must upload .age (upload executed)'
    Assert-True (@($k | Where-Object { $_ -like '*/manifest.json' }).Count -ge 1) 'must upload manifest'
    Assert-True (@($k | Where-Object { $_ -like '*.dump' -or $_ -like '*backup.tar' }).Count -eq 0) 'must NOT upload plaintext'
    Assert-True ((Test-Path -LiteralPath $headlog) -and (@(Get-Content -LiteralPath $headlog).Count -ge 1)) 'HEAD must be executed'
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

    # 10b) DB error CLASSIFICATION: for each allowlist category, a fake psql fails with a representative
    #      libpq stderr that embeds a sensitive marker (host/user/ref). The orchestrator output must contain
    #      ONLY the safe category label, and NEVER the raw stderr / marker / 'psql: error:' text.
    $cmarker = 'SENSITIVE_dbident_9f3a2b1c'
    $classCases = @(
        @{ cat='DB_AUTH_FAILED';            err=('psql: error: connection to server failed: FATAL:  password authentication failed for user "postgres.{0}"' -f $cmarker) },
        @{ cat='DB_DNS_FAILED';             err=('psql: error: could not translate host name "{0}.pooler.supabase.com" to address: Name or service not known' -f $cmarker) },
        @{ cat='DB_TIMEOUT';                err=('psql: error: connection to server at "{0}" (10.0.0.1), port 5432 failed: Connection timed out' -f $cmarker) },
        @{ cat='DB_REFUSED';                err=('psql: error: connection to server at "{0}" (10.0.0.1), port 5432 failed: Connection refused' -f $cmarker) },
        @{ cat='DB_ACCESS_POLICY';          err=('psql: error: connection failed: FATAL:  no pg_hba.conf entry for host "10.0.0.{0}", user "postgres", database "postgres", no encryption' -f $cmarker) },
        @{ cat='DB_SSL_FAILED';             err=('psql: error: connection failed: SSL error: certificate verify failed (host {0})' -f $cmarker) },
        @{ cat='DB_PORT_INVALID';           err=('psql: error: invalid port number: "{0}"' -f $cmarker) },
        @{ cat='DB_POOLER_CIRCUIT_BREAKER'; err=('psql: error: server closed the connection: Supavisor circuit breaker is open for tenant {0}' -f $cmarker) },
        @{ cat='DB_UNKNOWN';                err=('psql: error: an unexpected internal failure occurred near {0}' -f $cmarker) }
    )
    foreach ($case in $classCases) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH')
        $e.FAKE_PSQL_EXIT='2'; $e.FAKE_PSQL_STDERR=$case.err
        $r = Run-Capture $Script $e $args0
        Assert-True ($r.ExitCode -ne 0) ("classification {0}: run must fail" -f $case.cat)
        Assert-True ($r.Output -like ("*category={0}*" -f $case.cat)) ("classification: expected category={0} in output" -f $case.cat)
        Assert-True (-not ($r.Output -like "*$cmarker*")) ("classification {0}: sensitive marker must be absent" -f $case.cat)
        Assert-True (-not ($r.Output -like '*psql: error:*')) ("classification {0}: raw stderr must be absent" -f $case.cat)
        Write-Host ("OK classification {0}: only safe category, no raw stderr/marker" -f $case.cat)
    }
    # 10c) no OTHER allowlist category may leak in place of the expected one (mutual exclusivity spot-check)
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH')
    $e.FAKE_PSQL_EXIT='2'; $e.FAKE_PSQL_STDERR=('psql: error: could not translate host name "{0}" to address: Name or service not known' -f $cmarker)
    $r = Run-Capture $Script $e $args0
    Assert-True ($r.Output -like '*category=DB_DNS_FAILED*') 'DNS case must classify as DB_DNS_FAILED'
    Assert-True (-not ($r.Output -like '*DB_AUTH_FAILED*')) 'DNS case must NOT be misclassified as auth'
    Write-Host 'OK classification mutual-exclusivity spot-check'

    # 10d) PHASE A error CLASSIFICATION: a fake Phase A backup (via TASK009_PHASEA_BACKUP_PATH seam) fails
    #      with a representative stderr embedding a sensitive marker. Orchestrator output must contain ONLY
    #      the safe category and NEVER the raw stderr / marker / raw prefixes (pg_dump:/pg_restore:/TASK009_BACKUP_FAILED:).
    $pmarker = 'SENSITIVE_pgident_7b1e4d2a'
    $fakePhaseA = Join-Path $tmp 'fake_phasea.ps1'
    Set-Content -LiteralPath $fakePhaseA -Encoding UTF8 -Value @'
if ($env:FAKE_PHASEA_STDERR) { [Console]::Error.WriteLine($env:FAKE_PHASEA_STDERR) }
exit 1
'@
    $phaseaCases = @(
        @{ cat='PG_DUMP_VERSION_MISMATCH'; err=('pg_dump: error: aborting because of server version mismatch; pg_dump: server version: 17.4 (host {0}); pg_dump version: 16.14' -f $pmarker) },
        @{ cat='PG_SCHEMA_DUMP_FAILED';    err=('pg_dump: error: connection to database "{0}" failed; TASK009_BACKUP_FAILED: schema 匯出失敗，代碼：1' -f $pmarker) },
        @{ cat='PG_DATA_DUMP_FAILED';      err=('pg_dump: error: relation dump failed for {0}; TASK009_BACKUP_FAILED: data 匯出失敗，代碼：1' -f $pmarker) },
        @{ cat='PG_RESTORE_VERIFY_FAILED'; err=('pg_restore: error: could not read from file {0}; TASK009_BACKUP_FAILED: schema 備份檔無法讀取' -f $pmarker) },
        @{ cat='PHASEA_INPUT_OR_PATH_FAILED'; err=('TASK009_BACKUP_FAILED: 缺少必要連線環境變數：PGPASSWORD（來源 {0}）' -f $pmarker) },
        @{ cat='PHASEA_UNKNOWN';           err=('TASK009_BACKUP_FAILED: 未預期的內部錯誤，附近 {0}' -f $pmarker) }
    )
    foreach ($case in $phaseaCases) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH')
        $e.TASK009_PHASEA_BACKUP_PATH=$fakePhaseA; $e.FAKE_PHASEA_STDERR=$case.err
        $r = Run-Capture $Script $e $args0
        Assert-True ($r.ExitCode -ne 0) ("phaseA classification {0}: run must fail" -f $case.cat)
        Assert-True ($r.Output -like ("*stage=phaseA_backup*category={0}*" -f $case.cat)) ("phaseA classification: expected category={0}" -f $case.cat)
        Assert-True (-not ($r.Output -like "*$pmarker*")) ("phaseA classification {0}: marker must be absent" -f $case.cat)
        foreach ($raw in @('pg_dump:','pg_restore:','TASK009_BACKUP_FAILED:')) {
            Assert-True (-not ($r.Output -like "*$raw*")) ("phaseA classification {0}: raw prefix '$raw' must be absent" -f $case.cat)
        }
        Write-Host ("OK phaseA classification {0}: only safe category, no raw stderr/marker" -f $case.cat)
    }

    # 10e) SAFE VERSION PREFLIGHT (client pg_dump major vs server major), fail-closed:
    #      client<server FAIL, client=server PASS, client>server PASS, unparsable server/client FAIL closed.
    #      Only numeric majors may appear; never a connection string or command line.
    # client < server -> fail closed PG_DUMP_VERSION_MISMATCH
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_PGDUMP_VERSION='16.14'; $e.FAKE_SERVER_VERSION_NUM='170004'
    $r = Run-Capture $Script $e $args0
    Assert-True ($r.ExitCode -ne 0) 'version preflight client<server must fail'
    Assert-True ($r.Output -like '*stage=version_preflight*category=PG_DUMP_VERSION_MISMATCH*') 'client<server must be PG_DUMP_VERSION_MISMATCH'
    Assert-True (-not ($r.Output -like '*/manifest.json*')) 'client<server must fail BEFORE any upload'
    Write-Host 'OK version preflight client<server fail-closed'
    # client = server -> pass (full pipeline succeeds)
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_PGDUMP_VERSION='16.14'; $e.FAKE_SERVER_VERSION_NUM='160014'
    $rc = Run-Backup $e $args0
    Assert-True ($rc -eq 0) 'version preflight client=server must pass'
    Write-Host 'OK version preflight client=server pass'
    # client > server -> pass
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_PGDUMP_VERSION='17.2'; $e.FAKE_SERVER_VERSION_NUM='160014'
    $rc = Run-Backup $e $args0
    Assert-True ($rc -eq 0) 'version preflight client>server must pass'
    Write-Host 'OK version preflight client>server pass'
    # unparsable server version -> fail closed
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_SERVER_VERSION_NUM='not-a-number'
    $r = Run-Capture $Script $e $args0
    Assert-True ($r.ExitCode -ne 0) 'unparsable server version must fail closed'
    Assert-True ($r.Output -like '*stage=version_preflight*category=PG_DUMP_VERSION_MISMATCH*') 'unparsable server version -> PG_DUMP_VERSION_MISMATCH'
    Write-Host 'OK version preflight unparsable-server fail-closed'
    # unparsable client version -> fail closed
    Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.FAKE_PGDUMP_VERSION='not-a-version'
    $r = Run-Capture $Script $e $args0
    Assert-True ($r.ExitCode -ne 0) 'unparsable client version must fail closed'
    Assert-True ($r.Output -like '*stage=version_preflight*category=PG_DUMP_VERSION_MISMATCH*') 'unparsable client version -> PG_DUMP_VERSION_MISMATCH'
    Write-Host 'OK version preflight unparsable-client fail-closed'

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

    # 12) AGE ERROR CLASSIFICATION: fake age fails with a representative stderr embedding a
    #     sensitive marker; orchestrator output must contain ONLY the safe age category and
    #     NEVER the raw stderr / marker / 'age: error:' text.
    $amarker = 'SENSITIVE_agekey_5c1d9f0e'
    $ageCases = @(
        @{ cat='AGE_RECIPIENT_INVALID'; err=('age: error: parsing recipient "{0}": malformed X25519 recipient' -f $amarker) },
        @{ cat='AGE_RECIPIENT_INVALID'; err=('age: error: no recipients specified {0}' -f $amarker) },
        @{ cat='AGE_ENCRYPT_FAILED';    err=('age: error: failed to write header near {0}' -f $amarker) }
    )
    foreach ($case in $ageCases) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH')
        $e.FAKE_AGE_MODE='fail'; $e.FAKE_AGE_STDERR=$case.err
        $r = Run-Capture $Script $e $args0
        Assert-True ($r.ExitCode -ne 0) ("age classification {0}: run must fail" -f $case.cat)
        Assert-True ($r.Output -like ("*stage=age_encrypt*category={0}*" -f $case.cat)) ("age classification: expected category={0}" -f $case.cat)
        Assert-True (-not ($r.Output -like "*$amarker*")) ("age classification {0}: marker must be absent" -f $case.cat)
        Assert-True (-not ($r.Output -like '*age: error:*')) ("age classification {0}: raw stderr must be absent" -f $case.cat)
        Assert-True (-not (Test-Path -LiteralPath $keys)) ("age classification {0}: no upload on age failure" -f $case.cat)
        Write-Host ("OK age classification {0}: only safe category, no raw stderr/marker" -f $case.cat)
    }

    # 13) AGE RECIPIENT PREFLIGHT — fail-closed IMMEDIATELY after Require-Env, BEFORE any
    #     row-count / psql / version-preflight / Phase A / tar / age / upload work. Proves an
    #     invalid recipient never triggers production DB reads or plaintext backup generation.
    foreach ($bad in @('age1UPPER','age1abc ',"age1abc`n",'notanagekey','age2abc','ssh-dss AAAA')) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.AGE_RECIPIENT=$bad
        $r = Run-Capture $Script $e $args0
        Assert-True ($r.ExitCode -ne 0) 'invalid recipient must fail'
        Assert-True ($r.Output -like '*stage=age_preflight*category=AGE_RECIPIENT_INVALID*') 'invalid recipient -> AGE_RECIPIENT_INVALID at age_preflight'
        Assert-True (-not ($r.Output -like "*$bad*")) 'preflight must not echo the recipient value'
        Assert-True (-not ($r.Output -like '*age: error:*')) 'preflight must not leak raw age stderr'
        # ordering: no DB query, and none of the later progress markers appeared
        Assert-True (-not (Test-Path -LiteralPath $qlog)) 'preflight fails before any psql query (empty query log)'
        Assert-True (-not ($r.Output -like '*row-count 完成*')) 'no row-count-complete marker before preflight fail'
        Assert-True (-not ($r.Output -like '*版本前檢通過*')) 'no version-preflight-pass marker before preflight fail'
        Assert-True (-not ($r.Output -like '*manifest/checksum 驗證通過*')) 'no Phase A / manifest-check-success marker before preflight fail'
        Assert-True (-not ($r.Output -like '*TASK009_REMOTE_BACKUP_OK*')) 'no backup-success marker'
        Assert-True (-not (Test-Path -LiteralPath $headlog)) 'no HEAD verification when preflight fails'
        Assert-True (-not (Test-Path -LiteralPath $keys)) 'no R2 upload call when recipient preflight fails'
        Write-Host 'OK age recipient preflight rejects invalid shape (early, fail-closed, no DB, no echo)'
    }
    # valid recipient shapes pass the preflight (full pipeline succeeds)
    foreach ($good in @('age1fakerecipient','ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITEST comment-ok')) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.AGE_RECIPIENT=$good
        $rc = Run-Backup $e $args0
        Assert-True ($rc -eq 0) ("valid recipient must pass preflight and pipeline: {0}" -f $good)
        Write-Host 'OK age recipient preflight accepts valid shape'
    }

    # 14) AWS/S3 ERROR CLASSIFICATION: fake aws s3 cp fails with a representative stderr embedding a
    #     sensitive marker; orchestrator output must contain ONLY the safe R2 category and NEVER the
    #     raw stderr / marker. Also verifies AWS official exit-code fallback (252/253/254).
    $s3marker = 'SENSITIVE_r2ident_3e9a7c15'
    $s3cases = @(
        @{ cat='R2_PARAMETER_INVALID';     exit='2';   err=('Parameter validation failed: Invalid bucket name "{0}"' -f $s3marker) },
        @{ cat='R2_CONFIG_OR_CREDENTIALS'; exit='2';   err=('Unable to locate credentials near {0}' -f $s3marker) },
        @{ cat='R2_SERVICE_REJECTED';      exit='2';   err=('An error occurred (AccessDenied) when calling PutObject {0}' -f $s3marker) },
        @{ cat='R2_PARAMETER_INVALID';     exit='252'; err='' },   # exit-code fallback (252)
        @{ cat='R2_CONFIG_OR_CREDENTIALS'; exit='253'; err='' },   # exit-code fallback (253)
        @{ cat='R2_SERVICE_REJECTED';      exit='254'; err='' },   # exit-code fallback (254)
        @{ cat='R2_UNKNOWN';               exit='1';   err='' }
    )
    foreach ($case in $s3cases) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH')
        $e.FAKE_S3_MODE='upload_fail'; $e.FAKE_S3_EXIT=$case.exit; $e.FAKE_S3_STDERR=$case.err
        $r = Run-Capture $Script $e $args0
        Assert-True ($r.ExitCode -ne 0) ("s3 classification {0}: run must fail" -f $case.cat)
        Assert-True ($r.Output -like ("*stage=s3_upload*category={0}*" -f $case.cat)) ("s3 classification: expected category={0}" -f $case.cat)
        if ($case.err) { Assert-True (-not ($r.Output -like "*$s3marker*")) ("s3 classification {0}: marker must be absent" -f $case.cat) }
        Write-Host ("OK s3 classification {0}: only safe category, no raw stderr/marker" -f $case.cat)
    }

    # 15) R2 TARGET PREFLIGHT — fail-closed IMMEDIATELY after Require-Env, BEFORE any DB/Phase A/upload.
    #     invalid bucket/endpoint shapes -> R2_PARAMETER_INVALID at stage=r2_preflight; value never echoed.
    $r2bad = @(
        @{ k='R2_BUCKET';   v='ab' },                 # too short (<3)
        @{ k='R2_BUCKET';   v='ci-test-bucket ' },    # trailing space
        @{ k='R2_BUCKET';   v="ci-test`nbucket" },    # newline
        @{ k='R2_BUCKET';   v='CI-Test-Bucket' },     # uppercase
        @{ k='R2_BUCKET';   v='ci..bucket' },         # consecutive dots
        @{ k='R2_ENDPOINT'; v='http://example.invalid' },   # not https
        @{ k='R2_ENDPOINT'; v='https://example.invalid ' }, # trailing space
        @{ k='R2_ENDPOINT'; v="https://example.invalid`n" }, # newline
        @{ k='R2_ENDPOINT'; v='ftp://example.invalid' }      # wrong scheme
    )
    foreach ($case in $r2bad) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e[$case.k]=$case.v
        $r = Run-Capture $Script $e $args0
        Assert-True ($r.ExitCode -ne 0) ("invalid {0} must fail" -f $case.k)
        Assert-True ($r.Output -like '*stage=r2_preflight*category=R2_PARAMETER_INVALID*') ("invalid {0} -> R2_PARAMETER_INVALID at r2_preflight" -f $case.k)
        Assert-True (-not ($r.Output -like ("*{0}*" -f $case.v))) 'r2 preflight must not echo the value'
        Assert-True (-not (Test-Path -LiteralPath $qlog)) 'r2 preflight fails before any psql query (empty query log)'
        Assert-True (-not ($r.Output -like '*row-count 完成*')) 'no row-count-complete marker before r2 preflight fail'
        Assert-True (-not (Test-Path -LiteralPath $keys)) 'no R2 upload when r2 preflight fails'
        Write-Host ("OK r2 target preflight rejects invalid {0} (early, fail-closed, no DB, no echo)" -f $case.k)
    }
    # valid bucket/endpoint shapes pass the preflight (full pipeline succeeds)
    foreach ($case in @(
        @{ b='xiaochenguang-task009-backups'; ep='https://acct.r2.cloudflarestorage.com' },
        @{ b='ci.test.bucket'; ep='https://example.invalid:8443/path' }
    )) {
        Reset; $e = Base-Env; $e.Remove('MANIFEST_CHECK_PATH'); $e.R2_BUCKET=$case.b; $e.R2_ENDPOINT=$case.ep
        $rc = Run-Backup $e $args0
        Assert-True ($rc -eq 0) ("valid R2 target must pass preflight and pipeline: {0}" -f $case.b)
        Write-Host 'OK r2 target preflight accepts valid shape'
    }

    Write-Host ''
    Write-Host 'TASK009_REMOTE_BACKUP_TESTS_PASS'
}
finally { Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue }
