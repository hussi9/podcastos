# GitHub Issue Tracking Rules

## Automatic Issue Tracking

When working on this project, Claude MUST track issues to GitHub:

### When to Create Issues

1. **Gaps Identified** (label: `gap`)
   - Missing functionality discovered during development
   - Features that should exist but don't
   - Integration points that are incomplete

2. **Bugs/Issues Found** (label: `issue-found`)
   - Runtime errors encountered
   - Logic errors discovered
   - Failed tests indicating problems
   - Security vulnerabilities identified

3. **Fixes Applied** (label: `fix-applied`)
   - When closing an issue after implementing a fix

### How to Track

Use the GitHub MCP tools directly:

```
# Create an issue
mcp__github__create_issue with:
- owner: "hussi9"
- repo: "podcastos"
- title: "Brief description"
- body: "Detailed description with context"
- labels: ["claude-tracked", "gap|issue-found"]

# Close with fix
mcp__github__add_issue_comment to document fix
mcp__github__update_issue to close
```

Or use helper scripts:
```bash
./scripts/github/track_issue.sh "gap" "Title" "Description" "file:line"
./scripts/github/close_issue.sh <issue_number> "Fix description"
./scripts/github/list_issues.sh [open|closed|all]
```

### Issue Format

**Title**: `[TYPE] Brief description`
- `[GAP]` - Missing functionality
- `[BUG]` - Something broken
- `[PERF]` - Performance issue
- `[SEC]` - Security concern

**Body**:
```markdown
## Description
What was found

## Context
- File: `path/to/file.py:123`
- Component: affected area
- Severity: low/medium/high/critical

## Steps to Reproduce (for bugs)
1. Step one
2. Step two

## Suggested Fix (if known)
Potential solution
```

### Tracking Workflow

1. **Discovery** → Create issue immediately with `claude-tracked` + type label
2. **Investigation** → Add comments with findings
3. **Fix Implementation** → Reference issue in commits
4. **Verification** → Add `fix-applied` label and close

### Quick Commands

- Track gap: `./scripts/github/track_issue.sh gap "Missing X" "Need to implement X"`
- Track bug: `./scripts/github/track_issue.sh issue-found "Bug in Y" "Error when Z"`
- List open: `./scripts/github/list_issues.sh open`
- Close issue: `./scripts/github/close_issue.sh 123 "Fixed by implementing..."`
