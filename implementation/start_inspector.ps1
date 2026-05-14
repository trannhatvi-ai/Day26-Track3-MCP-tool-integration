$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
$CachePath = Join-Path $RepoRoot ".npm-cache"
New-Item -ItemType Directory -Force -Path $CachePath | Out-Null

$env:NPM_CONFIG_CACHE = $CachePath
Push-Location $RepoRoot
try {
    npx -y @modelcontextprotocol/inspector py -m implementation.mcp_server
}
finally {
    Pop-Location
}

