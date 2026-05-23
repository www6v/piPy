#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

usage() {
    echo "Usage: $0 <commit-message>"
    echo "  Stage all changes, commit on master, and push to origin."
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

commit_message="$*"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "error: not a git repository" >&2
    exit 1
fi

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "master" ]]; then
    git checkout master
fi

git add -A

if git diff --cached --quiet; then
    echo "nothing to commit, working tree clean"
    exit 0
fi

git commit -m "$commit_message"
git push origin master

echo "committed and pushed to origin/master"
