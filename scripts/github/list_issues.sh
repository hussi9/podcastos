#!/bin/bash
# List Claude-tracked issues
# Usage: list_issues.sh [state]

REPO="hussi9/podcastos"
STATE="${1:-open}"  # open, closed, all

gh issue list \
    --repo "$REPO" \
    --label "claude-tracked" \
    --state "$STATE" \
    --limit 50
