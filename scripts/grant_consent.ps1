# Grant admin consent for Power BI Application permissions
# Run this in PowerShell as jonathan@autobi.co.uk (Global Admin / Privileged Role Admin)
#
# Prerequisites:
#   Install-Module Microsoft.Graph -Scope CurrentUser
#
# This bypasses the portal "DelegationScope 8000 char limit" bug by granting
# Application permissions (app roles) directly via Graph API.

$ErrorActionPreference = "Stop"

# Our app details
$AppClientId = "9ed15462-1e96-49b9-b362-aa86c139a177"
$PowerBIAppId = "00000009-0000-0000-c000-000000000000"

# Connect to Graph with required permissions
Write-Host "Connecting to Microsoft Graph..." -ForegroundColor Cyan
Connect-MgGraph -Scopes "AppRoleAssignment.ReadWrite.All,Application.Read.All" -NoWelcome

# Get our Service Principal
Write-Host "Finding AutoBI PowerBI MCP Service Principal..." -ForegroundColor Cyan
$ourSP = Get-MgServicePrincipal -Filter "appId eq '$AppClientId'"
if (-not $ourSP) { throw "Service Principal not found for appId $AppClientId" }
Write-Host "  SP: $($ourSP.DisplayName) ($($ourSP.Id))"

# Get Power BI Service Principal (the resource we're requesting permissions on)
$pbiSP = Get-MgServicePrincipal -Filter "appId eq '$PowerBIAppId'"
if (-not $pbiSP) { throw "Power BI Service Principal not found" }
Write-Host "  Power BI SP: $($pbiSP.DisplayName) ($($pbiSP.Id))"

# List available Power BI app roles
Write-Host "`nAvailable Power BI app roles:" -ForegroundColor Cyan
$pbiSP.AppRoles | Where-Object { $_.AllowedMemberTypes -contains "Application" } | ForEach-Object {
    Write-Host "  $($_.Value): $($_.Id)"
}

# Roles we want to grant
$rolesToGrant = @(
    "Tenant.Read.All",
    "Dataset.Read.All",
    "Dataset.ReadWrite.All"
)

# Check existing assignments
$existing = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $ourSP.Id
Write-Host "`nExisting role assignments: $($existing.Count)" -ForegroundColor Cyan
foreach ($a in $existing) {
    $roleName = ($pbiSP.AppRoles | Where-Object { $_.Id -eq $a.AppRoleId }).Value
    Write-Host "  $roleName ($($a.AppRoleId))"
}

# Grant each role
Write-Host "`nGranting roles..." -ForegroundColor Green
foreach ($roleName in $rolesToGrant) {
    $role = $pbiSP.AppRoles | Where-Object { $_.Value -eq $roleName -and $_.AllowedMemberTypes -contains "Application" }
    if (-not $role) {
        Write-Host "  SKIP: Role '$roleName' not found" -ForegroundColor Yellow
        continue
    }

    # Check if already granted
    $alreadyGranted = $existing | Where-Object { $_.AppRoleId -eq $role.Id }
    if ($alreadyGranted) {
        Write-Host "  SKIP: $roleName already granted" -ForegroundColor Yellow
        continue
    }

    $params = @{
        PrincipalId = $ourSP.Id
        ResourceId  = $pbiSP.Id
        AppRoleId   = $role.Id
    }

    try {
        New-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $ourSP.Id -BodyParameter $params | Out-Null
        Write-Host "  GRANTED: $roleName" -ForegroundColor Green
    }
    catch {
        Write-Host "  FAILED: $roleName - $_" -ForegroundColor Red
    }
}

# Verify
Write-Host "`nVerifying..." -ForegroundColor Cyan
$final = Get-MgServicePrincipalAppRoleAssignment -ServicePrincipalId $ourSP.Id
Write-Host "Total role assignments: $($final.Count)" -ForegroundColor Green
foreach ($a in $final) {
    $roleName = ($pbiSP.AppRoles | Where-Object { $_.Id -eq $a.AppRoleId }).Value
    Write-Host "  $roleName" -ForegroundColor Green
}

Disconnect-MgGraph | Out-Null
Write-Host "`nDone. Restart the MCP server to pick up new permissions." -ForegroundColor Cyan
