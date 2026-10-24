#!/bin/bash
# ════════════════════════════════════════════════════════
# 🐕 Perrobotillo Trading Bot - Version Command
# ════════════════════════════════════════════════════════
# Uso:
#   ./crypto-bots/version.sh          # Print version
#   ./crypto-bots/version.sh --json   # Print version as JSON
#   ./crypto-bots/version.sh --check  # Compare local vs remote tag

set -euo pipefail

WORKSPACE="${WORKSPACE:-$(printf '%s' "$HOME/.openclaw/workspace")}"
VERSION_FILE="${WORKSPACE}/VERSION"
REPO_DIR="${WORKSPACE}"

get_version() {
    # Try VERSION file first, then git describe, then fallback
    if [ -f "$VERSION_FILE" ]; then
        cat "$VERSION_FILE" | tr -d '[:space:]'
    elif [ -d "$REPO_DIR/.git" ]; then
        git -C "$REPO_DIR" describe --tags --always --dirty 2>/dev/null || echo "unknown"
    else
        echo "unknown"
    fi
}

case "${1:-}" in
    --json)
        version=$(get_version)
        git_hash=""
        if [ -d "$REPO_DIR/.git" ]; then
            git_hash=$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
        fi
        echo "{\"version\": \"$version\", \"git_hash\": \"$git_hash\"}"
        ;;
    --check)
        echo "Checking for updates..."
        version=$(get_version)
        echo "  Local version: $version"
        if [ -d "$REPO_DIR/.git" ]; then
            git -C "$REPO_DIR" fetch --tags --quiet 2>/dev/null || true
            latest_tag=$(git -C "$REPO_DIR" describe --tags "$(git -C "$REPO_DIR" rev-list --tags --max-count=1)" 2>/dev/null || echo "unknown")
            echo "  Latest tag: $latest_tag"
            if [ "$version" = "$latest_tag" ]; then
                echo "  ✅ You are on the latest release"
            else
                echo "  ⚠️  A new release is available: $latest_tag"
            fi
        fi
        ;;
    *)
        get_version
        ;;
esac
