<#
.SYNOPSIS
    Parallel build and deploy for OpenInsure backend + dashboard.
.DESCRIPTION
    THE standard way to build and deploy OpenInsure. Uses parallel ACR builds.
    Auto-increments version from latest ACR tag if not specified.
.PARAMETER Version
    Version tag suffix (e.g., 48 -> openinsure-backend:v48). Auto-detected if omitted.
.PARAMETER BackendOnly
    Only build/deploy the backend
.PARAMETER DashboardOnly
    Only build/deploy the dashboard
.EXAMPLE
    pwsh scripts/deploy.ps1                    # auto-version, both
    pwsh scripts/deploy.ps1 -BackendOnly       # auto-version, backend only
    pwsh scripts/deploy.ps1 -Version 55        # explicit version
#>
param(
    [int]$Version = 0,
    [switch]$BackendOnly,
    [switch]$DashboardOnly
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

$registry = "openinsuredevacr"
$rg = "openinsure-dev-sc"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent

# Auto-detect next version from ACR if not specified
if ($Version -eq 0) {
    try {
        $tags = az acr repository show-tags --name $registry --repository openinsure-backend --orderby time_desc --top 1 -o tsv 2>$null
        if ($tags -match 'v(\d+)') { $Version = [int]$Matches[1] + 1 }
        else { $Version = 1 }
    } catch { $Version = 1 }
}

Write-Host "`n=== OpenInsure Deploy v$Version ===" -ForegroundColor Cyan
Write-Host "   Registry: $registry | RG: $rg" -ForegroundColor DarkGray

$backendTag = "openinsure-backend:v$Version"
$dashboardTag = "openinsure-dashboard:v$Version"
$jobs = @()

$sw = [System.Diagnostics.Stopwatch]::StartNew()

if (-not $DashboardOnly) {
    Write-Host "Building backend ($backendTag)..." -ForegroundColor Yellow
    $jobs += Start-Job -Name "backend-build" -ScriptBlock {
        param($reg, $tag, $root)
        $env:PYTHONIOENCODING = "utf-8"
        az acr build --registry $reg --image $tag --file "$root\Dockerfile" $root --no-logs 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Backend build failed" }
    } -ArgumentList $registry, $backendTag, $repoRoot
}

if (-not $BackendOnly) {
    Write-Host "Building dashboard ($dashboardTag)..." -ForegroundColor Yellow
    $jobs += Start-Job -Name "dashboard-build" -ScriptBlock {
        param($reg, $tag, $root)
        $env:PYTHONIOENCODING = "utf-8"
        az acr build --registry $reg --image $tag --file "$root\dashboard\Dockerfile" "$root\dashboard" --no-logs 2>&1
        if ($LASTEXITCODE -ne 0) { throw "Dashboard build failed" }
    } -ArgumentList $registry, $dashboardTag, $repoRoot
}

Write-Host "Waiting for parallel builds..." -ForegroundColor DarkGray
$jobs | Wait-Job | Out-Null
$buildTime = $sw.Elapsed.TotalSeconds

$failed = $jobs | Where-Object { $_.State -eq "Failed" }
if ($failed) {
    Write-Host "Build failed:" -ForegroundColor Red
    $failed | Receive-Job
    exit 1
}
$jobs | Receive-Job | Out-Null
Write-Host "Builds completed in $([math]::Round($buildTime))s" -ForegroundColor Green

$sw.Restart()

if (-not $DashboardOnly) {
    Write-Host "Deploying backend..." -ForegroundColor Yellow
    az containerapp update --name openinsure-backend --resource-group $rg --image "$registry.azurecr.io/$backendTag" --output none 2>&1
    Write-Host "Backend deployed" -ForegroundColor Green
}

if (-not $BackendOnly) {
    Write-Host "Deploying dashboard..." -ForegroundColor Yellow
    az containerapp update --name openinsure-dashboard --resource-group $rg --image "$registry.azurecr.io/$dashboardTag" --output none 2>&1
    Write-Host "Dashboard deployed" -ForegroundColor Green
}

$deployTime = $sw.Elapsed.TotalSeconds
Write-Host "`n--- Deploy Summary ---" -ForegroundColor Cyan
Write-Host "   Build:  $([math]::Round($buildTime))s | Deploy: $([math]::Round($deployTime))s | Total: $([math]::Round($buildTime + $deployTime))s" -ForegroundColor White
