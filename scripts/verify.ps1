$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Invoke-Check {
    param([string]$Tool, [string[]]$ToolArgs)
    & $Tool @ToolArgs
    if ($LASTEXITCODE -ne 0) { throw "Verification failed: $Tool $ToolArgs" }
}

Invoke-Check 'uv' @('run', 'ruff', 'format', '--check', 'apps/api', 'scripts')
Invoke-Check 'uv' @('run', 'ruff', 'check', 'apps/api', 'scripts')
Invoke-Check 'uv' @('run', 'mypy')
Invoke-Check 'uv' @('run', 'pytest', '-q')
Invoke-Check 'npm' @('run', 'format:check')
Invoke-Check 'npm' @('run', 'lint')
Invoke-Check 'npm' @('run', 'typecheck')
Invoke-Check 'npm' @('test')
Invoke-Check 'npm' @('run', 'build')
Invoke-Check 'npm' @('run', 'test:e2e')
Write-Output 'All Slice 0 verification commands passed.'
