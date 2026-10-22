# 서버 컴퓨터용: 10분마다 deploy.ps1 을 실행하는 Windows 작업 스케줄러 작업을 만든다 (한 번만 실행)
#   powershell -ExecutionPolicy Bypass -File deploy\register-auto-deploy.ps1
# 끄기: Unregister-ScheduledTask -TaskName "FarmBid-AutoDeploy" -Confirm:$false
# Docker Desktop 처럼 로그인한 사용자로 돈다 → 서버 컴퓨터는 로그인한 상태로 둔다

$script = Join-Path $PSScriptRoot "deploy.ps1"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" `
    -WorkingDirectory (Split-Path $PSScriptRoot -Parent)
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -StartWhenAvailable

Register-ScheduledTask -TaskName "FarmBid-AutoDeploy" -Action $action -Trigger $trigger -Settings $settings `
    -Description "팜비드: GitHub main 에 새 커밋이 있으면 받아서 docker compose 로 다시 띄움 (deploy\deploy.ps1)" -Force | Out-Null

Write-Host "등록 완료: 10분마다 main 을 확인해 바뀌었으면 배포합니다. 기록은 deploy\deploy.log"
