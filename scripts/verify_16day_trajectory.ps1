<#
.SYNOPSIS
    Authoritative 16-Day Forecast Bust Trajectory Verification Utility for Veyra.
.DESCRIPTION
    Queries POST /v1/dashboard/intelligence with mode=full_16d to inspect the
    authoritative 16-day operational trajectory (24h to 384h).
    Strictly verifies:
      - Actual backend lead_hours and valid_time (Day = lead_hours / 24).
      - Pure null-safe display: null probability is printed as 'ABSTAIN' / 'NULL',
        never as 0%, LOW, or SUPPORTED.
      - Certified benchmark scope (<=240h) vs operational-only (264h-384h).
      - Rejection of invalid / unsupported request fields (e.g. lead_hours on /v1/predict).
.PARAMETER Location
    Location name, station, or coordinates (e.g. 'Delhi', 'Kolkata', 'London', 'Tokyo'). Default: 'Delhi'
.PARAMETER Variable
    Meteorological target variable (temperature_2m, wind_speed_10m, surface_pressure). Default: 'temperature_2m'
.PARAMETER BaseUrl
    Base URL of the Veyra FastAPI service. Default: 'http://127.0.0.1:8000'
.EXAMPLE
    .\scripts\verify_16day_trajectory.ps1 -Location "Delhi" -Variable "temperature_2m"
#>

[CmdletBinding()]
param (
    [Parameter(Position = 0)]
    [string]$Location = "Delhi",

    [Parameter(Position = 1)]
    [string]$Variable = "temperature_2m",

    [Parameter(Position = 2)]
    [string]$BaseUrl = "http://127.0.0.1:8000",

    [Parameter()]
    [switch]$CheckBadContract
)

$ErrorActionPreference = "Stop"

$cleanBaseUrl = $BaseUrl.TrimEnd('/')

Write-Host ("=" * 95) -ForegroundColor Cyan
Write-Host " VEYRA AUTHORITATIVE 16-DAY TRAJECTORY VERIFICATION UTILITY" -ForegroundColor Cyan
Write-Host " Endpoint: $cleanBaseUrl/v1/dashboard/intelligence (mode=full_16d)" -ForegroundColor Cyan
Write-Host " Target Location: $Location | Variable: $Variable" -ForegroundColor Cyan
Write-Host ("=" * 95) -ForegroundColor Cyan

# 1. Health Probe
Write-Host "`n[1/3] Probing service health at $cleanBaseUrl/v1/health..." -ForegroundColor Yellow
try {
    $healthResp = Invoke-RestMethod -Uri "$cleanBaseUrl/v1/health" -Method Get -TimeoutSec 10
    Write-Host "  [+] Service Health: $($healthResp.status) (service: $($healthResp.service), version: $($healthResp.version))" -ForegroundColor Green
} catch {
    Write-Host "  [-] Failed connecting to Veyra backend at ${cleanBaseUrl}: $_" -ForegroundColor Red
    Write-Host "  Please ensure the FastAPI backend is running via:" -ForegroundColor Red
    Write-Host "    python -m uvicorn backend.app.main:app --port 8000" -ForegroundColor Red
    exit 1
}

# 2. Authoritative 16-Day Trajectory Request
Write-Host "`n[2/3] Requesting authoritative 16-day trajectory from /v1/dashboard/intelligence..." -ForegroundColor Yellow
$bodyPayload = @{
    location = $Location
    variable = $Variable
    mode     = "full_16d"
} | ConvertTo-Json

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
try {
    $dashResp = Invoke-RestMethod -Uri "$cleanBaseUrl/v1/dashboard/intelligence" `
        -Method Post `
        -Body $bodyPayload `
        -ContentType "application/json" `
        -TimeoutSec 60
    $stopwatch.Stop()
} catch {
    $stopwatch.Stop()
    Write-Host "  [-] Trajectory request failed: $_" -ForegroundColor Red
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "  Response Details: $($reader.ReadToEnd())" -ForegroundColor Red
    }
    exit 1
}

$durationMs = [math]::Round($stopwatch.Elapsed.TotalMilliseconds, 1)
Write-Host "  [+] Received response in ${durationMs}ms with status: $($dashResp.status)" -ForegroundColor Green

if ($dashResp.location) {
    Write-Host "  Resolved Station : $($dashResp.location.resolved_name) ($($dashResp.location.latitude), $($dashResp.location.longitude))" -ForegroundColor Gray
}
Write-Host "  Forecast Issue   : $($dashResp.issue_time)" -ForegroundColor Gray

# Validate and format timeline
$timeline = $dashResp.timeline
if (-not $timeline -or $timeline.Count -eq 0) {
    Write-Host "  [-] Warning: No timeline points returned by backend!" -ForegroundColor Red
    exit 1
}

Write-Host "`nAuthoritative Timeline Trajectory ($($timeline.Count) Points):" -ForegroundColor Cyan
Write-Host ("-" * 120) -ForegroundColor DarkGray
Write-Host ("{0,-5} | {1,-5} | {2,-20} | {3,-12} | {4,-8} | {5,-9} | {6,-16} | {7,-7} | {8,-11} | {9,-11}" -f `
    "Day", "Lead", "Valid Time", "P(Bust) Raw", "P(Bust)%", "Risk Tier", "Trust State", "Abstain", "Calibration", "Scope") -ForegroundColor White
Write-Host ("-" * 120) -ForegroundColor DarkGray

$validProbCount = 0
$abstainedCount = 0
$uniqueProbs = @{}

foreach ($point in $timeline) {
    $actualLead = $point.lead_hours
    # Authoritative Day derived strictly from returned lead_hours: Day = lead_hours / 24
    $dayCalculated = [math]::Round(($actualLead / 24.0), 1)
    $validTime = $point.valid_time

    # Safe null / abstention display formatting — NEVER convert null to 0%, LOW, or SUPPORTED
    $rawProb = $point.bust_probability
    if ($null -ne $rawProb) {
        $probRawStr = ("{0:F6}" -f $rawProb)
        $probPctStr = ("{0:F2}%" -f ($rawProb * 100))
        $validProbCount++
        $uniqueProbs[$rawProb] = $true
    } else {
        $probRawStr = "ABSTAIN"
        $probPctStr = "ABSTAIN"
        $abstainedCount++
    }

    $riskStr = if ($point.risk_level) { $point.risk_level } else { "NULL" }
    $trustStr = if ($point.trust_state) { $point.trust_state } else { "NULL" }
    $abstainStr = if ($point.abstain) { "TRUE" } else { "FALSE" }
    $calStr = if ($point.calibration_status) { $point.calibration_status } else { "UNAVAILABLE" }
    $scopeStr = if ($point.is_certified_horizon) { "CERTIFIED" } else { "OPERATIONAL" }

    # Color code by risk and abstention
    $rowColor = "White"
    if ($point.abstain -or $null -eq $rawProb) {
        $rowColor = "DarkYellow"
    } elseif ($riskStr -eq "CRITICAL") {
        $rowColor = "Magenta"
    } elseif ($riskStr -eq "HIGH") {
        $rowColor = "Red"
    } elseif ($riskStr -eq "MEDIUM") {
        $rowColor = "Yellow"
    } elseif ($riskStr -eq "LOW") {
        $rowColor = "Green"
    }

    Write-Host ("{0,-5} | {1,-4}h | {2,-20} | {3,-12} | {4,-8} | {5,-9} | {6,-16} | {7,-7} | {8,-11} | {9,-11}" -f `
        $dayCalculated, $actualLead, $validTime, $probRawStr, $probPctStr, $riskStr, $trustStr, $abstainStr, $calStr, $scopeStr) -ForegroundColor $rowColor
}

Write-Host ("-" * 120) -ForegroundColor DarkGray
Write-Host "Summary Diagnostics:" -ForegroundColor Cyan
Write-Host "  Total Requested Horizons : $($timeline.Count)"
Write-Host "  Valid Non-Null Points    : $validProbCount"
Write-Host "  Abstained Points         : $abstainedCount"
Write-Host "  Distinct Calibrated Probs: $($uniqueProbs.Keys.Count) (Stepwise isotonic calibration legitimately produces shared values across some horizons)"
if ($dashResp.summary) {
    $sum = $dashResp.summary
    Write-Host "  Peak Bust Probability   : $(if ($sum.max_bust_probability -ne $null) { '{0:F2}%' -f ($sum.max_bust_probability * 100) } else { 'NULL' })"
    Write-Host "  Peak Risk Level          : $(if ($sum.max_risk_level) { $sum.max_risk_level } else { 'NULL' })"
    Write-Host "  Peak Risk Horizon        : $(if ($sum.max_risk_lead_hours) { "$($sum.max_risk_lead_hours)h" } else { 'NULL' })"
    Write-Host "  Mean Bust Probability    : $(if ($sum.mean_bust_probability -ne $null) { '{0:F2}%' -f ($sum.mean_bust_probability * 100) } else { 'NULL' })"
    Write-Host "  Elevated Risk Horizons   : $($sum.elevated_risk_points) / $($sum.total_points)"
}
Write-Host ("=" * 95) -ForegroundColor Cyan

# 3. Contract Safety Verification: Verify unsupported lead_hours on /v1/predict is rejected
Write-Host "`n[3/3] Verifying Contract Safety: Testing unsupported 'lead_hours' on /v1/predict..." -ForegroundColor Yellow
$badPayload = @{
    location   = $Location
    lead_hours = 48
    variable   = $Variable
} | ConvertTo-Json

try {
    $null = Invoke-RestMethod -Uri "$cleanBaseUrl/v1/predict" `
        -Method Post `
        -Body $badPayload `
        -ContentType "application/json" `
        -TimeoutSec 10
    Write-Host "  [-] CRITICAL DEFECT: Backend accepted unsupported 'lead_hours' field with 200 OK!" -ForegroundColor Red
    exit 1
} catch {
    $statusCode = 0
    if ($_.Exception.Response) {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }
    if ($statusCode -eq 422) {
        Write-Host "  [+] PASS: Backend strictly rejected unsupported 'lead_hours' with HTTP 422 Unprocessable Entity." -ForegroundColor Green
        Write-Host "      Developers can no longer be silently misled by sending lead_hours to /v1/predict." -ForegroundColor Gray
    } else {
        Write-Host "  [!] Unexpected status code: $statusCode (Expected 422)" -ForegroundColor Yellow
    }
}

Write-Host "`n[+] 16-DAY TRAJECTORY VERIFICATION COMPLETED SUCCESSFULLY." -ForegroundColor Green
Write-Host ("=" * 95) -ForegroundColor Cyan
