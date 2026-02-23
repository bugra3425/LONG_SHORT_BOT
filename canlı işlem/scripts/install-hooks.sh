#!/bin/bash
# Git Hooks Installer for Unix/Linux/Mac
# Usage: ./scripts/install-hooks.sh

set -e

echo "🔧 Installing Git Hooks..."

# Get paths
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOKS_SOURCE="$REPO_ROOT/.git-hooks"
HOOKS_TARGET="$REPO_ROOT/.git/hooks"

# Check if .git exists
if [ ! -d "$HOOKS_TARGET" ]; then
    echo "❌ .git directory not found. Are you in a git repository?"
    exit 1
fi

# Copy hooks
HOOKS=("commit-msg" "pre-commit")

for hook in "${HOOKS[@]}"; do
    SOURCE="$HOOKS_SOURCE/$hook"
    TARGET="$HOOKS_TARGET/$hook"
    
    if [ -f "$SOURCE" ]; then
        cp "$SOURCE" "$TARGET"
        chmod +x "$TARGET"
        echo "  ✅ Installed: $hook"
    else
        echo "  ⚠️  Not found: $hook"
    fi
done

echo ""
echo "🎉 Git hooks installed successfully!"
echo ""
echo "Commit message format:"
echo "  <type>(<scope>): <subject>"
echo ""
echo "Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert"
