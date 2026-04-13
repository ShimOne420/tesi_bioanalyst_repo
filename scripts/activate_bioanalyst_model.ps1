$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

$VenvPath = Join-Path $ProjectRoot ".venv-bioanalyst\Scripts\Activate.ps1"
if (-not (Test-Path $VenvPath)) {
    Write-Host "Ambiente modello non trovato: $ProjectRoot\.venv-bioanalyst"
    Write-Host "Crea prima l'ambiente dedicato del modello."
    exit 1
}

. $VenvPath

$EnvFile = Join-Path $ProjectRoot ".env"
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') {
            return
        }
        $parts = $_ -split '=', 2
        if ($parts.Length -eq 2) {
            [System.Environment]::SetEnvironmentVariable($parts[0], $parts[1])
        }
    }
}

$BfmRoot = Join-Path $ProjectRoot "external\bfm-model"
$env:BFM_MODEL_REPO = $BfmRoot

if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $BfmRoot
}
elseif (-not $env:PYTHONPATH.Contains($BfmRoot)) {
    $env:PYTHONPATH = "$BfmRoot;$($env:PYTHONPATH)"
}

Write-Host "Ambiente BioAnalyst attivo"
Write-Host "PROJECT_ROOT=$ProjectRoot"
Write-Host "BFM_MODEL_REPO=$($env:BFM_MODEL_REPO)"
Write-Host "BIOANALYST_MODEL_DIR=$($env:BIOANALYST_MODEL_DIR)"
