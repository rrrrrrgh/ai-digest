# 每 3 天推一期「GitHub 上有意思的 AI 项目」到手机微信
#   .\run.ps1              # 正常跑：距上期满了 3 天才发
#   .\run.ps1 -Force       # 无视周期，现在就发一期
#   .\run.ps1 -Force -Dry  # 只生成不发送（本地看效果）
param(
    [switch]$Force,
    [switch]$Dry,
    [switch]$SkipFetch
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir ((Get-Date -Format 'yyyy-MM') + '.log')

function Log([string]$msg) {
    $line = "[{0}] {1}" -f (Get-Date -Format 'MM-dd HH:mm:ss'), $msg
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

# --- 找 Python ---
$py = $null
foreach ($c in @(
        'C:\Users\63076\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe',
        (Get-Command python -ErrorAction SilentlyContinue).Source)) {
    if ($c -and (Test-Path $c)) { $py = $c; break }
}
if (-not $py) { Log '找不到 Python，退出'; exit 1 }
$env:PYTHONIOENCODING = 'utf-8'

# --- 通道配好了吗？没配就安静退出，别天天报错 ---
$chFile = Join-Path $root 'channels.json'
$configured = $false
if (Test-Path $chFile) {
    try {
        $ch = Get-Content $chFile -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($ch.mail_pass -or $ch.pushplus_token -or $ch.serverchan_key -or $ch.webhook) { $configured = $true }
    } catch { }
}
if (-not $configured) { Log '还没有配置推送通道（channels.json 里没有 token），本次跳过'; exit 0 }

# --- 防重入 ---
$lock = Join-Path $root '.running'
if (Test-Path $lock) {
    if (((Get-Date) - (Get-Item $lock).LastWriteTime).TotalMinutes -lt 25) {
        Log '已有一次运行在进行，跳过'; exit 0
    }
}
Set-Content -Path $lock -Value (Get-Date -Format o)
try {
    # --- 周期判断 ---
    if (-not $Force) {
        $statePath = Join-Path $root 'state.json'
        if (Test-Path $statePath) {
            $st = Get-Content $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($st.last_sent) {
                $last = [datetime]::ParseExact($st.last_sent, 'yyyy-MM-dd HH:mm', $null)
                $days = ((Get-Date) - $last).TotalDays
                if ($days -lt 2.5) { Log ("距上期 {0:N1} 天，还没到 3 天，跳过" -f $days); exit 0 }
                Log ("距上期 {0:N1} 天，该发新一期了" -f $days)
            }
        }
    }

    # --- 1. 抓候选 ---
    if (-not $SkipFetch) {
        Log '抓 GitHub 新鲜 AI 项目…'
        & $py -X utf8 (Join-Path $root 'fetch_repos.py') --days 240 2>&1 | ForEach-Object { Log "$_" }
        if ($LASTEXITCODE -eq 3) { Log 'GitHub 打不开（梯子没开？）——本次跳过'; exit 0 }
        if ($LASTEXITCODE -ne 0) { Log "抓取失败 exit=$LASTEXITCODE"; exit 1 }
    }

    # --- 2. 组一期 ---
    Log '挑项目、组一期…'
    & $py -X utf8 (Join-Path $root 'build_auto_issue.py') --n 4 2>&1 | ForEach-Object { Log "$_" }
    $autoIssue = Join-Path $root 'auto-issue.json'
    if (-not (Test-Path $autoIssue)) { Log '没生成内容（候选可能都推过了），结束'; exit 0 }

    # --- 2.5 补中文 + 找配图 ---
    Log '翻成中文、找封面图…'
    & $py -X utf8 (Join-Path $root 'enrich.py') $autoIssue 2>&1 | ForEach-Object { Log "$_" }

    # --- 3. 渲染 ---
    & $py -X utf8 (Join-Path $root 'render_issue.py') $autoIssue 2>&1 | ForEach-Object { Log "$_" }

    # --- 4. 推送 ---
    if ($Dry) {
        & $py -X utf8 (Join-Path $root 'push.py') --issue $autoIssue --dry 2>&1 | ForEach-Object { Log "$_" }
        Log '（Dry 模式：没有真的发送）'
    }
    else {
        & $py -X utf8 (Join-Path $root 'push.py') --issue $autoIssue 2>&1 | ForEach-Object { Log "$_" }
        if ($LASTEXITCODE -ne 0) { Log "推送失败 exit=$LASTEXITCODE"; exit 1 }
        Log '这一期发出去了 ✅'
    }
}
finally {
    Remove-Item $lock -ErrorAction SilentlyContinue
}
