#!/bin/bash
# Close a GitHub issue with fix details
# Usage: close_issue.sh <issue_number> "fix description"

REPO="hussi9/podcastos"
ISSUE_NUM="$1"
FIX_DESC="$2"

if [ -z "$ISSUE_NUM" ]; then
    echo "Usage: close_issue.sh <issue_number> <fix_description>"
    exit 1
fi

# Add fix comment
COMMENT="## Fix Applied

$FIX_DESC

---
*Fixed by Claude Code - $(date '+%Y-%m-%d %H:%M:%S')*"

gh issue comment "$ISSUE_NUM" --repo "$REPO" --body "$COMMENT"

# Add fix-applied label and close
gh issue edit "$ISSUE_NUM" --repo "$REPO" --add-label "fix-applied"
gh issue close "$ISSUE_NUM" --repo "$REPO"

echo "Issue #$ISSUE_NUM closed with fix"
