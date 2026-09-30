# scripts/check-all.ps1
# Master verification script for DRISHTI.
#
# Runs three stages, in order:
#   1. backend tests   -- python -m pytest backend/tests -q  (from the repo root)
#   2. frontend tests  -- npm test                            (in frontend/)
#   3. frontend build  -- npm run build                      (in frontend/)
#
# Every stage runs even when an earlier one fails, so a single invocation
# reports the whole picture instead of stopping at the first failure. The
# script exits 1 if any stage failed, and 0 only when all three passed.
#
# Usage:  ./scripts/check-all.ps1
#
# The repo root is derived from this script's own location, so the caller's
# working directory does not matter.

$ErrorActionPreference = "Continue"

$repoRoot = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $repoRoot "frontend"
$failed = @()

# Fail fast and loudly if a required tool is missing, instead of letting every
# stage report a confusing "command not found".
foreach ($tool in @("python", "npm")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "==========================================" -ForegroundColor Red
        Write-Host " VERIFICATION FAILED - required tool '$tool' is not on PATH." -ForegroundColor Red
        Write-Host "==========================================" -ForegroundColor Red
        exit 1
    }
}

function Invoke-Stage {
    param(
        [Parameter(Mandatory = $true)][string] $Name,
        [Parameter(Mandatory = $true)][string] $WorkingDirectory,
        [Parameter(Mandatory = $true)][scriptblock] $Command
    )

    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan

    # Clear any exit code left over from an earlier native command. If this
    # stage dies before running a native command, we must not silently read
    # the previous stage's result.
    $global:LASTEXITCODE = 0

    Push-Location $WorkingDirectory
    try {
        & $Command
    }
    catch {
        Write-Host "FAIL: $Name did not run to completion: $_" -ForegroundColor Red
        $script:failed += $Name
        return
    }
    finally {
        Pop-Location
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name (exit code $LASTEXITCODE)." -ForegroundColor Red
        $script:failed += $Name
        return
    }

    Write-Host "PASS: $Name." -ForegroundColor Green
}

Invoke-Stage -Name "Backend tests (pytest)" -WorkingDirectory $repoRoot -Command {
    # -p no:faulthandler: under pytest, importing numpy/cv2 raises a non-fatal
    # "Windows fatal exception: access violation" that dumps three large stack
    # traces to stderr. The run still succeeds, but the noise buries the real
    # results. Disabling faulthandler silences it; genuine failures are still
    # reported with a non-zero exit code.
    python -m pytest backend/tests -q -p no:faulthandler
}

Invoke-Stage -Name "Frontend tests (npm test)" -WorkingDirectory $frontendDir -Command {
    npm test
}

Invoke-Stage -Name "Frontend build (npm run build)" -WorkingDirectory $frontendDir -Command {
    npm run build
}

Write-Host ""
Write-Host "=========================================="
if ($failed.Count -gt 0) {
    Write-Host " VERIFICATION FAILED - $($failed.Count) of 3 stages" -ForegroundColor Red
    foreach ($name in $failed) {
        Write-Host "   - $name" -ForegroundColor Red
    }
    Write-Host "==========================================" -ForegroundColor Red
    exit 1
}
else {
    Write-Host " ALL CHECKS PASSED SUCCESSFULLY - 3 of 3 stages" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    exit 0
}
