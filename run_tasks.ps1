# Autonomous Execution Loop for Windows
# Usage: powershell -ExecutionPolicy Bypass -File .\run_tasks.ps1
param(
    [string]$CliTool = "fcc-codex",
    # Force a subcommand, e.g. -CliVerb exec. Leave unset to auto-detect.
    [string[]]$CliVerb = @(),
    # codex exec has no --ask-for-approval. These are its real equivalents.
    [ValidateSet("Approve", "Bypass", "Prompt")]
    [string]$Approval = "Approve",
    [ValidateSet("read-only", "workspace-write", "danger-full-access")]
    [string]$Sandbox = "workspace-write",
    # Attempts per task before it is marked [BLOCKED].
    [int]$MaxAttempts = 3,
    # Lines of verification output fed back to the agent on a retry.
    [int]$FeedbackLines = 120
)

$ErrorActionPreference = "Continue"

$repoRoot = $PSScriptRoot
Set-Location $repoRoot

$tasksFile = Join-Path $repoRoot "tasks.md"
$checkScript = Join-Path $repoRoot "scripts\check-all.ps1"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

if (-not (Test-Path $tasksFile)) {
    Write-Error "Error: tasks.md not found at $tasksFile."
    exit 1
}

function Read-Tasks {
    $raw = [System.IO.File]::ReadAllText($tasksFile)
    $eol = if ($raw.Contains("`r`n")) { "`r`n" } else { "`n" }
    return , @{
        Lines = @($raw -split "`r?`n")
        Eol   = $eol
    }
}

function Write-Tasks($doc) {
    [System.IO.File]::WriteAllText(
        $tasksFile, (($doc.Lines) -join $doc.Eol), $utf8NoBom)
}

function Find-NextTask($lines) {
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $l = $lines[$i]
        if ($l -match "^\s*-\s*\[\s*\]" -and $l -notmatch "\[BLOCKED\]") {
            return $i
        }
    }
    return -1
}

function Get-TaskBlock($lines, $index) {
    # Checkbox line plus its indented continuation lines.
    $block = New-Object System.Collections.ArrayList
    [void]$block.Add($lines[$index])
    for ($j = $index + 1; $j -lt $lines.Count; $j++) {
        if ($lines[$j] -match "^\s*-\s*\[" -or $lines[$j] -match "^\S") { break }
        if (-not [string]::IsNullOrWhiteSpace($lines[$j])) {
            [void]$block.Add($lines[$j])
        }
    }
    return ($block -join "`n")
}

function Get-ApprovalArgs {
    # These three are mutually exclusive in `codex exec`. --approve-for-me
    # already implies the workspace-write sandbox, so it must not be paired
    # with -s, and -s is only used by the Prompt mode.
    switch ($Approval) {
        "Bypass" { return @("--dangerously-bypass-approvals-and-sandbox") }
        "Prompt" { return @("-s", $Sandbox) }
        default { return @("--approve-for-me") }
    }
}

function Get-Tail($text, $maxLines) {
    if ([string]::IsNullOrWhiteSpace($text)) { return "" }
    $all = @($text -split "`r?`n")
    if ($all.Count -le $maxLines) { return $text }
    $kept = $all[($all.Count - $maxLines)..($all.Count - 1)]
    return ("[{0} earlier lines omitted]`n" -f ($all.Count - $maxLines)) +
    ($kept -join "`n")
}

function Select-FailureDetail($text, $maxLines) {
    # A blind tail is unreliable: the interesting assertion can sit far above
    # the end once later stages have printed their own output. Prefer the
    # section that actually reports the failure, and fall back to the tail.
    if ([string]::IsNullOrWhiteSpace($text)) { return "" }
    $lines = @($text -split "`r?`n")

    $start = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "=+\s*(FAILURES|ERRORS)\s*=+") { $start = $i; break }
    }
    if ($start -lt 0) {
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -match "short test summary info") { $start = $i; break }
        }
    }

    if ($start -ge 0) {
        $window = @()
        for ($i = $start; $i -lt $lines.Count -and $window.Count -lt $maxLines; $i++) {
            $window += $lines[$i]
        }
        $header = "--- failure detail ---`n"
        if ($start -gt 0) {
            $header += ("[earlier output omitted; failure section starts at line {0} of {1}]`n" -f
                ($start + 1), $lines.Count)
        }
        return $header + ($window -join "`n")
    }

    return Get-Tail $text $maxLines
}

function Invoke-Verification {
    if (-not (Test-Path $checkScript)) {
        Write-Host "check-all.ps1 not found; skipping verification." -ForegroundColor Yellow
        return @{ Exit = 0; Output = "" }
    }
    Write-Host "Running verification via check-all.ps1..." -ForegroundColor Gray
    $out = & $hostExe -NoProfile -ExecutionPolicy Bypass -File $checkScript 2>&1
    $code = $LASTEXITCODE
    foreach ($l in $out) { Write-Host $l }
    return @{ Exit = $code; Output = ($out | Out-String) }
}

function Set-TaskBlocked($taskLine) {
    # Re-read first: the agent may have rewritten tasks.md during its attempt,
    # so writing a stale in-memory copy would discard the agent's own edits.
    $sig = ($taskLine -replace "^\s*-\s*\[[^\]]*\]", "").Trim()
    $fresh = Read-Tasks
    for ($i = 0; $i -lt $fresh.Lines.Count; $i++) {
        $s = ($fresh.Lines[$i] -replace "^\s*-\s*\[[^\]]*\]", "").Trim()
        if ($s -eq $sig) {
            $fresh.Lines[$i] = $fresh.Lines[$i] -replace
            "^\s*-\s*\[[^\]]*\]", "- [ ] [BLOCKED]"
            Write-Tasks $fresh
            return $true
        }
    }
    return $false
}

$cmd = Get-Command $CliTool -ErrorAction SilentlyContinue
if (-not $cmd) {
    Write-Error "Error: '$CliTool' not found on PATH."
    exit 1
}
$cliExe = $cmd.Source

if (-not $PSBoundParameters.ContainsKey("CliVerb")) {
    Write-Host "Probing $CliTool for a non-interactive subcommand..." -ForegroundColor DarkGray
    $helpText = (& $CliTool --help 2>&1 | Out-String)
    if ($helpText -match "(?m)^\s*exec\b") {
        $CliVerb = @("exec")
        Write-Host "Using '$CliTool exec' (non-interactive)." -ForegroundColor DarkGray
    }
    else {
        Write-Host "No 'exec' subcommand found; passing the prompt directly." -ForegroundColor Yellow
    }
}

$approvalArgs = Get-ApprovalArgs
Write-Host "Approval mode: $Approval  Sandbox: $Sandbox" -ForegroundColor DarkGray
Write-Host "Max attempts per task: $MaxAttempts" -ForegroundColor DarkGray
Write-Host "Repo root: $repoRoot" -ForegroundColor DarkGray

$hostExe = (Get-Process -Id $PID).Path
$taskNumber = 0
$promptFile = Join-Path $env:TEMP (
    "codex_prompt_{0}.txt" -f [guid]::NewGuid().ToString("N"))

try {
    while ($true) {
        $doc = Read-Tasks
        $idx = Find-NextTask $doc.Lines

        if ($idx -lt 0) {
            Write-Host "`n==================================================" -ForegroundColor Green
            Write-Host "All tasks completed or processed!" -ForegroundColor Green
            break
        }

        $taskNumber++
        $taskLine = $doc.Lines[$idx]
        $taskBlock = Get-TaskBlock $doc.Lines $idx
        $feedback = ""
        $verified = $false
        $usageError = $false

        for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
            $prompt = "Follow AGENTS.md and execute this task from tasks.md:`n`n" +
            $taskBlock

            if ($feedback) {
                $prompt += "`n`n--- VERIFICATION FAILED ON YOUR PREVIOUS ATTEMPT ---`n" +
                "Attempt $attempt of $MaxAttempts. Fix the root cause below.`n" +
                "Do NOT delete, skip, xfail, weaken or edit the failing test, and do not " +
                "edit check-all.ps1 to make it pass. Fix the code under test.`n`n" +
                (Select-FailureDetail $feedback $FeedbackLines)
            }

            # Feed the prompt over stdin. Passing it as an argv value re-parsed
            # it on Windows and split it into stray subcommands.
            [System.IO.File]::WriteAllText($promptFile, $prompt, $utf8NoBom)

            Write-Host "`n==================================================" -ForegroundColor Cyan
            Write-Host "[Task $taskNumber | Attempt $attempt/$MaxAttempts] $($taskLine.Trim())" -ForegroundColor Yellow
            Write-Host "==================================================" -ForegroundColor Cyan

            $argLine = '"{0}" {1} {2} - < "{3}"' -f
            $cliExe, ($CliVerb -join " "), ($approvalArgs -join " "), $promptFile

            & cmd.exe /c $argLine
            $agentExit = $LASTEXITCODE

            if ($agentExit -ne 0) {
                Write-Host "ERROR: '$CliTool' exited with code $agentExit." -ForegroundColor Red
                if ($agentExit -eq 2) {
                    # Deterministic usage error; retrying cannot help.
                    $usageError = $true
                    Write-Host "CLI usage error. Run this by hand to see the real message:" -ForegroundColor Red
                    Write-Host "  $argLine" -ForegroundColor Red
                }
                else {
                    $feedback = "The agent process exited with code $agentExit."
                }
                if ($usageError) { break }
                continue
            }

            $result = Invoke-Verification
            if ($result.Exit -eq 0) {
                $verified = $true
                break
            }

            Write-Host ("VERIFICATION FAILED (attempt {0}/{1})." -f $attempt, $MaxAttempts) -ForegroundColor Red
            if ($attempt -lt $MaxAttempts) {
                Write-Host "Retrying with the failure output fed back to the agent..." -ForegroundColor Yellow
            }
            $feedback = $result.Output
        }

        if (-not $verified) {
            $reason = if ($usageError) { "CLI usage error" } else { "verification failed" }
            Write-Host ("Giving up after {0} attempt(s): {1}. Marking [BLOCKED]..." -f $MaxAttempts, $reason) -ForegroundColor Red
            if (-not (Set-TaskBlocked $taskLine)) {
                Write-Host "Could not locate the task line to mark [BLOCKED]." -ForegroundColor Red
            }
            break
        }

        # Re-read: the agent may have already ticked the box or reworded the line.
        $doc = Read-Tasks
        if ($doc.Lines[$idx] -match "^\s*-\s*\[\s*\]") {
            $doc.Lines[$idx] = $doc.Lines[$idx] -replace "^\s*-\s*\[\s*\]", "- [x]"
            Write-Tasks $doc
            Write-Host "Marked task as completed [x] in tasks.md." -ForegroundColor Green
        }
        else {
            Write-Host "Task already marked by agent; leaving tasks.md as-is." -ForegroundColor Gray
        }

        # Guard: if the next pending task is still this line, stop instead of looping.
        $after = Read-Tasks
        if ((Find-NextTask $after.Lines) -eq $idx) {
            Write-Host "No progress detected; stopping to avoid an infinite loop." -ForegroundColor Red
            break
        }
    }
}
finally {
    Remove-Item $promptFile -Force -ErrorAction SilentlyContinue
}
