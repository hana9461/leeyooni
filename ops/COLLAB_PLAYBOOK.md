# Pair-Agent Collaboration Playbook

**Principle**: Code talks, chat only clarifies.
**Channels**: Git commits, PRs, ops/handoff/*.md (not Slack/email).

---

## Roles

### Claude (Terminal Agent)
- **Execute**: `git`, `bash`, tests, file I/O, commands
- **Assume**: Receive detailed commands in ops/handoff/TODAY.md
- **Deliver**: Commits with clean messages, PR links, error logs in ops/logs/

### Human (Designer/Reviewer)
- **Design**: Requirements, A/B trade-offs, Kill Gates in ops/handoff/*.md
- **Review**: PR logic, measurement results, blockers
- **Decide**: When to pivot, when to kill a branch

---

## File Structure

```
unslug-city/
├── .github/
│   └── PULL_REQUEST_TEMPLATE.md    # PR standard format
├── ops/
│   ├── COLLAB_PLAYBOOK.md          # This file (rules)
│   ├── handoff/
│   │   ├── TODAY.md                # Today's sprint (updated by human)
│   │   ├── PREV.md                 # Yesterday's summary
│   │   └── STATUS.md               # Running status (updated by Claude)
│   └── logs/
│       ├── errors.log              # Failed runs (Claude logs)
│       ├── measurements.json        # Perf/test data (Claude logs)
│       └── branches.log            # Branch activity (Claude logs)
├── reports/
│   ├── backtest_*.json             # Test reports
│   ├── calibration_*.png           # Reliability diagrams
│   └── metrics_*.json              # Perf snapshots
└── PROJECT_OVERVIEW.md             # Living strategy doc
```

---

## Git Workflow

### Branch Naming
```
feat/{feature-name}           # New feature
fix/{issue-name}              # Bug fix
refactor/{area}               # Code cleanup
test/{test-focus}             # Tests only
docs/{topic}                  # Documentation
chore/{task}                  # Setup, build, deps
```

### Commit Message Format
```
type(scope): subject

Body (if needed):
- Point 1
- Point 2

Closes: #N (if applicable)
Measurement: test_pass_rate=95%, perf_p99=123ms
```

**Examples**:
```
feat(core): add factor_calculations module with zscore, pct_rank, rolling_minmax

- Normalized factors to [0,1] scale
- Tested on SPY 5-year daily data
- Ready for trust_aggregation integration

Measurement: test_pass_rate=100%, coverage=85%

---

fix(scheduler): retry logic for Yahoo API timeouts

- Added exponential backoff (max 3 retries)
- Log failed attempts to ops/logs/errors.log
- Tested with synthetic delay injection

Measurement: timeout_recovery_success_rate=98%
```

### PR Workflow
1. Create branch from `main`
2. Work locally (commit frequently)
3. Push to remote: `git push -u origin {branch-name}`
4. Create PR with template (auto-filled from .github/)
5. Wait for reviewer approval
6. Merge only if Kill Gate + measurements pass

---

## Kill Gate Framework

Every task must have **explicit failure criteria**. Examples:

```yaml
Kill Gate (P2 - Factors/Trust):
  - Test pass rate < 90%  →  BLOCK (fix + rerun)
  - Factor scale ∉ [0,1]  →  BLOCK (fix normalization)
  - Commit message missing measurement  →  BLOCK (rewrite)

Kill Gate (P3 - Data Adapter):
  - 3-ticker daily pipe missing 1 day  →  WARN (check scheduler)
  - API call P99 > 5s  →  BLOCK (optimize or defer)
  - No error log entry  →  BLOCK (add logging)
```

**Default Actions**:
- BLOCK → do not merge until fixed
- WARN → log in ops/logs/measurements.json, document in PR
- INFO → track for post-launch improvement

---

## Evidence Framework (E1–E4)

Before starting any sprint:

**E1 (Structure)**: Are folders/templates/git config in place?
**E2 (State)**: What's the current code + doc status?
**E3 (Risk)**: What are failure modes? (data delay, test flake, etc.)
**E4 (Resources)**: Do we have keys, credentials, dependencies?

Document in PR description + ops/handoff/{date}.md.

---

## Handoff Daily Ritual

### Human → Claude (Daily Brief)
File: `ops/handoff/TODAY.md` (created by human before 09:00)

Contents:
```markdown
# TODAY.md — 2025-01-XX Sprint

## Objective
[High-level goal]

## P1 (blocker)
### Task Name
- Why: [rationale]
- Action: [CLI commands, file paths]
- A/B: [choices + trade-offs]
- Kill Gate: [failure criteria]
- Measurement: [success metrics]

## P2 (urgent)
...

## A/B Decisions
...

## Evidence (E1–E4)
...

## Success Criteria
- [ ] Checklist item 1
- [ ] Checklist item 2
```

### Claude → Human (Daily Report)
File: `ops/STATUS.md` (updated by Claude at end of day)

Contents:
```markdown
# STATUS — 2025-01-XX

## Completed
- [ ] P1 task: feat/core-factors-trust → PR #N
- [ ] P2 task: feat/data-adapter → PR #N

## Blocked
- [ ] P3 task: [reason + error log path]

## Metrics
| Metric | Target | Actual | Pass? |
|--------|--------|--------|-------|
| Test pass rate | 90% | 95% | ✅ |
| API P99 | <3s | 2.1s | ✅ |

## Next Steps
- Await review on PR #N
- If approved, deploy branch #N

## Logs
- errors.log: [summary of errors + line numbers]
- measurements.json: [snapshot of KPIs]
```

---

## Communication Rules

| Medium | Use | Don't |
|--------|-----|-------|
| Git commit msg | Explain WHY + MEASUREMENT | Chitchat |
| PR description | Summary + Kill Gate + Evidence | Vague descriptions |
| ops/handoff/*.md | Detailed specs + commands | Back-of-napkin notes |
| Bash logs | Error traces, timestamps, context | Swallowed errors |

---

## Rollback & Pivot

**Rollback Trigger**:
- Kill Gate not met for 2+ attempts
- Measurement shows regression (e.g., test drop, perf degrade)
- New blocker discovered mid-execution

**Action**:
1. `git reset --hard {last-known-good-commit}`
2. Document reason in `ops/logs/errors.log`
3. Update `ops/STATUS.md` with "Blocked" status
4. Wait for human decision to continue or pivot

**Pivot Trigger**:
- Evidence (E3/E4) shifts (e.g., API key expired, data source unavailable)
- A/B trade-off becomes untenable (e.g., time estimate 3x worse)
- Kill Gate reframes scope (e.g., "SPY 1-year only" instead of "all tickers")

---

## Testing & Validation

### Unit Tests
```bash
cd backend && pytest -q --tb=short
```
**Gate**: 90%+ pass rate (starting), 99%+ post-stabilization.

### Integration Tests
```bash
uvicorn backend.src.main:app --reload &
# [run endpoint tests]
```
**Gate**: All critical endpoints respond in <500ms (local).

### Performance
- Store results in `ops/logs/measurements.json`
- Track: p50, p99, error_rate per endpoint
- **Gate**: p99 < target (varies by feature)

---

## Reference

- **PROJECT_OVERVIEW.md**: Strategy & long-term vision
- **ops/handoff/TODAY.md**: Today's sprint (human-written)
- **ops/COLLAB_PLAYBOOK.md**: This file (collaboration rules)
- **GitHub Issues**: Persistent discussion (optional; use PRs first)

---

## Approvals & Merges

### PR Approval Checklist
- [ ] Code follows COLLAB_PLAYBOOK
- [ ] Tests pass (log: pytest output)
- [ ] Kill Gate met
- [ ] Measurement captured
- [ ] Commit message complete
- [ ] No merge conflicts

### Merge Strategy
- **Default**: Squash + merge (keeps main history clean)
- **Exception**: If branch has logical commit breakdown, use rebase + merge

---

**Last Updated**: 2025-01-XX
**Owner**: Collaboration Framework
**Version**: 1.0
