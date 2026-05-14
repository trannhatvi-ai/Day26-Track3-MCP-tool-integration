#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export NPM_CONFIG_CACHE="$repo_root/.npm-cache"
mkdir -p "$NPM_CONFIG_CACHE"

cd "$repo_root"
npx -y @modelcontextprotocol/inspector python -m implementation.mcp_server

