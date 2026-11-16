# hdrive_move_gate.ps1 - Windows-side move-only safety gate (fail-closed)
#
# Supports only mkdir + move. No delete, copy, exec, overwrite, or cross-volume move.
# A FAIL action must be reviewed one-by-one by a separate SAFETY identity.
# All state is JSON files under <RunRoot>\safety.
#
# Tested with Windows PowerShell 5.1. Use -File to invoke this script.

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('init','propose','gate','review','human-approve','run','run-batch','status')]
    [string]$Command,

    [string]$RunRoot,
    [string]$Root,
    [string]$StorageRoot,
    [string]$PendingRoot,
    [string]$ProtectedManifest,
    [string[]]$SafetyReviewer = @(),
    [string[]]$HumanApprover = @(),

    [string]$ActionFile,
    [string]$BatchFile,
    [string]$Agent,
    [string]$Action,
    [string]$Reviewer,
    [string]$Verdict,
    [string]$Digest,
    [string]$Reason,
    [string]$Evidence,
    [string]$Approver,
    [switch]$AllowRootStorage,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$script:Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
try { [Console]::OutputEncoding = $script:Utf8NoBom } catch { }

$script:SystemNames = @(
    '$RECYCLE.BIN','System Volume Information','$WinREAgent','Recovery','Windows',
    'Program Files','Program Files (x86)','ProgramData','PerfLogs','pagefile.sys',
    'hiberfil.sys','swapfile.sys','lost+found'
)
$script:ReservedNamePattern = '^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$'
$script:SupportedOps = @('mkdir','move')

function Get-Ext([string]$Path) {
    if ($Path.StartsWith('\\?\UNC\')) { return $Path }
    if ($Path.StartsWith('\\?\')) { return $Path }
    if ($Path.StartsWith('\\')) { return '\\?\UNC\' + $Path.Substring(2) }
    return '\\?\' + $Path
}

function Ensure-Dir([string]$Path) {
    [IO.Directory]::CreateDirectory((Get-Ext $Path)) | Out-Null
}

function Test-FileExists([string]$Path) { return [IO.File]::Exists((Get-Ext $Path)) }
function Test-DirExists([string]$Path) { return [IO.Directory]::Exists((Get-Ext $Path)) }
function Test-AnyExists([string]$Path) { return (Test-FileExists $Path) -or (Test-DirExists $Path) }

function Read-JsonFile([string]$Path) {
    if (-not (Test-FileExists $Path)) { throw "JSON file not found: $Path" }
    $raw = [IO.File]::ReadAllText((Get-Ext $Path), $script:Utf8NoBom)
    return ($raw | ConvertFrom-Json)
}

function Write-NewJson([string]$Path, $Obj) {
    if (Test-AnyExists $Path) { throw "Refusing to overwrite existing safety ledger: $Path" }
    $parent = Split-Path -Parent $Path
    if ($parent) { Ensure-Dir $parent }
    $json = $Obj | ConvertTo-Json -Depth 30
    [IO.File]::WriteAllText((Get-Ext $Path), $json, $script:Utf8NoBom)
}

function Write-JsonOverwrite([string]$Path, $Obj) {
    $parent = Split-Path -Parent $Path
    if ($parent) { Ensure-Dir $parent }
    $json = $Obj | ConvertTo-Json -Depth 30
    [IO.File]::WriteAllText((Get-Ext $Path), $json, $script:Utf8NoBom)
}

function Normalize-Path([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'Path must not be empty' }
    if ($Path -match '[\*\?]') { throw "Wildcards are not allowed: $Path" }
    if ($Path.StartsWith('\\?\')) { throw "Extended paths are internal only: $Path" }
    if ($Path -notmatch '^[A-Za-z]:\\') { throw "Path must be an absolute drive path: $Path" }
    $tail = $Path.Substring(2)
    if ($tail.Contains(':')) { throw "Alternate data streams are not allowed: $Path" }
    $full = [IO.Path]::GetFullPath($Path)
    if ($full.Length -gt 3 -and $full.EndsWith('\')) { $full = $full.TrimEnd('\') }
    foreach ($part in ($full -split '\\')) {
        if ($part -match $script:ReservedNamePattern) { throw "Reserved Windows name: $Path" }
    }
    return $full
}

function Get-RootCompare([string]$Path) {
    $p = (Normalize-Path $Path).TrimEnd('\')
    return $p
}

function Test-PathUnder([string]$Child, [string]$Parent) {
    $c = (Normalize-Path $Child).TrimEnd('\')
    $p = (Normalize-Path $Parent).TrimEnd('\')
    if ($c.Equals($p, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    return $c.StartsWith($p + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Get-RelativePath([string]$Child, [string]$Parent) {
    $c = (Normalize-Path $Child).TrimEnd('\')
    $p = (Normalize-Path $Parent).TrimEnd('\')
    if ($c.Equals($p, [StringComparison]::OrdinalIgnoreCase)) { return '' }
    if (-not $c.StartsWith($p + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Path is not under parent: $Child"
    }
    return $c.Substring($p.Length + 1)
}

function Get-ParentPath([string]$Path) {
    $p = Normalize-Path $Path
    $idx = $p.LastIndexOf('\')
    if ($idx -lt 0) { return $null }
    if ($idx -eq 2) { return $p.Substring(0, 3) }
    return $p.Substring(0, $idx)
}

function Test-ReparseChain([string]$Path, [string]$RootPath) {
    $root = (Normalize-Path $RootPath).TrimEnd('\')
    $rel = Get-RelativePath $Path $RootPath
    $cur = $root
    if (Test-AnyExists $cur) {
        $attrs = [IO.File]::GetAttributes((Get-Ext $cur))
        if (($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return $true }
    }
    if ([string]::IsNullOrEmpty($rel)) { return $false }
    foreach ($part in ($rel -split '\\')) {
        $cur = $cur + '\' + $part
        if (Test-AnyExists $cur) {
            $attrs = [IO.File]::GetAttributes((Get-Ext $cur))
            if (($attrs -band [IO.FileAttributes]::ReparsePoint) -ne 0) { return $true }
        }
    }
    return $false
}

function Test-SystemRelativePath([string]$Rel) {
    foreach ($part in ($Rel -split '\\')) {
        if ([string]::IsNullOrWhiteSpace($part)) { continue }
        if ($part.StartsWith('$')) { return $true }
        if ($part.StartsWith('.Trash-', [StringComparison]::OrdinalIgnoreCase)) { return $true }
        foreach ($s in $script:SystemNames) {
            if ($part.Equals($s, [StringComparison]::OrdinalIgnoreCase)) { return $true }
        }
    }
    return $false
}

function Test-ProtectedPath([string]$Path, $Config) {
    $root = [string]$Config.root
    $rel = Get-RelativePath $Path $root
    if ([string]::IsNullOrEmpty($rel)) { return 'H drive root itself is protected' }
    $parts = @($rel -split '\\')
    $top = [string]$parts[0]
    foreach ($p in @($Config.protected.toplevel)) {
        if ($top.Equals([string]$p, [StringComparison]::OrdinalIgnoreCase)) {
            return "Protected top-level path: $p"
        }
    }
    if ($parts.Count -eq 1) {
        $ext = [IO.Path]::GetExtension($top)
        foreach ($e in @($Config.protected.root_extensions)) {
            if ($ext.Equals([string]$e, [StringComparison]::OrdinalIgnoreCase)) {
                return "Protected root file extension: $e"
            }
        }
        foreach ($f in @($Config.protected.root_files)) {
            if ($top.Equals([string]$f, [StringComparison]::OrdinalIgnoreCase)) {
                return "Protected root file: $f"
            }
        }
    }
    return $null
}

function Get-ActionDigest($Proposal) {
    $op = if ($null -eq $Proposal.op) { '' } else { [string]$Proposal.op }
    $src = if ($null -eq $Proposal.src) { '' } else { [string]$Proposal.src }
    $dst = if ($null -eq $Proposal.dst) { '' } else { [string]$Proposal.dst }
    $intent = if ($null -eq $Proposal.intent) { '' } else { [string]$Proposal.intent }
    $text = $op + "`n" + $src + "`n" + $dst + "`n" + $intent
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($text)
        $hash = $sha.ComputeHash($bytes)
        return (-join ($hash | ForEach-Object { $_.ToString('x2') }))
    } finally { $sha.Dispose() }
}

function Get-ItemInfo([string]$Path) {
    if (Test-FileExists $Path) {
        $fi = New-Object IO.FileInfo((Get-Ext $Path))
        return [ordered]@{
            kind = 'file'
            length = [long]$fi.Length
            last_write_utc = $fi.LastWriteTimeUtc.ToString('o')
            attributes = [string]$fi.Attributes
        }
    }
    if (Test-DirExists $Path) {
        $di = New-Object IO.DirectoryInfo((Get-Ext $Path))
        return [ordered]@{
            kind = 'dir'
            length = $null
            last_write_utc = $di.LastWriteTimeUtc.ToString('o')
            attributes = [string]$di.Attributes
        }
    }
    return $null
}

function New-Reason([string]$Code, [string]$Message, [string]$Risk) {
    return [ordered]@{ code = $Code; message = $Message; risk = $Risk }
}

function Evaluate-Action($Action, $Config) {
    $p = $Action.proposal
    $reasons = New-Object System.Collections.ArrayList
    $hardBlock = $false
    $srcInfo = $null

    if ([string]::IsNullOrWhiteSpace([string]$p.intent)) {
        [void]$reasons.Add((New-Reason 'INTENT_MISSING' 'intent must not be empty' 'yellow'))
    }
    if ([string]::IsNullOrWhiteSpace([string]$p.op)) {
        [void]$reasons.Add((New-Reason 'OP_MISSING' 'op must not be empty' 'red'))
        $hardBlock = $true
    } elseif ($script:SupportedOps -notcontains [string]$p.op) {
        [void]$reasons.Add((New-Reason 'UNKNOWN_OP' ("unsupported op: " + [string]$p.op) 'red'))
        $hardBlock = $true
    }

    if (-not $hardBlock -and [string]$p.op -eq 'mkdir') {
        try {
            $dst = Normalize-Path ([string]$p.dst)
            if (-not (Test-PathUnder $dst $Config.storage_root)) {
                [void]$reasons.Add((New-Reason 'OUTSIDE_STORAGE' "mkdir dst must be under storage root: $dst" 'red'))
                $hardBlock = $true
            }
            if (Test-ProtectedPath $dst $Config) {
                [void]$reasons.Add((New-Reason 'PROTECTED_PATH' (Test-ProtectedPath $dst $Config) 'red'))
                $hardBlock = $true
            }
            if (Test-SystemRelativePath (Get-RelativePath $dst $Config.root)) {
                [void]$reasons.Add((New-Reason 'SYSTEM_PATH' "system/recycle path: $dst" 'red'))
                $hardBlock = $true
            }
            if (Test-ReparseChain $dst $Config.root) {
                [void]$reasons.Add((New-Reason 'REPARSE_PATH' "reparse point in path: $dst" 'red'))
                $hardBlock = $true
            }
            $parent = Get-ParentPath $dst
            if (-not $parent -or -not (Test-DirExists $parent)) {
                [void]$reasons.Add((New-Reason 'PARENT_MISSING' "destination parent does not exist: $parent" 'yellow'))
            }
            if (Test-AnyExists $dst) {
                [void]$reasons.Add((New-Reason 'DEST_EXISTS' "destination already exists: $dst" 'yellow'))
            }
            if ($dst.Length -gt 240) {
                [void]$reasons.Add((New-Reason 'LONG_PATH_REVIEW' "path length $($dst.Length) requires safety review (extended path supported)" 'yellow'))
            }
        } catch {
            [void]$reasons.Add((New-Reason 'PATH_INVALID' $_.Exception.Message 'red'))
            $hardBlock = $true
        }
    } elseif (-not $hardBlock -and [string]$p.op -eq 'move') {
        try {
            $src = Normalize-Path ([string]$p.src)
            $dst = Normalize-Path ([string]$p.dst)
            if (-not (Test-PathUnder $src $Config.root)) {
                [void]$reasons.Add((New-Reason 'SRC_OUTSIDE_ROOT' "src must be under H root: $src" 'red'))
                $hardBlock = $true
            }
            if (-not (Test-PathUnder $dst $Config.storage_root)) {
                [void]$reasons.Add((New-Reason 'DST_OUTSIDE_STORAGE' "dst must be under storage root: $dst" 'red'))
                $hardBlock = $true
            }
            $dstRel = Get-RelativePath $dst $Config.storage_root
            if ([string]::IsNullOrEmpty($dstRel)) {
                [void]$reasons.Add((New-Reason 'DST_IS_STORAGE_ROOT' 'dst cannot be the storage root itself' 'red'))
                $hardBlock = $true
            }
            if ($src.Equals($dst, [StringComparison]::OrdinalIgnoreCase)) {
                [void]$reasons.Add((New-Reason 'SAME_SRC_DST' 'src and dst are identical' 'red'))
                $hardBlock = $true
            }
            $srcProtected = Test-ProtectedPath $src $Config
            if ($srcProtected) {
                [void]$reasons.Add((New-Reason 'PROTECTED_PATH' $srcProtected 'red'))
                $hardBlock = $true
            }
            $dstProtected = Test-ProtectedPath $dst $Config
            if ($dstProtected) {
                [void]$reasons.Add((New-Reason 'PROTECTED_DST' $dstProtected 'red'))
                $hardBlock = $true
            }
            if (Test-SystemRelativePath (Get-RelativePath $src $Config.root)) {
                [void]$reasons.Add((New-Reason 'SYSTEM_PATH' "system/recycle path: $src" 'red'))
                $hardBlock = $true
            }
            if (Test-ReparseChain $src $Config.root) {
                [void]$reasons.Add((New-Reason 'SRC_REPARSE' "reparse point in source path: $src" 'red'))
                $hardBlock = $true
            }
            $parent = Get-ParentPath $dst
            if (Test-ReparseChain $parent $Config.root) {
                [void]$reasons.Add((New-Reason 'DST_REPARSE' "reparse point in destination path: $parent" 'red'))
                $hardBlock = $true
            }
            if (-not (Test-AnyExists $src)) {
                [void]$reasons.Add((New-Reason 'SRC_MISSING' "source does not exist: $src" 'yellow'))
            } else {
                $srcInfo = Get-ItemInfo $src
            }
            if (Test-AnyExists $dst) {
                [void]$reasons.Add((New-Reason 'DEST_EXISTS' "destination already exists: $dst" 'yellow'))
            }
            if (-not $parent -or -not (Test-DirExists $parent)) {
                [void]$reasons.Add((New-Reason 'PARENT_MISSING' "destination parent does not exist: $parent" 'yellow'))
            }
            if ($src.Length -gt 240 -or $dst.Length -gt 240) {
                [void]$reasons.Add((New-Reason 'LONG_PATH_REVIEW' "path length src=$($src.Length) dst=$($dst.Length) requires safety review (extended path supported)" 'yellow'))
            }
        } catch {
            [void]$reasons.Add((New-Reason 'PATH_INVALID' $_.Exception.Message 'red'))
            $hardBlock = $true
        }
    }

    $status = if ($reasons.Count -eq 0) { 'PASS' } else { 'FAIL' }
    $hasRed = ($hardBlock -or (@($reasons | Where-Object { $_.risk -eq 'red' }).Count -gt 0))
    $risk = if ($status -eq 'PASS') { 'green' } elseif ($hasRed) { 'red' } else { 'yellow' }
    return [ordered]@{
        action_id = [string]$Action.id
        action_digest = [string]$Action.digest
        gate_version = 1
        status = $status
        risk = $risk
        executable = (-not $hardBlock)
        review_required = ($status -eq 'FAIL')
        reasons = @($reasons)
        src_info = $srcInfo
        evaluated_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    }
}

function Get-Config([string]$RunRootPath) {
    $p = Join-Path $RunRootPath 'safety\config.json'
    return Read-JsonFile $p
}

function Get-Action([string]$RunRootPath, [string]$ActionId) {
    if ($ActionId -notmatch '^ACT-\d{4,}$') { throw "Invalid action id: $ActionId" }
    $p = Join-Path $RunRootPath ("safety\actions\$ActionId.json")
    $a = Read-JsonFile $p
    $actual = Get-ActionDigest $a.proposal
    if ($actual -ne [string]$a.digest) { throw "Action digest mismatch for $ActionId" }
    return $a
}

function Get-Gate([string]$RunRootPath, [string]$ActionId) {
    $p = Join-Path $RunRootPath ("safety\gates\$ActionId.json")
    $g = Read-JsonFile $p
    $a = Get-Action $RunRootPath $ActionId
    if ([string]$g.action_digest -ne [string]$a.digest) { throw "Gate digest mismatch for $ActionId" }
    return $g
}

function Get-Review([string]$RunRootPath, [string]$ActionId) {
    $p = Join-Path $RunRootPath ("safety\reviews\$ActionId.json")
    if (-not (Test-FileExists $p)) { return $null }
    return Read-JsonFile $p
}

function Get-Human([string]$RunRootPath, [string]$ActionId) {
    $p = Join-Path $RunRootPath ("safety\human-approvals\$ActionId.json")
    if (-not (Test-FileExists $p)) { return $null }
    return Read-JsonFile $p
}

function Get-Execution([string]$RunRootPath, [string]$ActionId) {
    $p = Join-Path $RunRootPath ("safety\executions\$ActionId.json")
    if (-not (Test-FileExists $p)) { return $null }
    return Read-JsonFile $p
}

function Test-ContainsName($List, [string]$Name) {
    foreach ($x in @($List)) {
        if ([string]$x -ieq $Name) { return $true }
    }
    return $false
}

function Init-Gate {
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    if ([string]::IsNullOrWhiteSpace($Root)) { throw '-Root is required' }
    if ([string]::IsNullOrWhiteSpace($StorageRoot)) { throw '-StorageRoot is required' }
    if ([string]::IsNullOrWhiteSpace($PendingRoot)) { throw '-PendingRoot is required' }
    if ([string]::IsNullOrWhiteSpace($ProtectedManifest)) { throw '-ProtectedManifest is required' }
    if (@($SafetyReviewer).Count -eq 0) { throw 'At least one -SafetyReviewer is required' }

    $configPath = Join-Path $RunRoot 'safety\config.json'
    if (Test-AnyExists $configPath) { throw "Gate already initialized: $configPath" }

    $rootNorm = Normalize-Path $Root
    $storageNorm = Normalize-Path $StorageRoot
    $pendingNorm = Normalize-Path $PendingRoot
    if (-not (Test-DirExists $rootNorm)) { throw "Root does not exist: $rootNorm" }
    if (-not (Test-PathUnder $storageNorm $rootNorm)) {
        throw 'StorageRoot must be inside Root'
    }
    if ($storageNorm.TrimEnd('\') -ieq $rootNorm.TrimEnd('\') -and -not $AllowRootStorage) {
        throw 'StorageRoot equals Root; pass -AllowRootStorage for explicit root-level destination mode'
    }
    if (-not (Test-PathUnder $pendingNorm $storageNorm) -or $pendingNorm.TrimEnd('\') -ieq $storageNorm.TrimEnd('\')) {
        throw 'PendingRoot must be inside StorageRoot and must not equal StorageRoot'
    }
    if (-not (Test-FileExists $ProtectedManifest)) { throw "ProtectedManifest not found: $ProtectedManifest" }
    $prot = Read-JsonFile $ProtectedManifest

    $reviewers = @($SafetyReviewer | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)
    $approvers = @($HumanApprover | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -Unique)
    foreach ($r in $reviewers) {
        foreach ($a in $approvers) {
            if ([string]$r -ieq [string]$a) { throw "SafetyReviewer and HumanApprover must be different: $r" }
        }
    }

    $config = [ordered]@{
        gate_version = 1
        root = $rootNorm
        storage_root = $storageNorm
        pending_root = $pendingNorm
        safety_reviewers = @($reviewers)
        human_approvers = @($approvers)
        protected = [ordered]@{
            toplevel = @($prot.protected_toplevel)
            root_extensions = @($prot.protected_root_extensions)
            root_files = @($prot.protected_root_files)
        }
        created_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        mode = 'move-only'
        allow_root_storage = [bool]$AllowRootStorage
        notes = 'No delete/copy/exec. FAIL actions require one-by-one SAFETY review.'
    }
    foreach ($sub in @('actions','gates','reviews','human-approvals','executions')) {
        Ensure-Dir (Join-Path $RunRoot ("safety\" + $sub))
    }
    Write-NewJson $configPath $config
    Write-Host "[OK] gate initialized: $configPath"
}

function Propose-Actions {
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    if ([string]::IsNullOrWhiteSpace($ActionFile)) { throw '-ActionFile is required' }
    if ([string]::IsNullOrWhiteSpace($Agent)) { throw '-Agent is required' }
    [void](Get-Config $RunRoot)
    if (-not (Test-FileExists $ActionFile)) { throw "ActionFile not found: $ActionFile" }

    $lines = [IO.File]::ReadAllLines((Get-Ext $ActionFile), $script:Utf8NoBom)
    $parsed = New-Object System.Collections.ArrayList
    $lineNo = 0
    foreach ($line in $lines) {
        $lineNo++
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try { $obj = $line | ConvertFrom-Json } catch { throw "Invalid JSON on line ${lineNo}: $($_.Exception.Message)" }
        if ($null -eq $obj) { throw "Empty action on line $lineNo" }
        if ([string]::IsNullOrWhiteSpace([string]$obj.op)) { throw "Missing op on line $lineNo" }
        if ([string]::IsNullOrWhiteSpace([string]$obj.intent)) { throw "Missing intent on line $lineNo" }
        if ($obj.PSObject.Properties.Name -contains 'id' -or $obj.PSObject.Properties.Name -contains 'digest') {
            throw "Do not supply id/digest in action file (line $lineNo)"
        }
        [void]$parsed.Add($obj)
    }
    if ($parsed.Count -eq 0) { throw 'No actions found' }

    $actionsDir = Join-Path $RunRoot 'safety\actions'
    $maxNum = 0
    foreach ($f in [IO.Directory]::GetFiles((Get-Ext $actionsDir), 'ACT-*.json')) {
        $name = [IO.Path]::GetFileNameWithoutExtension($f)
        if ($name -match '^ACT-(\d+)$') { $maxNum = [Math]::Max($maxNum, [int]$Matches[1]) }
    }
    $ids = @()
    for ($i=0; $i -lt $parsed.Count; $i++) {
        $num = $maxNum + $i + 1
        $id = ('ACT-{0:D4}' -f $num)
        $p = $parsed[$i]
        $proposal = [ordered]@{
            op = [string]$p.op
            intent = [string]$p.intent
            src = [string]$p.src
            dst = [string]$p.dst
        }
        $digest = Get-ActionDigest $proposal
        $action = [ordered]@{
            id = $id
            requested_by = $Agent
            created_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
            proposal = $proposal
            digest = $digest
        }
        Write-NewJson (Join-Path $actionsDir ($id + '.json')) $action
        $ids += $id
    }
    Write-Host ("[OK] proposed {0} action(s): {1}" -f $ids.Count, ($ids -join ', '))
}

function Gate-Actions {
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    $config = Get-Config $RunRoot
    $actionsDir = Join-Path $RunRoot 'safety\actions'
    $results = @()
    foreach ($f in ([IO.Directory]::GetFiles((Get-Ext $actionsDir), 'ACT-*.json') | Sort-Object)) {
        $id = [IO.Path]::GetFileNameWithoutExtension($f)
        $gateFile = Join-Path $RunRoot ("safety\gates\$id.json")
        if (Test-FileExists $gateFile) {
            $results += (Read-JsonFile $gateFile)
            continue
        }
        $a = Get-Action $RunRoot $id
        $g = Evaluate-Action $a $config
        Write-NewJson $gateFile $g
        $results += $g
    }
    $pass = @($results | Where-Object { $_.status -eq 'PASS' }).Count
    $fail = @($results | Where-Object { $_.status -eq 'FAIL' }).Count
    Write-Host "[OK] gate complete: PASS=$pass FAIL=$fail"
    foreach ($r in $results) {
        $codes = (@($r.reasons | ForEach-Object { $_.code }) -join ',')
        if ([string]::IsNullOrEmpty($codes)) { $codes = '-' }
        Write-Host ("  {0}  {1}  risk={2}  digest={3}  reasons={4}" -f $r.action_id, $r.status, $r.risk, $r.action_digest, $codes)
    }
}

function Review-Action {
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    if ([string]::IsNullOrWhiteSpace($Action)) { throw '-Action is required' }
    if ([string]::IsNullOrWhiteSpace($Reviewer)) { throw '-Reviewer is required' }
    if (($Verdict -ne 'approve') -and ($Verdict -ne 'reject')) { throw '-Verdict must be approve or reject' }
    if ([string]::IsNullOrWhiteSpace($Reason) -or $Reason.Length -lt 8) { throw 'Reason must be at least 8 characters' }
    if ([string]::IsNullOrWhiteSpace($Evidence)) { throw 'Evidence must not be empty' }

    $config = Get-Config $RunRoot
    if (-not (Test-ContainsName $config.safety_reviewers $Reviewer)) { throw "$Reviewer is not in safety_reviewers" }
    $a = Get-Action $RunRoot $Action
    if ([string]$a.requested_by -ieq $Reviewer) { throw 'Safety reviewer cannot review own action' }
    $g = Get-Gate $RunRoot $Action
    if ([string]$g.status -ne 'FAIL') { throw 'Only FAIL actions require safety review' }
    if ([string]$g.action_digest -ne [string]$a.digest) { throw 'Gate digest mismatch' }
    if ([string]$Digest -ne [string]$a.digest) { throw 'Provided digest does not match action digest' }
    $reviewFile = Join-Path $RunRoot ("safety\reviews\$Action.json")
    if (Test-FileExists $reviewFile) { throw "Review already exists: $Action" }

    $rec = [ordered]@{
        action_id = $Action
        action_digest = [string]$a.digest
        reviewer = $Reviewer
        verdict = $Verdict
        reason = $Reason
        evidence = $Evidence
        gate_risk = [string]$g.risk
        reviewed_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    }
    Write-NewJson $reviewFile $rec
    Write-Host "[OK] safety review recorded: $Action $Verdict"
}

function Human-Approve {
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    if ([string]::IsNullOrWhiteSpace($Action)) { throw '-Action is required' }
    if ([string]::IsNullOrWhiteSpace($Approver)) { throw '-Approver is required' }
    if ([string]::IsNullOrWhiteSpace($Reason) -or $Reason.Length -lt 8) { throw 'Reason must be at least 8 characters' }
    $config = Get-Config $RunRoot
    if (-not (Test-ContainsName $config.human_approvers $Approver)) { throw "$Approver is not in human_approvers" }
    $a = Get-Action $RunRoot $Action
    $g = Get-Gate $RunRoot $Action
    if ([string]$g.risk -ne 'red') { throw 'Only red actions require human approval' }
    if (-not [bool]$g.executable) { throw 'Action is hard-blocked and cannot be approved' }
    $r = Get-Review $RunRoot $Action
    if (-not $r -or [string]$r.verdict -ne 'approve') { throw 'Safety review approve is required first' }
    if ([string]$r.action_digest -ne [string]$a.digest) { throw 'Safety review digest mismatch' }
    if ([string]$r.reviewer -ieq $Approver) { throw 'Human approver must differ from safety reviewer' }
    if ([string]$a.requested_by -ieq $Approver) { throw 'Human approver must differ from requester' }
    if ([string]$Digest -ne [string]$a.digest) { throw 'Provided digest does not match action digest' }
    $file = Join-Path $RunRoot ("safety\human-approvals\$Action.json")
    if (Test-FileExists $file) { throw "Human approval already exists: $Action" }
    $rec = [ordered]@{
        action_id = $Action
        action_digest = [string]$a.digest
        approver = $Approver
        reason = $Reason
        safety_reviewer = [string]$r.reviewer
        approved_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    }
    Write-NewJson $file $rec
    Write-Host "[OK] human approval recorded: $Action"
}

function Test-Runnable($Action, $Config) {
    $p = $Action.proposal
    $op = [string]$p.op
    if ($op -eq 'mkdir') {
        $dst = Normalize-Path ([string]$p.dst)
        if (-not (Test-PathUnder $dst $Config.storage_root)) { return 'dst is outside storage root' }
        if (Test-ProtectedPath $dst $Config) { return 'dst is protected' }
        if (Test-SystemRelativePath (Get-RelativePath $dst $Config.root)) { return 'dst is a system path' }
        if (Test-ReparseChain $dst $Config.root) { return 'dst contains reparse point' }
        if (Test-AnyExists $dst) { return 'destination already exists' }
        $parent = Get-ParentPath $dst
        if (-not $parent -or -not (Test-DirExists $parent)) { return 'destination parent missing' }
        return $null
    }
    if ($op -eq 'move') {
        $src = Normalize-Path ([string]$p.src)
        $dst = Normalize-Path ([string]$p.dst)
        if (-not (Test-PathUnder $src $Config.root)) { return 'src outside root' }
        if (-not (Test-PathUnder $dst $Config.storage_root)) { return 'dst outside storage root' }
        if ((Get-RelativePath $dst $Config.storage_root) -eq '') { return 'dst is storage root' }
        if ($src.Equals($dst, [StringComparison]::OrdinalIgnoreCase)) { return 'src equals dst' }
        if (Test-ProtectedPath $src $Config) { return 'src is protected' }
        if (Test-ProtectedPath $dst $Config) { return 'dst is protected' }
        if (Test-SystemRelativePath (Get-RelativePath $src $Config.root)) { return 'src is a system path' }
        if (Test-ReparseChain $src $Config.root) { return 'src contains reparse point' }
        if (Test-ReparseChain (Get-ParentPath $dst) $Config.root) { return 'dst contains reparse point' }
        if (-not (Test-AnyExists $src)) { return 'src missing' }
        if (Test-AnyExists $dst) { return 'destination already exists' }
        $parent = Get-ParentPath $dst
        if (-not $parent -or -not (Test-DirExists $parent)) { return 'destination parent missing' }
        return $null
    }
    return "unsupported op: $op"
}

function Invoke-RunAction {
    param([string]$ActionId, [string]$AgentName)
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    if ([string]::IsNullOrWhiteSpace($ActionId)) { throw '-Action is required' }
    if ([string]::IsNullOrWhiteSpace($AgentName)) { throw '-Agent is required' }
    $config = Get-Config $RunRoot
    if (Test-ContainsName $config.safety_reviewers $AgentName) { throw 'Safety reviewer must not execute actions' }
    if (Test-ContainsName $config.human_approvers $AgentName) { throw 'Human approver must not execute actions' }
    if (-not (Test-DirExists $config.root)) { throw "Root does not exist: $($config.root)" }

    $a = Get-Action $RunRoot $ActionId
    $g = Get-Gate $RunRoot $ActionId
    $execFile = Join-Path $RunRoot ("safety\executions\$ActionId.json")
    if (Test-FileExists $execFile) { throw "Execution record already exists: $ActionId" }
    if (-not [bool]$g.executable) { throw "Action is hard-blocked: $ActionId" }

    $review = Get-Review $RunRoot $ActionId
    $human = Get-Human $RunRoot $ActionId
    if ([string]$g.status -eq 'PASS') {
        # no extra approval needed
    } elseif ([string]$g.status -eq 'FAIL') {
        if (-not $review -or [string]$review.verdict -ne 'approve') { throw "No SAFETY approve for FAIL action: $ActionId" }
        if ([string]$review.action_digest -ne [string]$a.digest) { throw 'SAFETY review digest mismatch' }
        if ([string]$review.reviewer -ieq [string]$a.requested_by) { throw 'SAFETY reviewer is requester' }
        if ([string]$g.risk -eq 'red') {
            if (-not $human) { throw "Red action requires human approval: $ActionId" }
            if ([string]$human.action_digest -ne [string]$a.digest) { throw 'Human approval digest mismatch' }
        }
    } else { throw "Unknown gate status: $($g.status)" }

    $problem = Test-Runnable $a $config
    if ($problem) {
        $blocked = [ordered]@{
            action_id = $ActionId
            action_digest = [string]$a.digest
            agent = $AgentName
            status = 'BLOCKED_PRECHECK'
            problem = $problem
            at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        }
        Write-NewJson $execFile $blocked
        throw "Precheck failed: $problem"
    }

    $p = $a.proposal
    $op = [string]$p.op
    $src = if ($op -eq 'move') { Normalize-Path ([string]$p.src) } else { $null }
    $dst = Normalize-Path ([string]$p.dst)
    $before = if ($src) { Get-ItemInfo $src } else { $null }

    $running = [ordered]@{
        action_id = $ActionId
        action_digest = [string]$a.digest
        agent = $AgentName
        status = 'RUNNING'
        op = $op
        src = $src
        dst = $dst
        before = $before
        started_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        safety_reviewer = if ($review) { [string]$review.reviewer } else { $null }
        human_approver = if ($human) { [string]$human.approver } else { $null }
    }
    Write-NewJson $execFile $running

    $status = 'SUCCESS'
    $errorText = $null
    try {
        if ($op -eq 'mkdir') {
            [IO.Directory]::CreateDirectory((Get-Ext $dst)) | Out-Null
        } elseif ($op -eq 'move') {
            if ((Test-FileExists $src)) {
                [IO.File]::Move((Get-Ext $src), (Get-Ext $dst))
            } elseif ((Test-DirExists $src)) {
                [IO.Directory]::Move((Get-Ext $src), (Get-Ext $dst))
            } else {
                throw "Source disappeared before move: $src"
            }
        } else {
            throw "Unsupported op: $op"
        }

        if (-not (Test-AnyExists $dst)) { $status = 'EFFECT_MISMATCH'; $errorText = 'destination missing after operation' }
        if ($op -eq 'move' -and (Test-AnyExists $src)) { $status = 'EFFECT_MISMATCH'; $errorText = 'source still exists after move' }
        if ($op -eq 'move' -and $before.kind -eq 'file' -and (Test-FileExists $dst)) {
            $after = Get-ItemInfo $dst
            if ($after.length -ne $before.length) {
                $status = 'EFFECT_MISMATCH'
                $errorText = "file size mismatch: before=$($before.length) after=$($after.length)"
            }
        }
    } catch {
        $status = 'FAILED'
        $errorText = $_.Exception.Message
    }

    $afterInfo = if (Test-AnyExists $dst) { Get-ItemInfo $dst } else { $null }
    $final = [ordered]@{
        action_id = $ActionId
        action_digest = [string]$a.digest
        agent = $AgentName
        status = $status
        op = $op
        src = $src
        dst = $dst
        before = $before
        after = $afterInfo
        error = $errorText
        safety_reviewer = if ($review) { [string]$review.reviewer } else { $null }
        human_approver = if ($human) { [string]$human.approver } else { $null }
        started_at = [string]$running.started_at
        finished_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    }
    Write-JsonOverwrite $execFile $final
    Write-Host ("[{0}] {1}  src={2}  dst={3}" -f $status, $ActionId, $src, $dst)
    if ($status -ne 'SUCCESS') { throw "Action did not reach SUCCESS: $status" }
}

function Run-Action {
    Invoke-RunAction -ActionId $Action -AgentName $Agent
}

function Run-Batch {
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    if ([string]::IsNullOrWhiteSpace($BatchFile)) { throw '-BatchFile is required' }
    if ([string]::IsNullOrWhiteSpace($Agent)) { throw '-Agent is required' }
    if (-not (Test-FileExists $BatchFile)) { throw "BatchFile not found: $BatchFile" }
    $ids = @([IO.File]::ReadAllLines((Get-Ext $BatchFile), $script:Utf8NoBom) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($ids.Count -eq 0) { throw 'BatchFile is empty' }
    $n = 0
    foreach ($id in $ids) {
        $id = $id.Trim()
        $n++
        Write-Host ("[BATCH {0}/{1}] {2}" -f $n, $ids.Count, $id)
        Invoke-RunAction -ActionId $id -AgentName $Agent
        Start-Sleep -Milliseconds 120
    }
    Write-Host ("[OK] batch complete: {0} action(s)" -f $ids.Count)
}

function Status-Gate {
    if ([string]::IsNullOrWhiteSpace($RunRoot)) { throw '-RunRoot is required' }
    $config = Get-Config $RunRoot
    $actionsDir = Join-Path $RunRoot 'safety\actions'
    $rows = @()
    foreach ($f in ([IO.Directory]::GetFiles((Get-Ext $actionsDir), 'ACT-*.json') | Sort-Object)) {
        $id = [IO.Path]::GetFileNameWithoutExtension($f)
        $a = Get-Action $RunRoot $id
        $gateFile = Join-Path $RunRoot ("safety\gates\$id.json")
        $g = if (Test-FileExists $gateFile) { Read-JsonFile $gateFile } else { $null }
        $review = Get-Review $RunRoot $id
        $human = Get-Human $RunRoot $id
        $exec = Get-Execution $RunRoot $id
        $rows += [ordered]@{
            action_id = $id
            digest = [string]$a.digest
            op = [string]$a.proposal.op
            src = [string]$a.proposal.src
            dst = [string]$a.proposal.dst
            gate = if ($g) { [string]$g.status } else { 'UNGATED' }
            risk = if ($g) { [string]$g.risk } else { $null }
            review = if ($review) { [string]$review.verdict } elseif ($g -and $g.status -eq 'FAIL') { 'PENDING' } else { '-' }
            human = if ($human) { [string]$human.approver } elseif ($g -and $g.risk -eq 'red' -and $review -and $review.verdict -eq 'approve') { 'PENDING' } else { '-' }
            execution = if ($exec) { [string]$exec.status } else { '-' }
        }
    }
    $summary = [ordered]@{
        actions = @($rows).Count
        gate_pass = @($rows | Where-Object { $_.gate -eq 'PASS' }).Count
        gate_fail = @($rows | Where-Object { $_.gate -eq 'FAIL' }).Count
        ungated = @($rows | Where-Object { $_.gate -eq 'UNGATED' }).Count
        safety_pending = @($rows | Where-Object { $_.gate -eq 'FAIL' -and $_.review -eq 'PENDING' }).Count
        safety_reject = @($rows | Where-Object { $_.review -eq 'reject' }).Count
        executed_ok = @($rows | Where-Object { $_.execution -eq 'SUCCESS' }).Count
        executed_bad = @($rows | Where-Object { $_.execution -in @('FAILED','EFFECT_MISMATCH','BLOCKED_PRECHECK') }).Count
        running = @($rows | Where-Object { $_.execution -eq 'RUNNING' }).Count
    }
    $result = [ordered]@{ run_root = $RunRoot; config = $config; summary = $summary; rows = @($rows) }
    if ($Json) {
        $result | ConvertTo-Json -Depth 20
    } else {
        Write-Host ("== hdrive move gate: {0} ==" -f $RunRoot)
        Write-Host ("root: {0}" -f $config.root)
        Write-Host ("storage: {0}" -f $config.storage_root)
        Write-Host ("pending: {0}" -f $config.pending_root)
        Write-Host ("safety reviewers: {0}" -f (@($config.safety_reviewers) -join ', '))
        Write-Host ("human approvers: {0}" -f (@($config.human_approvers) -join ', '))
        Write-Host ("actions={0} gate_pass={1} gate_fail={2} ungated={3} safety_pending={4} safety_reject={5} executed_ok={6} executed_bad={7} running={8}" -f `
            $summary.actions, $summary.gate_pass, $summary.gate_fail, $summary.ungated, $summary.safety_pending, $summary.safety_reject, $summary.executed_ok, $summary.executed_bad, $summary.running)
        foreach ($r in @($rows | Where-Object { $_.gate -eq 'FAIL' -and $_.review -eq 'PENDING' })) {
            Write-Host ("  PENDING {0} risk={1} op={2} digest={3}" -f $r.action_id, $r.risk, $r.op, $r.digest)
        }
    }
}

try {
    switch ($Command) {
        'init' { Init-Gate }
        'propose' { Propose-Actions }
        'gate' { Gate-Actions }
        'review' { Review-Action }
        'human-approve' { Human-Approve }
        'run' { Run-Action }
        'run-batch' { Run-Batch }
        'status' { Status-Gate }
        default { throw "Unknown command: $Command" }
    }
} catch {
    Write-Host ("[ERROR] " + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
