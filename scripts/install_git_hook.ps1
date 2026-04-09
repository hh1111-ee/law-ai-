param()

# Install the repository pre-commit hook from .githooks/pre-commit to .git/hooks/pre-commit
$src = Join-Path $PSScriptRoot '..\.githooks\pre-commit' | Resolve-Path -ErrorAction Stop
$dst = Join-Path $PSScriptRoot '..\.git\hooks\pre-commit'
Write-Host "Installing pre-commit hook to $dst"
Copy-Item -Path $src -Destination $dst -Force
# Make sure it's executable in environments that respect the executable bit
try {
    icacls $dst /grant "$(whoami):(RX)" | Out-Null
} catch {
    # ignore
}
Write-Host 'Pre-commit hook installed. To enable repo-level hooks path, you can run:'
Write-Host "  git config core.hooksPath .githooks"
Write-Host 'Or leave the hook copied into .git/hooks for immediate effect.'
