param(
    [string]$ConfigPath = "$PSScriptRoot\voice-device-config.json"
)

powershell.exe -ExecutionPolicy Bypass -File "$PSScriptRoot\voice_device_watcher.ps1" -ConfigPath $ConfigPath
