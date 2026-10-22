$ErrorActionPreference = 'Stop'
$enc = [System.Text.UTF8Encoding]::new($false)
$old = ([System.IO.File]::ReadAllText('tasks.md.bak', $enc)) -split "`n"
$new = ([System.IO.File]::ReadAllText('tasks.md',     $enc)) -split "`n"

function Get-TaskBlocks([string[]]$lines) {
    $res = @{}
    $order = New-Object 'System.Collections.Generic.List[string]'
    $inFence = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^\s*(```|~~~)') { $inFence = -not $inFence; continue }
        if ($inFence) { continue }
        if ($lines[$i] -match '^- \[([ x])\]') {
            $id = [regex]::Match($lines[$i], '\*\*([\d.]+)\*\*').Groups[1].Value
            $blk = New-Object 'System.Collections.Generic.List[string]'
            $blk.Add($lines[$i])
            $j = $i + 1
            while ($j -lt $lines.Count) {
                if ($lines[$j] -match '^- \[[ x]\]') { break }
                if ($lines[$j] -match '^\s*(```|~~~)') { break }
                if ($lines[$j] -match '^#') { break }
                if ($lines[$j].Trim() -eq '') {
                    $k = $j
                    while ($k -lt $lines.Count -and $lines[$k].Trim() -eq '') { $k++ }
                    if ($k -ge $lines.Count -or ($lines[$k] -notmatch '^\s')) { break }
                    $j = $k
                }
                $blk.Add($lines[$j]); $j++
            }
            $res[$id] = ($blk -join "`n")
            $order.Add($id)
            $i = $j - 1
        }
    }
    return @{ Blocks = $res; Order = $order }
}

$ob = Get-TaskBlocks $old
$nb = Get-TaskBlocks $new
$fail = 0

if (($ob.Order -join ',') -ne ($nb.Order -join ',')) { "FAIL: task order changed"; $fail++ }
else { "PASS: $($nb.Order.Count) task ids present in identical order" }

$EMD = [char]0x2014
$END = [char]0x2013

$pendSame = 0
foreach ($id in $ob.Order) {
    if ($ob.Blocks[$id] -match '^- \[ \]') {
        if ($ob.Blocks[$id] -ne $nb.Blocks[$id]) { "FAIL: pending task $id changed"; $fail++ }
        else { $pendSame++ }
    }
}
"PASS: $pendSame pending task blocks byte-identical (title, sub-tasks, Verify line, instructions)"

$compOk = 0
foreach ($id in $ob.Order) {
    if ($ob.Blocks[$id] -match '^- \[x\]') {
        $oLines = $ob.Blocks[$id] -split "`n"
        $nLines = $nb.Blocks[$id] -split "`n"
        $vi = -1
        for ($j = 0; $j -lt $oLines.Count; $j++) { if ($oLines[$j] -match '^\s*Verify:') { $vi = $j; break } }
        if ($vi -lt 0) { "FAIL: $id has no Verify line"; $fail++; continue }
        $oDef = ($oLines[0..$vi]) -join "`n"
        $nDef = ($nLines[0..$vi]) -join "`n"
        if ($oDef -ne $nDef) { "FAIL: completed task $id definition changed"; $fail++; continue }
        $nRest = @()
        if ($nLines.Count -gt ($vi + 1)) { $nRest = @($nLines[($vi + 1)..($nLines.Count - 1)] | Where-Object { $_.Trim() -ne '' }) }
        if ($nRest.Count -gt 1) { "FAIL: task $id kept $($nRest.Count) trailing lines"; $fail++; continue }
        if ($nRest.Count -eq 1) {
            $lead = $nRest[0].TrimStart().Substring(0, 1)
            if ($lead -ne [string]$EMD -and $lead -ne [string]$END -and $lead -ne '-') {
                "FAIL: task $id trailing line is not a summary"; $fail++; continue
            }
        }
        $compOk++
    }
}
"PASS: $compOk completed task definitions byte-identical through the Verify line, each with at most one summary line"

$oldEx = ($old[($old.Count - 14)..($old.Count - 1)]) -join "`n"
$newEx = ($new[($new.Count - 14)..($new.Count - 1)]) -join "`n"
if ($oldEx.Trim() -eq $newEx.Trim()) { "PASS: trailing fenced markdown example unchanged" }
else { "FAIL: trailing fenced example changed"; $fail++ }

$bytes = [System.IO.File]::ReadAllBytes('tasks.md')
$hasBom = ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$crCount = 0
foreach ($x in $bytes) { if ($x -eq 13) { $crCount++ } }
"PASS: no BOM=$(-not $hasBom), CR bytes=$crCount, trailing newline=$($bytes[$bytes.Length - 1] -eq 10)"
if ($hasBom -or $crCount -ne 0) { $fail++ }

if ($fail -eq 0) { "ALL CHECKS PASSED" } else { "$fail CHECK(S) FAILED" }
