param(
    [string] $LogPath = ''
)

$ErrorActionPreference = 'Stop'
$compiler = 'git+https://github.com/deltathedumb/asmpython.git@376cf9422c28123673a1dedd7dd66b845f3c5ed1'
$python = (Get-Command python -ErrorAction Stop).Source

function Write-InstallLog([string] $Text) {
    Write-Host $Text
    if ($LogPath) {
        $Text | Out-File -FilePath $LogPath -Encoding utf8 -Append
    }
}

for ($attempt = 1; $attempt -le 3; $attempt += 1) {
    Write-InstallLog "Installing pinned asmpython (attempt $attempt/3)"
    $stdout = Join-Path $env:RUNNER_TEMP "asmpython-install-$attempt.stdout.log"
    $stderr = Join-Path $env:RUNNER_TEMP "asmpython-install-$attempt.stderr.log"
    Remove-Item $stdout, $stderr -Force -ErrorAction SilentlyContinue

    $process = Start-Process `
        -FilePath $python `
        -ArgumentList @(
            '-m', 'pip', 'install',
            '--no-cache-dir', '--force-reinstall',
            $compiler
        ) `
        -Wait `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr

    foreach ($path in @($stdout, $stderr)) {
        if (Test-Path $path) {
            Get-Content $path | ForEach-Object { Write-InstallLog $_ }
        }
    }
    if ($process.ExitCode -eq 0) {
        Write-InstallLog 'Pinned asmpython installation succeeded.'
        exit 0
    }
    Write-InstallLog "Pinned asmpython installation failed with exit code $($process.ExitCode)."
    if ($attempt -lt 3) {
        Start-Sleep -Seconds (10 * $attempt)
    }
}

throw 'Pinned asmpython installation failed after 3 attempts.'
