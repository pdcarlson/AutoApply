<#
.SYNOPSIS
Starts the AutoApply demo: the backend API and the frontend, in this one terminal.

.DESCRIPTION
Runs `python -m server` from backend/ (API on http://127.0.0.1:8080) in the background and
`npm run dev:api` from frontend/ in the foreground (http://localhost:5173). Press Ctrl+C to stop
both. See "Run the demo" in README.md for the two-terminal version and what each switch means.

.PARAMETER Offline
FAKE_GREENHOUSE=true and USE_CLAUDE=false: paste
https://job-boards.greenhouse.io/fakecompany/jobs/1001 and the agent fills the local fake form.
Nothing goes online.

.PARAMETER SubmitRealForm
SUBMIT_REAL_FORM=true for this run, so Submit really presses Submit. Only allowed with -Offline,
where the only form is the local fake one. For real employers, set it in backend/agent/.env.

.PARAMETER DataDir
Where the demo keeps its data (AUTOAPPLY_DATA_DIR). Default: backend/data.

.PARAMETER Reset
Delete the data dir first and start from a clean slate.

.EXAMPLE
.\scripts\demo.ps1 -Offline -Reset
#>
param(
    [switch]$Offline,
    [switch]$SubmitRealForm,
    [string]$DataDir,
    [switch]$Reset
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo 'backend'
$frontend = Join-Path $repo 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    throw "No backend venv at $python. Create it first (see README.md, Run the demo)."
}
if ($SubmitRealForm -and -not $Offline) {
    throw '-SubmitRealForm is only allowed with -Offline (the local fake form). To submit to real employers, set SUBMIT_REAL_FORM=true in backend/agent/.env yourself.'
}
if (-not $DataDir) { $DataDir = Join-Path $backend 'data' }
$DataDir = [System.IO.Path]::GetFullPath($DataDir)
if ($Reset -and (Test-Path $DataDir)) {
    Write-Host "Deleting $DataDir"
    Remove-Item -Recurse -Force $DataDir
}

# Child processes inherit these. Variables you already set in this terminal win otherwise.
$env:AUTOAPPLY_DATA_DIR = $DataDir
if ($Offline) {
    $env:FAKE_GREENHOUSE = 'true'
    $env:USE_CLAUDE = 'false'
}
if ($SubmitRealForm) { $env:SUBMIT_REAL_FORM = 'true' }

if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Push-Location $frontend
    try { npm install } finally { Pop-Location }
}

$server = Start-Process -FilePath $python -ArgumentList '-m', 'server' `
    -WorkingDirectory $backend -NoNewWindow -PassThru
try {
    if ($Offline) {
        Write-Host 'Offline demo: paste https://job-boards.greenhouse.io/fakecompany/jobs/1001'
    }
    Write-Host 'Open http://localhost:5173 once Vite is ready. Ctrl+C stops both.'
    Push-Location $frontend
    try { npm run dev:api } finally { Pop-Location }
}
finally {
    if (-not $server.HasExited) {
        & taskkill /PID $server.Id /T /F | Out-Null
    }
}
