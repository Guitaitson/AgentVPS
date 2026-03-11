param(
    [string]$ConfigPath = "$PSScriptRoot\voice-device-config.json"
)

Add-Type -AssemblyName System.Windows.Forms

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

function Confirm-Send {
    param($DriveInfo, $Files)
    $count = $Files.Count
    $message = "Drive $($DriveInfo.Drive) [$($DriveInfo.Label)] com $count arquivo(s) novo(s). Enviar para a VPS?"
    $result = [System.Windows.Forms.MessageBox]::Show(
        $message,
        'AgentVPS Voice Import',
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    return $result -eq [System.Windows.Forms.DialogResult]::Yes
}

function Send-FilesToVps {
    param($Files, $Config, $State)
    $scp = Get-ScpPath
    $ssh = Get-SshPath
    New-Item -ItemType Directory -Force -Path $Config.stagingDir | Out-Null
    $remoteStagingDir = if ([string]::IsNullOrWhiteSpace($Config.remoteStagingDir)) {
        '/tmp/agentvps-voice-inbox'
    } else {
        $Config.remoteStagingDir
    }
    foreach ($file in $Files) {
        $stagedName = "{0}_{1}" -f $file.Hash.Substring(0, 12), $file.Name
        $stagedPath = Join-Path $Config.stagingDir $stagedName
        Copy-Item -Path $file.Path -Destination $stagedPath -Force
        $remoteTempPath = "$remoteStagingDir/$stagedName"
        $remoteFinalPath = "$($Config.remoteInboxDir)/$stagedName"

        $prepareArguments = @('-F', 'NUL')
        if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
            $prepareArguments += @('-i', $Config.sshKeyPath)
        }
        $prepareArguments += @($Config.sshTarget, "mkdir -p $(Quote-Posix $remoteStagingDir)")
        Invoke-Process -FilePath $ssh -ArgumentList $prepareArguments

        $scpArguments = @('-F', 'NUL')
        if (-not [string]::IsNullOrWhiteSpace($Config.sshKeyPath)) {
            $scpArguments += @('-i', $Config.sshKeyPath)
        }
        $scpArguments += @($stagedPath, "$($Config.sshTarget):$remoteTempPath")
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
            throw "remote install failed for $($file.Name): $($_.Exception.Message)"
        }

        $State.files[$file.Hash] = @{
            name = $file.Name
            uploadedAt = (Get-Date).ToString('o')
            stagedName = $stagedName
        }
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
            if (Confirm-Send -DriveInfo $drive -Files $newFiles) {
                Send-FilesToVps -Files $newFiles -Config $config -State $state
                Save-State -State $state
                [System.Windows.Forms.MessageBox]::Show(
                    "Envio concluido: $($newFiles.Count) arquivo(s).",
                    'AgentVPS Voice Import',
                    [System.Windows.Forms.MessageBoxButtons]::OK,
                    [System.Windows.Forms.MessageBoxIcon]::Information
                ) | Out-Null
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
