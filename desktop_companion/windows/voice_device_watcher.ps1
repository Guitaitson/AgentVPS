param(
    [string]$ConfigPath = "$PSScriptRoot\voice-device-config.json",
    [switch]$RunOnce,
    [switch]$OnlyToday,
    [ValidateSet('prompt', 'send', 'open', 'skip')]
    [string]$BatchAction = 'prompt',
    [ValidateSet('none', 'inspect', 'sync_if_green', 'sync')]
    [string]$RemoteAction = 'none'
)

Add-Type -AssemblyName System.Windows.Forms
[System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture
[System.Threading.Thread]::CurrentThread.CurrentUICulture = [System.Globalization.CultureInfo]::InvariantCulture

function Load-Config {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        throw "Config file not found: $Path"
    }
    return Get-Content $Path -Raw | ConvertFrom-Json
}

function Get-StatePath {
    $base = Join-Path $env:LOCALAPPDATA 'AgentVPS'
    New-Item -ItemType Directory -Force -Path $base | Out-Null
    return Join-Path $base 'voice-device-state.json'
}

function Get-ConfigValue {
    param(
        $Config,
        [string]$Name,
        $Default
    )
    if ($null -eq $Config) {
        return $Default
    }
    if ($Config.PSObject.Properties.Name -contains $Name) {
        $value = $Config.$Name
        if ($null -ne $value -and (-not ($value -is [string]) -or -not [string]::IsNullOrWhiteSpace($value))) {
            return $value
        }
    }
    return $Default
}

function Load-State {
    $path = Get-StatePath
    if (-not (Test-Path $path)) {
        return @{ files = @{} }
    }
    try {
        $raw = Get-Content $path -Raw | ConvertFrom-Json
        $files = @{}
        if ($null -ne $raw -and $null -ne $raw.files) {
            foreach ($prop in $raw.files.PSObject.Properties) {
                $files[$prop.Name] = @{
                    name = $prop.Value.name
                    uploadedAt = $prop.Value.uploadedAt
                    stagedName = $prop.Value.stagedName
                    batchId = $prop.Value.batchId
                }
            }
        }
        return @{ files = $files }
    }
    catch {
        return @{ files = @{} }
    }
}

function Save-State {
    param($State)
    $path = Get-StatePath
    $State | ConvertTo-Json -Depth 5 | Set-Content $path
}

function Save-JsonFile {
    param(
        [string]$Path,
        $Data
    )
    $json = $Data | ConvertTo-Json -Depth 10
    Set-Content -Path $Path -Value $json -Encoding UTF8
}

function Get-ScpPath {
    $scp = (Get-Command scp.exe -ErrorAction SilentlyContinue).Source
    if (-not $scp) {
        throw 'scp.exe not found. Install OpenSSH Client on Windows.'
    }
    return $scp
}

function Get-SshPath {
    $ssh = (Get-Command ssh.exe -ErrorAction SilentlyContinue).Source
    if (-not $ssh) {
        throw 'ssh.exe not found. Install OpenSSH Client on Windows.'
    }
    return $ssh
}

function Get-SshIdentityArgs {
    param($Config)
    if ([string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
        return @()
    }
    return @('-i', ('"{0}"' -f $Config.sshKeyPath))
}

function Quote-Posix {
    param([string]$Value)
    $replacement = [string]::Concat("'", [char]34, "'", [char]34, "'")
    return "'" + ($Value -replace "'", $replacement) + "'"
}

function Invoke-Process {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList
    )
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -Wait -PassThru -NoNewWindow
    if ($process.ExitCode -ne 0) {
        throw "$([System.IO.Path]::GetFileName($FilePath)) failed with exit code $($process.ExitCode)"
    }
}

function Invoke-ProcessCapture {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList
    )
    $output = & $FilePath @ArgumentList 2>&1
    if ($LASTEXITCODE -ne 0) {
        $rendered = ($output | Out-String).Trim()
        if ([string]::IsNullOrWhiteSpace($rendered)) {
            throw "$([System.IO.Path]::GetFileName($FilePath)) failed with exit code $LASTEXITCODE"
        }
        throw "$([System.IO.Path]::GetFileName($FilePath)) failed with exit code ${LASTEXITCODE}: $rendered"
    }
    return ($output | Out-String).Trim()
}

function Get-PreTriageRoot {
    param($Config)
    $configured = Get-ConfigValue -Config $Config -Name 'preTriageDir' -Default $null
    if ($configured) {
        New-Item -ItemType Directory -Force -Path $configured | Out-Null
        return $configured
    }
    $root = Join-Path $Config.stagingDir 'pretriage'
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    return $root
}

function Get-AvailableFreeSpaceBytes {
    param([string]$Path)
    $root = [System.IO.Path]::GetPathRoot($Path)
    if ([string]::IsNullOrWhiteSpace($root)) {
        return $null
    }
    try {
        $drive = [System.IO.DriveInfo]::new($root)
        return [int64]$drive.AvailableFreeSpace
    }
    catch {
        return $null
    }
}

function Resolve-BatchStorageMode {
    param(
        $Config,
        $Files
    )
    $configuredMode = [string](Get-ConfigValue -Config $Config -Name 'batchStorageMode' -Default 'auto')
    if ($configuredMode -ne 'auto') {
        return $configuredMode
    }

    $requiredBytes = 0
    foreach ($file in $Files) {
        $info = Get-Item -LiteralPath $file.Path
        $requiredBytes += [int64]$info.Length
    }
    $reserveMb = [int64](Get-ConfigValue -Config $Config -Name 'stagingReserveMb' -Default 512)
    $freeBytes = Get-AvailableFreeSpaceBytes -Path $Config.stagingDir
    if ($null -eq $freeBytes) {
        return 'copy'
    }
    if ($freeBytes -lt ($requiredBytes + ($reserveMb * 1MB))) {
        return 'reference'
    }
    return 'copy'
}

function Get-AudioDurationSeconds {
    param([string]$Path)
    $ffprobe = (Get-Command ffprobe.exe -ErrorAction SilentlyContinue).Source
    if (-not $ffprobe) {
        return $null
    }
    $output = & $ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $Path 2>$null
    if (-not $output) {
        return $null
    }
    $value = 0.0
    $style = [System.Globalization.NumberStyles]::Float
    $culture = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse(($output | Select-Object -First 1).Trim(), $style, $culture, [ref]$value)) {
        return [math]::Round($value, 2)
    }
    return $null
}

function Get-InitialDecision {
    param(
        $Entry,
        $Config,
        $State
    )
    $reviewDurationMinutes = [double](Get-ConfigValue -Config $Config -Name 'reviewDurationMinutes' -Default 30)
    $minimumFileSizeKb = [int](Get-ConfigValue -Config $Config -Name 'minimumFileSizeKb' -Default 128)
    $minimumDurationSeconds = [double](Get-ConfigValue -Config $Config -Name 'minimumDurationSeconds' -Default 20)
    $reviewFileSizeMb = [int](Get-ConfigValue -Config $Config -Name 'reviewFileSizeMb' -Default 256)

    if ($State.files.ContainsKey($Entry.hash)) {
        return @{
            decision = 'hold'
            reason = 'already_uploaded'
        }
    }
    if ($Entry.sizeBytes -lt ($minimumFileSizeKb * 1024)) {
        return @{
            decision = 'hold'
            reason = "small_file_lt_${minimumFileSizeKb}kb"
        }
    }
    if ($null -ne $Entry.durationSeconds) {
        if ([double]$Entry.durationSeconds -lt $minimumDurationSeconds) {
            return @{
                decision = 'hold'
                reason = "short_audio_lt_${minimumDurationSeconds}s"
            }
        }
        if ([double]$Entry.durationSeconds -gt ($reviewDurationMinutes * 60)) {
            return @{
                decision = 'hold'
                reason = "long_audio_gt_${reviewDurationMinutes}m"
            }
        }
    } elseif ($Entry.sizeBytes -gt ($reviewFileSizeMb * 1MB)) {
        return @{
            decision = 'hold'
            reason = "large_file_without_duration_gt_${reviewFileSizeMb}mb"
        }
    }
    return @{
        decision = 'approved'
        reason = 'metadata_ok'
    }
}

function Convert-EntryProjection {
    param(
        $Entries,
        [switch]$IncludeUploadedAt
    )
    $projected = @()
    foreach ($entry in $Entries) {
        $item = [ordered]@{
            name = $entry.name
            stagedName = $entry.stagedName
            durationSeconds = $entry.durationSeconds
            sizeBytes = $entry.sizeBytes
            decisionReason = $entry.decisionReason
        }
        if ($IncludeUploadedAt) {
            $item.uploadedAt = $entry.uploadedAt
        }
        $projected += [PSCustomObject]$item
    }
    return $projected
}

function Get-BatchSummary {
    param(
        $Entries,
        $Config
    )
    $approved = @($Entries | Where-Object { $_.decision -eq 'approved' }).Count
    $hold = @($Entries | Where-Object { $_.decision -eq 'hold' }).Count
    $discarded = @($Entries | Where-Object { $_.decision -eq 'discarded' }).Count
    $knownDurations = @($Entries | Where-Object { $null -ne $_.durationSeconds })
    $totalDurationSeconds = 0.0
    foreach ($entry in $knownDurations) {
        $totalDurationSeconds += [double]$entry.durationSeconds
    }
    $averageDurationSeconds = if ($knownDurations.Count -gt 0) {
        [math]::Round(($totalDurationSeconds / $knownDurations.Count), 2)
    } else {
        $null
    }

    $recommendation = if ($discarded -gt 0) {
        'test_conservative_profile'
    } elseif ($hold -gt 0) {
        'review_before_send'
    } else {
        'approve_current_profile'
    }

    $advice = switch ($recommendation) {
        'test_conservative_profile' {
            'O lote tem arquivos com sinal fraco ou inconsistencias de metadata. Teste o perfil conservador antes de subir tudo.'
        }
        'review_before_send' {
            'Ha arquivos que merecem segregacao manual antes do envio. Revise os itens em hold e suba apenas os aprovados.'
        }
        default {
            'O lote parece estavel pelo gate local. Se o conteudo estiver coerente, envie apenas os aprovados.'
        }
    }

    return @{
        totalFiles = $Entries.Count
        approvedFiles = $approved
        holdFiles = $hold
        discardedFiles = $discarded
        totalDurationMinutes = if ($knownDurations.Count -gt 0) { [math]::Round($totalDurationSeconds / 60.0, 1) } else { $null }
        averageDurationSeconds = $averageDurationSeconds
        recommendation = $recommendation
        advice = $advice
        reviewDurationMinutes = [double](Get-ConfigValue -Config $Config -Name 'reviewDurationMinutes' -Default 30)
    }
}

function New-PreTriageBatch {
    param(
        $DriveInfo,
        $Files,
        $Config,
        $State
    )
    New-Item -ItemType Directory -Force -Path $Config.stagingDir | Out-Null
    $preTriageRoot = Get-PreTriageRoot -Config $Config
    $storageMode = Resolve-BatchStorageMode -Config $Config -Files $Files
    $batchId = 'voice-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    $batchDir = Join-Path $preTriageRoot $batchId
    $filesDir = Join-Path $batchDir 'files'
    New-Item -ItemType Directory -Force -Path $filesDir | Out-Null

    $entries = @()
    foreach ($file in $Files) {
        $stagedName = "{0}_{1}" -f $file.Hash.Substring(0, 12), $file.Name
        $stagedPath = Join-Path $filesDir $stagedName
        $info = Get-Item -LiteralPath $file.Path
        if ($storageMode -eq 'copy') {
            Copy-Item -Path $file.Path -Destination $stagedPath -Force
            $resolvedPath = $stagedPath
            $resolvedMode = 'copied'
        } else {
            $resolvedPath = $file.Path
            $resolvedMode = 'source_reference'
        }
        $durationSeconds = Get-AudioDurationSeconds -Path $resolvedPath
        $entry = @{
            name = $file.Name
            hash = $file.Hash
            sourcePath = $file.Path
            stagedName = $stagedName
            stagedPath = $resolvedPath
            sizeBytes = [int64]$info.Length
            lastWriteTime = $info.LastWriteTimeUtc.ToString('o')
            durationSeconds = $durationSeconds
            storageMode = $resolvedMode
            decision = 'pending'
            decisionReason = 'pending_review'
            uploadedAt = $null
            remoteInboxPath = $null
        }
        $decision = Get-InitialDecision -Entry $entry -Config $Config -State $State
        $entry.decision = $decision.decision
        $entry.decisionReason = $decision.reason
        $entries += $entry
    }

    $summary = Get-BatchSummary -Entries $entries -Config $Config
    $manifest = @{
        batchId = $batchId
        createdAt = (Get-Date).ToString('o')
        watcherVersion = '2'
        reviewMode = 'metadata_gate'
        drive = $DriveInfo.Drive
        volumeLabel = $DriveInfo.Label
        importRoot = $DriveInfo.ImportRoot
        batchStorageMode = $storageMode
        recorderProfile = (Get-ConfigValue -Config $Config -Name 'recorderProfile' -Default 'unknown')
        summary = $summary
        files = $entries
    }
    $review = @{
        batchId = $batchId
        createdAt = $manifest.createdAt
        recommendation = $summary.recommendation
        advice = $summary.advice
        approvedFiles = @(Convert-EntryProjection -Entries @($entries | Where-Object { $_.decision -eq 'approved' }))
        holdFiles = @(Convert-EntryProjection -Entries @($entries | Where-Object { $_.decision -eq 'hold' }))
        discardedFiles = @(Convert-EntryProjection -Entries @($entries | Where-Object { $_.decision -eq 'discarded' }))
    }

    $manifestPath = Join-Path $batchDir 'batch_manifest.json'
    $reviewPath = Join-Path $batchDir 'batch_review.json'
    Save-JsonFile -Path $manifestPath -Data $manifest
    Save-JsonFile -Path $reviewPath -Data $review

    return @{
        BatchId = $batchId
        BatchDir = $batchDir
        ManifestPath = $manifestPath
        ReviewPath = $reviewPath
        Manifest = $manifest
        Config = $Config
    }
}

function Save-BatchArtifacts {
    param($Batch)
    Save-JsonFile -Path $Batch.ManifestPath -Data $Batch.Manifest
    $summary = Get-BatchSummary -Entries $Batch.Manifest.files -Config $Batch.Config
    $Batch.Manifest.summary = $summary
    Save-JsonFile -Path $Batch.ManifestPath -Data $Batch.Manifest
    Save-JsonFile -Path $Batch.ReviewPath -Data @{
        batchId = $Batch.Manifest.batchId
        createdAt = $Batch.Manifest.createdAt
        recommendation = $summary.recommendation
        advice = $summary.advice
        approvedFiles = @(Convert-EntryProjection -Entries @($Batch.Manifest.files | Where-Object { $_.decision -eq 'approved' }) -IncludeUploadedAt)
        holdFiles = @(Convert-EntryProjection -Entries @($Batch.Manifest.files | Where-Object { $_.decision -eq 'hold' }))
        discardedFiles = @(Convert-EntryProjection -Entries @($Batch.Manifest.files | Where-Object { $_.decision -eq 'discarded' }))
    }
}

function Get-EligibleDrives {
    param($Config)
    $drives = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 2 }
    foreach ($drive in $drives) {
        if ($Config.volumeLabel -and $drive.VolumeName -ne $Config.volumeLabel) {
            continue
        }
        $root = $drive.DeviceID + '\\'
        $importRoot = if ([string]::IsNullOrWhiteSpace($Config.importPath)) { $root } else { Join-Path $root $Config.importPath }
        if (-not (Test-Path $importRoot)) {
            continue
        }
        [PSCustomObject]@{
            Drive = $drive.DeviceID
            Label = $drive.VolumeName
            ImportRoot = $importRoot
        }
    }
}

function Get-NewFiles {
    param($DriveInfo, $Config, $State, [switch]$OnlyToday)
    $extensions = @($Config.extensions | ForEach-Object { $_.ToLowerInvariant() })
    $today = (Get-Date).Date
    $files = Get-ChildItem -Path $DriveInfo.ImportRoot -Recurse -File | Where-Object {
        ($extensions -contains $_.Extension.ToLowerInvariant()) -and (
            (-not $OnlyToday) -or $_.LastWriteTime.Date -eq $today
        )
    }
    $newFiles = @()
    foreach ($file in $files) {
        $hash = (Get-FileHash -Algorithm SHA256 -Path $file.FullName).Hash.ToLowerInvariant()
        if (-not $State.files.ContainsKey($hash)) {
            $newFiles += [PSCustomObject]@{
                Path = $file.FullName
                Name = $file.Name
                Hash = $hash
            }
        }
    }
    return $newFiles
}

function Confirm-BatchAction {
    param($Batch)
    $summary = $Batch.Manifest.summary
    $count = $summary.totalFiles
    $message = @(
        "Lote $($Batch.Manifest.batchId)"
        "Drive $($Batch.Manifest.drive) [$($Batch.Manifest.volumeLabel)] com $count arquivo(s) novo(s)."
        ""
        "Aprovados: $($summary.approvedFiles)"
        "Em hold: $($summary.holdFiles)"
        "Descartados: $($summary.discardedFiles)"
        "Duracao total (min): $($summary.totalDurationMinutes)"
        "Recomendacao: $($summary.recommendation)"
        ""
        "$($summary.advice)"
        ""
        "Sim = enviar apenas aprovados agora"
        "Nao = abrir a pasta do lote para revisao local"
        "Cancelar = deixar o lote parado"
    ) -join [Environment]::NewLine
    $result = [System.Windows.Forms.MessageBox]::Show(
        $message,
        'AgentVPS Voice Pre-Triage',
        [System.Windows.Forms.MessageBoxButtons]::YesNoCancel,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    return $result
}

function Send-FilesToVps {
    param($Batch, $Config, $State)
    $scp = Get-ScpPath
    $ssh = Get-SshPath
    New-Item -ItemType Directory -Force -Path $Config.stagingDir | Out-Null
    $remoteStagingDir = if ([string]::IsNullOrWhiteSpace($Config.remoteStagingDir)) {
        '/tmp/agentvps-voice-inbox'
    } else {
        $Config.remoteStagingDir
    }
    $remoteManifestDir = Get-ConfigValue -Config $Config -Name 'remoteManifestDir' -Default '/opt/vps-agent/data/voice/manifests'
    $uploadManifest = [bool](Get-ConfigValue -Config $Config -Name 'uploadBatchManifest' -Default $true)

    $prepareArguments = @('-F', 'NUL')
    $prepareArguments += @(Get-SshIdentityArgs -Config $Config)
    $prepareTargets = @(
        "mkdir -p $(Quote-Posix $remoteStagingDir) $(Quote-Posix $Config.remoteInboxDir)"
    )
    if ($uploadManifest) {
        $prepareTargets += "mkdir -p $(Quote-Posix $remoteManifestDir)"
    }
    $prepareArguments += @(
        $Config.sshTarget,
        ($prepareTargets -join '; ')
    )
    Invoke-Process -FilePath $ssh -ArgumentList $prepareArguments

    $approvedFiles = @($Batch.Manifest.files | Where-Object { $_.decision -eq 'approved' })
    foreach ($file in $approvedFiles) {
        $remoteTempPath = "$remoteStagingDir/$($file.stagedName)"
        $remoteFinalPath = "$($Config.remoteInboxDir)/$($file.stagedName)"

        $scpArguments = @('-F', 'NUL')
        $scpArguments += @(Get-SshIdentityArgs -Config $Config)
        $scpArguments += @($file.stagedPath, "$($Config.sshTarget):$remoteTempPath")
        Invoke-Process -FilePath $scp -ArgumentList $scpArguments

        $remoteCommand = @(
            'set -e'
            "mkdir -p $(Quote-Posix $remoteStagingDir)"
            "sudo install -o vps_agent -g vps_agent -m 0644 $(Quote-Posix $remoteTempPath) $(Quote-Posix $remoteFinalPath)"
            "rm -f $(Quote-Posix $remoteTempPath)"
            "test -f $(Quote-Posix $remoteFinalPath)"
        ) -join '; '

        $sshArguments = @('-F', 'NUL')
        $sshArguments += @(Get-SshIdentityArgs -Config $Config)
        $sshArguments += @($Config.sshTarget, $remoteCommand)
        try {
            Invoke-Process -FilePath $ssh -ArgumentList $sshArguments
        }
        catch {
            $cleanupCommand = "rm -f $(Quote-Posix $remoteTempPath)"
            $cleanupArguments = @('-F', 'NUL')
            $cleanupArguments += @(Get-SshIdentityArgs -Config $Config)
            $cleanupArguments += @($Config.sshTarget, $cleanupCommand)
            Start-Process -FilePath $ssh -ArgumentList $cleanupArguments -Wait -NoNewWindow | Out-Null
            throw "remote install failed for $($file.name): $($_.Exception.Message)"
        }

        $uploadedAt = (Get-Date).ToString('o')
        $file.uploadedAt = $uploadedAt
        $file.remoteInboxPath = $remoteFinalPath
        $State.files[$file.hash] = @{
            name = $file.name
            uploadedAt = $uploadedAt
            stagedName = $file.stagedName
            batchId = $Batch.Manifest.batchId
        }
    }

    Save-BatchArtifacts -Batch $Batch

    if ($uploadManifest) {
        $remoteTempManifest = "$remoteStagingDir/$($Batch.Manifest.batchId).json"
        $remoteFinalManifest = "$remoteManifestDir/$($Batch.Manifest.batchId).json"

        $scpArguments = @('-F', 'NUL')
        $scpArguments += @(Get-SshIdentityArgs -Config $Config)
        $scpArguments += @($Batch.ManifestPath, "$($Config.sshTarget):$remoteTempManifest")
        Invoke-Process -FilePath $scp -ArgumentList $scpArguments

        $remoteCommand = @(
            'set -e'
            "sudo install -o vps_agent -g vps_agent -m 0644 $(Quote-Posix $remoteTempManifest) $(Quote-Posix $remoteFinalManifest)"
            "rm -f $(Quote-Posix $remoteTempManifest)"
            "test -f $(Quote-Posix $remoteFinalManifest)"
        ) -join '; '

        $sshArguments = @('-F', 'NUL')
        $sshArguments += @(Get-SshIdentityArgs -Config $Config)
        $sshArguments += @($Config.sshTarget, $remoteCommand)
        Invoke-Process -FilePath $ssh -ArgumentList $sshArguments
        $Batch.Manifest.remoteManifestPath = $remoteFinalManifest
    } else {
        $Batch.Manifest.remoteManifestPath = $null
    }

    Save-BatchArtifacts -Batch $Batch
}

function Invoke-RemoteVoicePipeline {
    param(
        $Batch,
        $Config,
        [string]$Mode
    )
    $approvedFiles = @($Batch.Manifest.files | Where-Object { $_.decision -eq 'approved' })
    if ($approvedFiles.Count -eq 0) {
        return @{
            skipped = $true
            reason = 'no_approved_files'
            mode = $Mode
        }
    }

    $ssh = Get-SshPath
    $remoteProjectDir = Get-ConfigValue -Config $Config -Name 'remoteProjectDir' -Default '/opt/vps-agent'
    $remotePythonPath = Get-ConfigValue -Config $Config -Name 'remotePythonPath' -Default "$remoteProjectDir/core/venv/bin/python3"
    $remoteBatchRunnerPath = Get-ConfigValue -Config $Config -Name 'remoteBatchRunnerPath' -Default "$remoteProjectDir/scripts/voice_context_batch.py"
    $approvedNames = @($approvedFiles | ForEach-Object { $_.stagedName })
    $approvedNamesJson = ($approvedNames | ConvertTo-Json -Compress)
    $remoteSource = "windows_pretriage:$($Batch.Manifest.batchId)"
    $remoteInvocation = "$(Quote-Posix $remotePythonPath) $(Quote-Posix $remoteBatchRunnerPath) --mode $(Quote-Posix $Mode) --source $(Quote-Posix $remoteSource) --max-files $($approvedFiles.Count)"
    if ($Batch.Manifest.remoteManifestPath) {
        $remoteInvocation += " --manifest-path $(Quote-Posix ([string]$Batch.Manifest.remoteManifestPath))"
    } else {
        $remoteInvocation += " --file-names-json $(Quote-Posix $approvedNamesJson)"
    }
    $remoteCommand = @(
        'set -e'
        "cd $(Quote-Posix $remoteProjectDir)"
        $remoteInvocation
    ) -join '; '

    $sshArguments = @('-F', 'NUL')
    $sshArguments += @(Get-SshIdentityArgs -Config $Config)
    $sshArguments += @($Config.sshTarget, $remoteCommand)
    $output = Invoke-ProcessCapture -FilePath $ssh -ArgumentList $sshArguments
    $report = $output | ConvertFrom-Json -Depth 20
    $reportPath = Join-Path $Batch.BatchDir "remote_$Mode.json"
    Save-JsonFile -Path $reportPath -Data $report
    return @{
        skipped = $false
        mode = $Mode
        path = $reportPath
        report = $report
    }
}

function Format-RemotePipelineSummary {
    param($RemoteExecution)
    if ($null -eq $RemoteExecution -or $RemoteExecution.skipped) {
        return "Acao remota nao executada: $($RemoteExecution.reason)"
    }
    $report = $RemoteExecution.report
    $inspect = $report.inspect
    $gate = $report.green_gate
    $lines = @(
        "Acao remota: $($RemoteExecution.mode)",
        "inspect.processed_files: $($inspect.processed_files)",
        "inspect.batch_recommendation: $($inspect.batch_recommendation)",
        "green_gate.passed: $($gate.passed)"
    )
    if ($gate.failed_reasons) {
        $lines += "green_gate.failed_reasons: $([string]::Join(', ', @($gate.failed_reasons)))"
    }
    if ($report.sync) {
        $lines += "sync.status: $($report.sync.status)"
        $lines += "sync.auto_committed: $($report.sync.auto_committed)"
        $lines += "sync.pending_review: $($report.sync.pending_review)"
    }
    return ($lines -join [Environment]::NewLine)
}

$config = Load-Config -Path $ConfigPath
$state = Load-State
$seenDrives = @{}

Write-Host "AgentVPS voice watcher running. Monitoring removable drives..."
while ($true) {
    $processedBatch = $false
    try {
        $eligible = @(Get-EligibleDrives -Config $config)
        $activeDrives = @{}
        foreach ($drive in $eligible) {
            $activeDrives[$drive.Drive] = $true
            if ($seenDrives.ContainsKey($drive.Drive)) {
                continue
            }
            $newFiles = @(Get-NewFiles -DriveInfo $drive -Config $config -State $state -OnlyToday:$OnlyToday)
            if ($newFiles.Count -eq 0) {
                $seenDrives[$drive.Drive] = $true
                continue
            }
            $batch = New-PreTriageBatch -DriveInfo $drive -Files $newFiles -Config $config -State $state
            $remoteExecution = $null
            $sendBatch = $false
            $openBatch = $false

            switch ($BatchAction) {
                'send' {
                    $sendBatch = $true
                }
                'open' {
                    $openBatch = $true
                }
                'skip' {
                    $null = $true
                }
                default {
                    $decision = Confirm-BatchAction -Batch $batch
                    if ($decision -eq [System.Windows.Forms.DialogResult]::Yes) {
                        $sendBatch = $true
                    } elseif ($decision -eq [System.Windows.Forms.DialogResult]::No) {
                        $openBatch = $true
                    }
                }
            }

            if ($sendBatch) {
                Send-FilesToVps -Batch $batch -Config $config -State $state
                Save-State -State $state
                if ($RemoteAction -ne 'none') {
                    $remoteExecution = Invoke-RemoteVoicePipeline -Batch $batch -Config $config -Mode $RemoteAction
                }
                $approvedCount = @($batch.Manifest.files | Where-Object { $_.decision -eq 'approved' }).Count
                $message = "Pre-triagem concluida. Envio efetuado para $approvedCount arquivo(s) aprovado(s)." + [Environment]::NewLine + "Lote: $($batch.BatchDir)"
                if ($remoteExecution) {
                    $message += [Environment]::NewLine + [Environment]::NewLine + (Format-RemotePipelineSummary -RemoteExecution $remoteExecution)
                }
                if ($BatchAction -eq 'prompt' -and -not $RunOnce) {
                    [System.Windows.Forms.MessageBox]::Show(
                        $message,
                        'AgentVPS Voice Pre-Triage',
                        [System.Windows.Forms.MessageBoxButtons]::OK,
                        [System.Windows.Forms.MessageBoxIcon]::Information
                    ) | Out-Null
                } else {
                    Write-Host $message
                }
                $processedBatch = $true
            } elseif ($openBatch) {
                Start-Process explorer.exe $batch.BatchDir | Out-Null
                $processedBatch = $true
            }
            $seenDrives[$drive.Drive] = $true
            if ($RunOnce) {
                break
            }
        }
        foreach ($knownDrive in @($seenDrives.Keys)) {
            if (-not $activeDrives.ContainsKey($knownDrive)) {
                $seenDrives.Remove($knownDrive)
            }
        }
    }
    catch {
        Write-Warning $_.Exception.Message
        if ($RunOnce) {
            throw
        }
    }
    if ($RunOnce) {
        if (-not $processedBatch) {
            Write-Host "Nenhum lote novo encontrado."
        }
        break
    }
    Start-Sleep -Seconds ([int]$config.pollSeconds)
}
