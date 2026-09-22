# Build (if needed) and start the Spring Boot web application.
#
# Usage:  powershell -ExecutionPolicy Bypass -File run_web.ps1
#
# Prerequisites:
#   1. MySQL running  ->  run_mysql.ps1   (or: powershell -File ..\..\.tools\run_mysql.ps1)
#   2. Data loaded    ->  python src\step7_mysql.py
#
# Then open http://localhost:8080
#
# NOTE: keep this file ASCII-only - Windows PowerShell 5.1 reads BOM-less
#       UTF-8 .ps1 files as ANSI and would corrupt non-ASCII characters.

$ErrorActionPreference = "Stop"

$javaHome  = "D:\jdk-8u471-windows-x64\jdk1.8.0_471"
$maven     = "F:\myprogect\.tools\apache-maven-3.9.9\bin\mvn.cmd"
$settings  = "F:\myprogect\02-课程实验\maven-settings-aliyun.xml"
$repo      = "F:\myprogect\.tools\m2repo"
$webDir    = Join-Path $PSScriptRoot "web"
$jar       = Join-Path $webDir "target\air-quality-web.jar"

if (-not (Test-Path (Join-Path $javaHome "bin\java.exe"))) {
    Write-Host "[X] JDK 8 not found at: $javaHome" -ForegroundColor Red
    Write-Host "    Edit `$javaHome at the top of this script."
    exit 1
}
$env:JAVA_HOME = $javaHome

# ---------- 1. build if the jar is missing ----------
if (-not (Test-Path $jar)) {
    Write-Host "[1/2] Building jar (first run, may take a while) ..." -ForegroundColor Cyan
    Push-Location $webDir
    $mvnArgs = @("-s", $settings, "-Dmaven.repo.local=$repo", "-B", "clean", "package", "-DskipTests")
    & $maven @mvnArgs
    $code = $LASTEXITCODE
    Pop-Location
    if ($code -ne 0) { throw "Maven build failed" }
} else {
    Write-Host "[1/2] jar already exists, skipping build" -ForegroundColor Green
    Write-Host "      (delete target\ to force a rebuild)"
}

# ---------- 2. check MySQL ----------
$mysqlUp = Get-NetTCPConnection -LocalPort 3307 -State Listen -ErrorAction SilentlyContinue
if (-not $mysqlUp) {
    Write-Host "[!] MySQL is NOT listening on 3307." -ForegroundColor Yellow
    Write-Host "    Start it first:  powershell -File F:\myprogect\.tools\run_mysql.ps1"
    Write-Host ""
    Write-Host "    Continuing anyway - the web app will start but the APIs will fail."
    Write-Host ""
}

# ---------- 3. run ----------
Write-Host "[2/2] Starting Spring Boot on http://localhost:8080" -ForegroundColor Cyan
Write-Host "      press Ctrl+C to stop"
Write-Host ""
& (Join-Path $javaHome "bin\java.exe") @("-Dfile.encoding=UTF-8", "-jar", $jar)
