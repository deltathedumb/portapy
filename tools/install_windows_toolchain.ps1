$ErrorActionPreference = 'Stop'

function Add-ToolDirectory([string] $ExecutablePath) {
    $directory = Split-Path -Parent $ExecutablePath
    if (-not ($env:PATH -split ';' | Where-Object { $_ -eq $directory })) {
        $env:PATH = "$directory;$env:PATH"
        if ($env:GITHUB_PATH) {
            $directory | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
        }
    }
}

function Find-Tool([string] $Name, [string[]] $Candidates) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    foreach ($candidate in $Candidates) {
        if (Test-Path $candidate) {
            Add-ToolDirectory $candidate
            return $candidate
        }
    }
    return $null
}

function Install-ChocolateyPackage([string] $Package) {
    $successCodes = @(0, 1641, 3010)
    for ($attempt = 1; $attempt -le 3; $attempt += 1) {
        Write-Host "Installing $Package with Chocolatey (attempt $attempt/3)"
        & choco install $Package -y --no-progress --limit-output
        $status = $LASTEXITCODE
        if ($successCodes -contains $status) {
            return
        }
        if ($attempt -lt 3) {
            Start-Sleep -Seconds (10 * $attempt)
        }
    }
    throw "Chocolatey could not install $Package (exit code $status)"
}

$nasmCandidates = @(
    'C:\Program Files\NASM\nasm.exe',
    'C:\ProgramData\chocolatey\bin\nasm.exe',
    'C:\tools\nasm\nasm.exe'
)
$gccCandidates = @(
    'C:\msys64\mingw64\bin\gcc.exe',
    'C:\mingw64\bin\gcc.exe',
    'C:\tools\mingw64\bin\gcc.exe',
    'C:\ProgramData\mingw64\mingw64\bin\gcc.exe'
)

$nasm = Find-Tool 'nasm' $nasmCandidates
if (-not $nasm) {
    Install-ChocolateyPackage 'nasm'
    $nasm = Find-Tool 'nasm' $nasmCandidates
}
if (-not $nasm) {
    throw 'NASM was not found after installation'
}

$gcc = Find-Tool 'gcc' $gccCandidates
if (-not $gcc) {
    Install-ChocolateyPackage 'mingw'
    $gcc = Find-Tool 'gcc' $gccCandidates
}
if (-not $gcc) {
    throw 'MinGW GCC was not found after installation'
}

Add-ToolDirectory $nasm
Add-ToolDirectory $gcc

Write-Host "NASM: $nasm"
& nasm -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "GCC: $gcc"
& gcc --version
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
