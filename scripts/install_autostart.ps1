# Optional: start the AeroFox public server automatically when this Windows user logs in.
#   powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1            (install)
#   powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Remove    (uninstall)
# Creates ONE Task Scheduler entry for the current user ("AeroFox publico"). No administrator rights, no service.
param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$name = 'AeroFox publico'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[AeroFox] Inicio automatico removido."
    exit 0
}
$bat = Join-Path (Split-Path -Parent $PSScriptRoot) 'START_AEROFOX_PUBLICO.bat'
Write-Host "[AeroFox] Isto cria a tarefa agendada '$name' que abre $bat sempre que voce entrar no Windows."
$ok = Read-Host 'Confirmar? (S/N)'
if ($ok -notmatch '^[sSyY]') { Write-Host 'Cancelado.'; exit 1 }
$action = New-ScheduledTaskAction -Execute 'cmd.exe' -Argument "/c `"$bat`"" -WorkingDirectory (Split-Path $bat)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited -Force | Out-Null
Write-Host "[AeroFox] Pronto. Para remover: powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Remove"
