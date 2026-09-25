# Change Plan: [NAME]

**Date:** YYYY-MM-DD
**Status:** PENDING REVIEW | APPROVED | IMPLEMENTED | REJECTED
**Risk Level:** LOW | MEDIUM | HIGH
**Files Affected:** [list]

## 🎯 Problem Statement
[2-3 sentences describing the problem]

## 📍 Changes Required

### Change #1: [Description]
- **File:** [path]
- **Function:** [name]
- **Line:** [number]
- **Type:** REPLACE | ADD | DELETE

**BEFORE:**
[exact current code]

**AFTER:**
[exact new code]

**Rationale:** [why this change]

## ⚠️ Risk Assessment
| Risk | Impact | Mitigation |
|------|--------|------------|
| [risk] | [impact] | [how to handle] |

## 🧪 Verification Plan
1. [test step 1]
2. [test step 2]
- Expected log output: [what to look for]

## 🔄 Rollback Plan
```bash
git reset --hard HEAD~1
git push origin main --force
git push hf main --force
```

## 📊 Expected Outcome
- Before: [current behavior]
- After: [expected behavior]

## 📝 Implementation Notes (filled AFTER implementation)
- Actual files changed: [list]
- Actual lines changed: [numbers]
- Test results: [pass/fail]
- Logs verified: [yes/no]
- Deployed to HF: [yes/no]
