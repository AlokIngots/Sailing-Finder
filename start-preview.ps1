<#
Starts the whole local preview in one step:

  1. an embedded PostgreSQL 16 (from the pixeltable-pgserver wheel, no install)
  2. the schema (db.migrate) and the sample schedule (scripts.seed_sample)
  3. a local admin account to sign in with
  4. the built React app, served by the FastAPI backend

    powershell -ExecutionPolicy Bypass -File .\start-preview.ps1

Then open http://127.0.0.1:8010. Safe to re-run: it reuses the database,
re-seeds only the sample rows (source = 'sample-seed'), rebuilds the frontend
and restarts the backend.

Everything the preview writes - the database files, logs and the generated
preview password - lives in %LOCALAPPDATA%\SailingFinderPreview, outside the
repo, so nothing here can be committed by accident. Delete that folder (after
running with -Stop) to start from scratch.

    .\start-preview.ps1 -Stop     # stop the backend and the database

LOCAL PREVIEW ONLY. This is not how the app is deployed - ./deploy.sh is.
#>

[CmdletBinding()]
param(
    [switch]$Stop
)

$ErrorActionPreference = 'Stop'

$Root     = $PSScriptRoot
$Backend  = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Python   = Join-Path $Backend '.venv\Scripts\python.exe'

$AppHost  = '127.0.0.1'
$AppPort  = 8010
$DbPort   = 5433            # not 5432, so it never collides with a real Postgres
$DbName   = 'sailing_finder'
$DbUser   = 'postgres'
$PgServerPackage = 'pixeltable-pgserver==0.6.0'

$State    = Join-Path $env:LOCALAPPDATA 'SailingFinderPreview'
$PgData   = Join-Path $State 'pgdata'
$Logs     = Join-Path $State 'logs'
$Secrets  = Join-Path $State 'preview.json'
$AppPid   = Join-Path $State 'backend.pid'

function Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }

function Invoke-Native {
    # Runs a native command and stops the script if it fails.
    param([string]$File, [string[]]$Arguments, [string]$What)
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$What failed (exit code $LASTEXITCODE)." }
}

function Get-PgBin {
    $site = & $Python -c "import pixeltable_pgserver, pathlib; print(pathlib.Path(pixeltable_pgserver.__file__).parent)" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $site) { return $null }
    # 'pginstall' is PostgreSQL 16, the same major version production runs.
    $bin = Join-Path $site.Trim() 'pginstall\bin'
    if (Test-Path (Join-Path $bin 'pg_ctl.exe')) { return $bin }
    return $null
}

function Stop-Backend {
    if (Test-Path $AppPid) {
        $old = Get-Content $AppPid -ErrorAction SilentlyContinue
        if ($old) {
            $proc = Get-Process -Id $old -ErrorAction SilentlyContinue
            if ($proc) {
                Step "Stopping the previous preview backend (PID $old)"
                # /T takes uvicorn's child processes down with it.
                & taskkill.exe /PID $old /T /F | Out-Null
            }
        }
        Remove-Item $AppPid -Force -ErrorAction SilentlyContinue
    }
}

function Test-PortBusy($port) {
    $hits = netstat -ano | Select-String -Pattern "^\s*TCP\s+\S+:$port\s+\S+\s+LISTENING"
    return [bool]$hits
}

New-Item -ItemType Directory -Force -Path $State, $Logs | Out-Null

# --- -Stop ---------------------------------------------------------------------
if ($Stop) {
    Stop-Backend
    $bin = if (Test-Path $Python) { Get-PgBin } else { $null }
    if ($bin -and (Test-Path (Join-Path $PgData 'PG_VERSION'))) {
        & (Join-Path $bin 'pg_ctl.exe') status -D $PgData | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Step 'Stopping the preview database'
            Invoke-Native (Join-Path $bin 'pg_ctl.exe') @('stop', '-D', $PgData, '-m', 'fast', '-w') 'pg_ctl stop'
        }
    }
    Write-Host 'Preview stopped.' -ForegroundColor Green
    return
}

# --- 1. Python environment ---------------------------------------------------------
if (-not (Test-Path $Python)) {
    Step 'Creating backend\.venv and installing requirements'
    $py = (Get-Command py -ErrorAction SilentlyContinue)
    if ($py) { Invoke-Native 'py' @('-3', '-m', 'venv', (Join-Path $Backend '.venv')) 'Creating the venv' }
    else     { Invoke-Native 'python' @('-m', 'venv', (Join-Path $Backend '.venv')) 'Creating the venv' }
    Invoke-Native $Python @('-m', 'pip', 'install', '-q', '-r', (Join-Path $Backend 'requirements.txt')) 'pip install'
}

$PgBin = Get-PgBin
if (-not $PgBin) {
    Step "Installing the embedded Postgres ($PgServerPackage) into backend\.venv"
    Invoke-Native $Python @('-m', 'pip', 'install', '-q', $PgServerPackage) 'pip install pixeltable-pgserver'
    $PgBin = Get-PgBin
    if (-not $PgBin) { throw 'Embedded Postgres binaries not found after install.' }
}
$PgCtl = Join-Path $PgBin 'pg_ctl.exe'
$Psql  = Join-Path $PgBin 'psql.exe'

# --- 2. Embedded Postgres ---------------------------------------------------------
if (-not (Test-Path (Join-Path $PgData 'PG_VERSION'))) {
    Step "Initialising a new database cluster in $PgData"
    # trust auth is acceptable only because the server listens on 127.0.0.1 alone.
    Invoke-Native (Join-Path $PgBin 'initdb.exe') @(
        '-D', $PgData, '-U', $DbUser, '-A', 'trust', '-E', 'UTF8', '--locale=C'
    ) 'initdb'
}

& $PgCtl status -D $PgData | Out-Null
if ($LASTEXITCODE -ne 0) {
    if (Test-PortBusy $DbPort) { throw "Port $DbPort is already in use by something else." }
    Step "Starting Postgres 16 on ${AppHost}:$DbPort"
    Invoke-Native $PgCtl @(
        'start', '-D', $PgData, '-w', '-t', '60',
        '-l', (Join-Path $Logs 'postgres.log'),
        '-o', "-p $DbPort -c listen_addresses=$AppHost"
    ) 'pg_ctl start'
} else {
    Step 'Postgres already running'
}

$exists = & $Psql -h $AppHost -p $DbPort -U $DbUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$DbName'"
if ($LASTEXITCODE -ne 0) { throw 'Could not reach the preview database.' }
if (-not "$exists".Trim()) {
    Step "Creating database $DbName"
    Invoke-Native $Psql @('-h', $AppHost, '-p', $DbPort, '-U', $DbUser, '-d', 'postgres', '-qc', "CREATE DATABASE $DbName") 'CREATE DATABASE'
}

# --- 3. Preview settings (process env only; backend\.env is never touched) -----------
# Generated once, kept outside the repo, reused on every run.
if (Test-Path $Secrets) {
    $preview = Get-Content $Secrets -Raw | ConvertFrom-Json
} else {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $sessionSecret = -join ($bytes | ForEach-Object { $_.ToString('x2') })
    $alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'.ToCharArray()
    $pwBytes = New-Object byte[] 16
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($pwBytes)
    $password = -join ($pwBytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] })
    $preview = [pscustomobject]@{
        session_secret = $sessionSecret
        username       = 'preview'
        password       = $password
    }
    $preview | ConvertTo-Json | Set-Content -Path $Secrets -Encoding utf8
}

# python-dotenv does not override variables already set, so these win over
# backend\.env, and anything only in backend\.env (e.g. SMTP) still applies.
$env:APP_ENV         = 'development'          # cookie without the HTTPS-only flag
$env:TZ              = 'Asia/Kolkata'
$env:PORT            = "$AppPort"
$env:PUBLIC_URL      = "http://${AppHost}:$AppPort"
$env:DATABASE_URL    = "postgresql://$DbUser@${AppHost}:$DbPort/$DbName"
$env:SESSION_SECRET  = $preview.session_secret
$env:SHEET_ID        = 'preview-no-sheet'     # the sheet sync is not run locally
$env:GOOGLE_KEY_PATH = 'preview-no-key'
$env:UPLOAD_DIR      = (Join-Path $State 'uploads')
$env:FRONTEND_DIST   = (Join-Path $Frontend 'dist')
# Forwarders come from backend\.env (FORWARDER_n_NAME / _EMAIL / _CC). Only when
# it has none, placeholders on a reserved domain are used so the app can start -
# a preview enquiry can never reach one of those.
Get-ChildItem env: | Where-Object { $_.Name -match '^FORWARDER_\d+_' } | ForEach-Object { Remove-Item "env:$($_.Name)" }
$hasForwarders = Select-String -Path (Join-Path $Backend '.env') -Pattern '^\s*FORWARDER_\d+_NAME\s*=\s*\S' -Quiet -ErrorAction SilentlyContinue
if (-not $hasForwarders) {
    $env:FORWARDER_1_NAME = 'Preview Forwarder 1'; $env:FORWARDER_1_EMAIL = 'forwarder1@example.invalid'
    $env:FORWARDER_2_NAME = 'Preview Forwarder 2'; $env:FORWARDER_2_EMAIL = 'forwarder2@example.invalid'
    $env:FORWARDER_3_NAME = 'Preview Forwarder 3'; $env:FORWARDER_3_EMAIL = 'forwarder3@example.invalid'
}
foreach ($k in 'SMTP_HOST', 'SMTP_USER', 'SMTP_PASS', 'MAIL_FROM') {
    # Required by config.validate; filled from backend\.env when it has them.
    if (-not (Get-Item "env:$k" -ErrorAction SilentlyContinue)) {
        $fromFile = Select-String -Path (Join-Path $Backend '.env') -Pattern "^\s*$k\s*=\s*\S" -Quiet -ErrorAction SilentlyContinue
        if (-not $fromFile) { Set-Item "env:$k" 'preview-not-configured' }
    }
}

# --- 4. Schema, sample data, sign-in ----------------------------------------------
Push-Location $Backend
try {
    Step 'Applying the schema'
    Invoke-Native $Python @('-m', 'db.migrate') 'db.migrate'

    Step 'Seeding the sample schedule (only rows with source = sample-seed are touched)'
    # Clear then seed, so the made-up dates always start from today.
    Invoke-Native $Python @('-m', 'scripts.seed_sample', '--clear') 'seed_sample --clear'
    Invoke-Native $Python @('-m', 'scripts.seed_sample') 'seed_sample'

    $hasUser = & $Psql -h $AppHost -p $DbPort -U $DbUser -d $DbName -tAc "SELECT 1 FROM users WHERE username = '$($preview.username)'"
    if (-not "$hasUser".Trim()) {
        Step "Creating the preview admin account '$($preview.username)'"
        $env:SF_NEW_PASSWORD = $preview.password
        try {
            Invoke-Native $Python @('-m', 'scripts.create_user', $preview.username, 'Preview Admin', 'admin') 'create_user'
        } finally {
            Remove-Item env:SF_NEW_PASSWORD -ErrorAction SilentlyContinue
        }
    }
} finally {
    Pop-Location
}

# --- 5. Frontend build -------------------------------------------------------------
Push-Location $Frontend
try {
    if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) {
        Step 'Installing frontend dependencies (npm ci)'
        Invoke-Native 'npm.cmd' @('ci', '--no-audit', '--no-fund') 'npm ci'
    }
    Step 'Building the frontend'
    Invoke-Native 'npm.cmd' @('run', 'build') 'npm run build'
} finally {
    Pop-Location
}

# --- 6. Backend --------------------------------------------------------------------
Stop-Backend
if (Test-PortBusy $AppPort) {
    throw "Port $AppPort is already in use by another program. Free it and re-run."
}

Step "Starting the backend on http://${AppHost}:$AppPort"
$proc = Start-Process -FilePath $Python `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', $AppHost, '--port', "$AppPort") `
    -WorkingDirectory $Backend -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $Logs 'backend.out.log') `
    -RedirectStandardError  (Join-Path $Logs 'backend.err.log')
Set-Content -Path $AppPid -Value $proc.Id

$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    if ($proc.HasExited) { break }
    try {
        $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "http://${AppHost}:$AppPort/healthz"
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }
    Start-Sleep -Milliseconds 500
}
if (-not $healthy) {
    Write-Host '--- backend.err.log (tail) ---' -ForegroundColor Yellow
    Get-Content (Join-Path $Logs 'backend.err.log') -Tail 30 -ErrorAction SilentlyContinue
    throw 'The backend did not become healthy.'
}

Write-Host ''
Write-Host "Preview is live:  http://${AppHost}:$AppPort" -ForegroundColor Green
Write-Host "Sign in as:       $($preview.username) / $($preview.password)   (admin, local preview only)"
Write-Host "Logs:             $Logs"
Write-Host 'Stop it with:     .\start-preview.ps1 -Stop'
