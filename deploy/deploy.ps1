# 서버 컴퓨터용: GitHub main 의 최신 코드를 받아 바뀐 서비스만 다시 빌드·실행한다.
#   powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1          새 커밋이 있을 때만
#   powershell -ExecutionPolicy Bypass -File deploy\deploy.ps1 -Force   처음 실행·강제 재빌드
param([switch]$Force)

# git 이 내보내는 한글(커밋 메시지)을 Windows PowerShell 5.1 에서도 깨지지 않게 읽는다
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$repo = Split-Path $PSScriptRoot -Parent
Set-Location $repo
$logFile = Join-Path $PSScriptRoot "deploy.log"
$deployedFile = Join-Path $PSScriptRoot "deployed.txt"  # 마지막으로 배포에 성공한 커밋 (빌드가 실패하면 다음 회차에 다시 시도하려고)

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $msg"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

git fetch origin main --quiet
if ($LASTEXITCODE -ne 0) { Log "git fetch 실패 (인터넷·GitHub 로그인 확인)"; exit 1 }

$local = (git rev-parse HEAD).Trim()
$remote = (git rev-parse origin/main).Trim()
$deployed = if (Test-Path $deployedFile) { (Get-Content $deployedFile -Raw).Trim() } else { "" }
# 바뀐 것 없고 지난 배포도 성공 (10분마다 도는 자동 배포가 로그를 채우지 않게 조용히 끝냄)
if ($local -eq $remote -and $deployed -eq $local -and -not $Force) { exit 0 }

# 서버에서 직접 고친 파일이 있으면 덮어쓰지 않고 멈춘다 (코드는 내 PC 에서 고쳐 push)
$dirty = git status --porcelain --untracked-files=no
if ($dirty) { Log "서버에서 직접 고친 파일이 있어 멈춤 → git status 로 확인:`n$dirty"; exit 1 }

git checkout main --quiet
git pull --ff-only origin main --quiet
if ($LASTEXITCODE -ne 0) { Log "git pull 실패"; exit 1 }
if ($local -ne $remote) { Log "코드 받음: $($local.Substring(0, 7)) → $($remote.Substring(0, 7))" }
elseif (-not $Force) { Log "지난 배포가 끝나지 않아 다시 빌드: $($local.Substring(0, 7))" }

# 관리자 화면에 보일 배포 버전 (docker-compose.yml 의 web build args)
$env:BUILD_SHA = (git rev-parse --short HEAD).Trim()
$env:BUILD_MSG = (git log -1 --format=%s).Trim()
$env:BUILD_TIME = (git log -1 --format=%cI).Trim()

docker compose up -d --build --remove-orphans
if ($LASTEXITCODE -ne 0) { Log "docker compose 실패 (Docker Desktop 이 켜져 있는지 확인)"; exit 1 }
Set-Content -Path $deployedFile -Value (git rev-parse HEAD).Trim()
docker image prune -f | Out-Null  # 다시 빌드하며 남은 옛 이미지 정리
Log "배포 완료"
docker compose ps
