[CmdletBinding()]
param(
    [string]$OutputDirectory
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $PSScriptRoot "..\backups"
}

function Import-DatabaseEnvironment {
    param([string]$EnvironmentFile)

    if (-not (Test-Path -LiteralPath $EnvironmentFile)) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $EnvironmentFile) {
        if ($line -match '^\s*([^#=\s]+)\s*=\s*(.*)\s*$') {
            $name = $matches[1]
            $value = $matches[2]
            if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name, "Process"))) {
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
}

Import-DatabaseEnvironment (Join-Path $PSScriptRoot "..\.env")

$requiredVariables = "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"
$missingVariables = @(
    $requiredVariables | Where-Object {
        [string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($_, "Process"))
    }
)

if ($missingVariables.Count -gt 0) {
    throw "Missing required database configuration: $($missingVariables -join ', ')."
}

$pgDump = Get-Command pg_dump -ErrorAction SilentlyContinue
if ($null -eq $pgDump) {
    throw "pg_dump was not found on PATH. Install PostgreSQL command-line tools before creating a backup."
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

$safeDatabaseName = $env:DB_NAME -replace '[^A-Za-z0-9._-]', '_'
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = Join-Path $OutputDirectory "${safeDatabaseName}_${timestamp}.dump"

if (Test-Path -LiteralPath $backupPath) {
    throw "Refusing to overwrite an existing backup: $backupPath"
}

$previousPassword = $env:PGPASSWORD
try {
    $env:PGPASSWORD = $env:DB_PASSWORD
    & $pgDump.Source `
        "--host=$($env:DB_HOST)" `
        "--port=$($env:DB_PORT)" `
        "--username=$($env:DB_USER)" `
        "--format=custom" `
        "--file=$backupPath" `
        "--dbname=$($env:DB_NAME)"

    if ($LASTEXITCODE -ne 0) {
        throw "pg_dump failed with exit code $LASTEXITCODE."
    }
} finally {
    if ($null -eq $previousPassword) {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    } else {
        $env:PGPASSWORD = $previousPassword
    }
}

Write-Output "Database backup created: $backupPath"
