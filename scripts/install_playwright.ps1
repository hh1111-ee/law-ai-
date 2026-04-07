# scripts/install_playwright.ps1
# 一键安装/修复 Playwright Chromium 的辅助脚本（Windows PowerShell）
# 用法: 以管理员身份运行 PowerShell，然后:
#   powershell -ExecutionPolicy Bypass -File scripts\install_playwright.ps1

function Is-Administrator {
    $current = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

Write-Host "== Playwright Chromium 安装/修复脚本 =="

# Check for npx
$npx = Get-Command npx -ErrorAction SilentlyContinue
if (-not $npx) {
    Write-Host "未检测到 npx（Node.js/npm）。请先安装 Node.js (包含 npm)，再运行本脚本。" -ForegroundColor Yellow
    Write-Host "下载地址: https://nodejs.org/"
    exit 1
}

# Try to install chromium via Playwright
Write-Host "正在通过 npx playwright 下载 Chromium（可能需要较长时间）..."
try {
    npx playwright@latest install chromium
} catch {
    Write-Host "Playwright 安装步骤返回错误： $_" -ForegroundColor Red
}

# Attempt to create junction if version mismatch exists
$playwrightDir = Join-Path $env:LOCALAPPDATA 'ms-playwright'
if (-not (Test-Path $playwrightDir)) {
    Write-Host "未找到 Playwright 安装目录: $playwrightDir" -ForegroundColor Yellow
    exit 0
}

# Detect available chromium-* directories
$chromDirs = Get-ChildItem -Path $playwrightDir -Directory -Filter 'chromium-*' | Select-Object -ExpandProperty Name
if ($chromDirs.Count -eq 0) {
    Write-Host "未在 $playwrightDir 中找到 chromium-* 目录。安装可能失败或未下载。" -ForegroundColor Yellow
    exit 0
}

Write-Host "检测到的 chromium 目录： $($chromDirs -join ', ')"

# Define desired dir name (example: chromium-1200)
$desired = 'chromium-1200'
if ($chromDirs -contains $desired) {
    Write-Host "目标目录 $desired 已存在，修复无需执行。" -ForegroundColor Green
    exit 0
}

# Choose a candidate to link from (pick highest-numbered available)
$candidate = ($chromDirs | Sort-Object {[int]($_ -replace 'chromium-','') } -Descending)[0]
if (-not $candidate) {
    Write-Host "无法挑选候选目录创建联接" -ForegroundColor Yellow
    exit 0
}

Write-Host "尝试创建目录联接: $desired -> $candidate"
if (-not (Is-Administrator)) {
    Write-Host "当前非管理员权限，无法创建联接。请以管理员身份运行以下命令：" -ForegroundColor Yellow
    Write-Host "cd $playwrightDir"
    Write-Host "cmd /c \"mklink /J $desired $candidate\""
    exit 0
}

# Run mklink via cmd
Push-Location $playwrightDir
try {
    $cmd = "cmd /c `"mklink /J $desired $candidate`""
    Write-Host "Executing: $cmd"
    cmd /c "mklink /J $desired $candidate"
    Write-Host "已创建联接：$desired -> $candidate" -ForegroundColor Green
} catch {
    Write-Host "创建联接失败： $_" -ForegroundColor Red
} finally {
    Pop-Location
}

Write-Host "完成。若仍有问题请检查网络与磁盘空间，或查看 Playwright 安装日志。"