$ErrorActionPreference = 'Stop'
$LF = [string][char]10
$strict = [System.Text.UTF8Encoding]::new($false, $true)
$bytes = [System.IO.File]::ReadAllBytes('HANDOVER.md')
$text = $strict.GetString($bytes)
$new = $text -split $LF
$oldText = [System.IO.File]::ReadAllText('HANDOVER.md.bak', [System.Text.UTF8Encoding]::new($false))
$old = $oldText -split $LF
$fail = 0

"lines: $($old.Count) -> $($new.Count)"
"bytes: $((Get-Item HANDOVER.md.bak).Length) -> $($bytes.Length)"

$bom = ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
$cr = 0
foreach ($x in $bytes) { if ($x -eq 13) { $cr++ } }
$repl = ([regex]::Matches($text, [string][char]0xFFFD)).Count
"valid UTF-8 = True; BOM = $bom; CR bytes = $cr; U+FFFD = $repl; trailing LF = $($bytes[$bytes.Length-1] -eq 10)"
if ($bom -or $cr -ne 0 -or $repl -ne 0) { $fail++ }

$want = @('### Last Completed Task', '### Current State & Key Decisions', '### Known Issues / Blockers', '### Immediate Next Step')
$idx = @()
foreach ($h in $want) {
    $p = [Array]::IndexOf($new, $h)
    $idx += $p
    if ($p -lt 0) { "FAIL: missing section '$h'"; $fail++ }
}
for ($i = 1; $i -lt $idx.Count; $i++) { if ($idx[$i] -le $idx[$i - 1]) { "FAIL: sections out of order"; $fail++ } }
"PASS: 4 protocol sections present and ordered at lines $($idx -join ', ')"

$bullets = @($new | Where-Object { $_ -match '^- ' })
$cont = @($new | Where-Object { $_ -match '^  [a-z`(]' })
"bullet lines: $($bullets.Count); wrapped continuation lines: $($cont.Count)"
if ($cont.Count -gt 0) { "FAIL: $($cont.Count) wrapped continuations remain"; $fail++ }

$first = $idx[0]
$second = $idx[1]
$lct = $new[$first..($second - 1)]
$others = @($lct | Select-String -Pattern '\*\*Task [0-9]')
"older task writeup headers left in Last Completed Task: $($others.Count)"
if ($others.Count -gt 0) { $others | ForEach-Object { "      $($_.Line)"; $fail++ } }
if (-not ($lct -match '4\.6')) { "FAIL: 4.6 not present"; $fail++ }

if (-not ($text -match '1710 passed, 1 failed')) { "FAIL: red-suite state not recorded"; $fail++ }
if (-not ($text -match 'BLOCKED')) { "FAIL: 4.7 BLOCKED state not recorded"; $fail++ }
if (-not ($text -match 'infer_format')) { "FAIL: infer_format not recorded"; $fail++ }
"PASS: active blocker recorded (4.7 half-built, suite red)"

if ($text -match 'The suite is green') { "FAIL: stale green-suite claim survives"; $fail++ }
"PASS: stale 'The suite is green' claim removed"

if ($fail -eq 0) { "ALL CHECKS PASSED" } else { "$fail CHECK(S) FAILED" }
