param(
    [string]$ConfigPath = "$PSScriptRoot\voice-device-config.json"
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
    }
    return @{
        decision = 'approved'
        reason = 'metadata_ok'
    }
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
    $batchId = 'voice-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    $batchDir = Join-Path $preTriageRoot $batchId
    $filesDir = Join-Path $batchDir 'files'
    New-Item -ItemType Directory -Force -Path $filesDir | Out-Null

    $entries = @()
    foreach ($file in $Files) {
        $stagedName = "{0}_{1}" -f $file.Hash.Substring(0, 12), $file.Name
        $stagedPath = Join-Path $filesDir $stagedName
        Copy-Item -Path $file.Path -Destination $stagedPath -Force
        $info = Get-Item -LiteralPath $file.Path
        $durationSeconds = Get-AudioDurationSeconds -Path $stagedPath
        $entry = @{
            name = $file.Name
            hash = $file.Hash
            sourcePath = $file.Path
            stagedName = $stagedName
            stagedPath = $stagedPath
            sizeBytes = [int64]$info.Length
            lastWriteTime = $info.LastWriteTimeUtc.ToString('o')
            durationSeconds = $durationSeconds
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
        recorderProfile = (Get-ConfigValue -Config $Config -Name 'recorderProfile' -Default 'unknown')
        summary = $summary
        files = $entries
    }
    $review = @{
        batchId = $batchId
        createdAt = $manifest.createdAt
        recommendation = $summary.recommendation
        advice = $summary.advice
        approvedFiles = @($entries | Where-Object { $_.decision -eq 'approved' } | Select-Object name, stagedName, durationSeconds, sizeBytes, decisionReason)
        holdFiles = @($entries | Where-Object { $_.decision -eq 'hold' } | Select-Object name, stagedName, durationSeconds, sizeBytes, decisionReason)
        discardedFiles = @($entries | Where-Object { $_.decision -eq 'discarded' } | Select-Object name, stagedName, durationSeconds, sizeBytes, decisionReason)
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
        approvedFiles = @($Batch.Manifest.files | Where-Object { $_.decision -eq 'approved' } | Select-Object name, stagedName, durationSeconds, sizeBytes, decisionReason, uploadedAt)
        holdFiles = @($Batch.Manifest.files | Where-Object { $_.decision -eq 'hold' } | Select-Object name, stagedName, durationSeconds, sizeBytes, decisionReason)
        discardedFiles = @($Batch.Manifest.files | Where-Object { $_.decision -eq 'discarded' } | Select-Object name, stagedName, durationSeconds, sizeBytes, decisionReason)
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
    param($DriveInfo, $Config, $State)
    $extensions = @($Config.extensions | ForEach-Object { $_.ToLowerInvariant() })
    $files = Get-ChildItem -Path $DriveInfo.ImportRoot -Recurse -File | Where-Object {
        $extensions -contains $_.Extension.ToLowerInvariant()
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
    $remoteManifestDir = Get-ConfigValue -Config $Config -Name 'remoteManifestDir' -Default "$($Config.remoteInboxDir)/manifests"

    $prepareArguments = @('-F', 'NUL')
    if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
        $prepareArguments += @('-i', $Config.sshKeyPath)
    }
    $prepareArguments += @(
        $Config.sshTarget,
        "mkdir -p $(Quote-Posix $remoteStagingDir) $(Quote-Posix $Config.remoteInboxDir) $(Quote-Posix $remoteManifestDir)"
    )
    Invoke-Process -FilePath $ssh -ArgumentList $prepareArguments

    $approvedFiles = @($Batch.Manifest.files | Where-Object { $_.decision -eq 'approved' })
    foreach ($file in $approvedFiles) {
        $remoteTempPath = "$remoteStagingDir/$($file.stagedName)"
        $remoteFinalPath = "$($Config.remoteInboxDir)/$($file.stagedName)"

        $scpArguments = @('-F', 'NUL')
        if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
            $scpArguments += @('-i', $Config.sshKeyPath)
        }
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
        if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
            $sshArguments += @('-i', $Config.sshKeyPath)
        }
        $sshArguments += @($Config.sshTarget, $remoteCommand)
        try {
            Invoke-Process -FilePath $ssh -ArgumentList $sshArguments
        }
        catch {
            $cleanupCommand = "rm -f $(Quote-Posix $remoteTempPath)"
            $cleanupArguments = @('-F', 'NUL')
            if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
                $cleanupArguments += @('-i', $Config.sshKeyPath)
            }
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

    $uploadManifest = [bool](Get-ConfigValue -Config $Config -Name 'uploadBatchManifest' -Default $true)
    if ($uploadManifest) {
        $remoteTempManifest = "$remoteStagingDir/$($Batch.Manifest.batchId).json"
        $remoteFinalManifest = "$remoteManifestDir/$($Batch.Manifest.batchId).json"

        $scpArguments = @('-F', 'NUL')
        if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
            $scpArguments += @('-i', $Config.sshKeyPath)
        }
        $scpArguments += @($Batch.ManifestPath, "$($Config.sshTarget):$remoteTempManifest")
        Invoke-Process -FilePath $scp -ArgumentList $scpArguments

        $remoteCommand = @(
            'set -e'
            "sudo install -o vps_agent -g vps_agent -m 0644 $(Quote-Posix $remoteTempManifest) $(Quote-Posix $remoteFinalManifest)"
            "rm -f $(Quote-Posix $remoteTempManifest)"
            "test -f $(Quote-Posix $remoteFinalManifest)"
        ) -join '; '

        $sshArguments = @('-F', 'NUL')
        if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
            $sshArguments += @('-i', $Config.sshKeyPath)
        }
        $sshArguments += @($Config.sshTarget, $remoteCommand)
        Invoke-Process -FilePath $ssh -ArgumentList $sshArguments
    }
}

$config = Load-Config -Path $ConfigPath
$state = Load-State
$seenDrives = @{}

Write-Host "AgentVPS voice watcher running. Monitoring removable drives..."
while ($true) {
    try {
        $eligible = @(Get-EligibleDrives -Config $config)
        $activeDrives = @{}
        foreach ($drive in $eligible) {
            $activeDrives[$drive.Drive] = $true
            if ($seenDrives.ContainsKey($drive.Drive)) {
                continue
            }
            $newFiles = @(Get-NewFiles -DriveInfo $drive -Config $config -State $state)
            if ($newFiles.Count -eq 0) {
                $seenDrives[$drive.Drive] = $true
                continue
            }
            $batch = New-PreTriageBatch -DriveInfo $drive -Files $newFiles -Config $config -State $state
            $decision = Confirm-BatchAction -Batch $batch
            if ($decision -eq [System.Windows.Forms.DialogResult]::Yes) {
                Send-FilesToVps -Batch $batch -Config $config -State $state
                Save-State -State $state
                $approvedCount = @($batch.Manifest.files | Where-Object { $_.decision -eq 'approved' }).Count
                [System.Windows.Forms.MessageBox]::Show(
                    "Pre-triagem concluida. Envio efetuado para $approvedCount arquivo(s) aprovado(s)." + [Environment]::NewLine + "Lote: $($batch.BatchDir)",
                    'AgentVPS Voice Pre-Triage',
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
            } elseif ($decision -eq [System.Windows.Forms.DialogResult]::No) {
                Start-Process explorer.exe $batch.BatchDir | Out-Null
            }
            $seenDrives[$drive.Drive] = $true
        }
        foreach ($knownDrive in @($seenDrives.Keys)) {
            if (-not $activeDrives.ContainsKey($knownDrive)) {
                $seenDrives.Remove($knownDrive)
            }
        }
    }
    catch {
        Write-Warning $_.Exception.Message
    }
    Start-Sleep -Seconds ([int]$config.pollSeconds)
}
