# Safety & Boundaries

## Principles

1. **Least privilege**: Agents get minimum required capabilities
2. **Explicit consent**: Dangerous operations require human approval
3. **Audit trail**: All actions logged
4. **Reversibility**: Prefer reversible actions
5. **Fail safe**: On uncertainty, ask rather than act

## Autonomy Levels

| Level | Name | Behavior |
|-------|------|----------|
| 0 | Inform only | Agent reports, human acts |
| 1 | Suggest | Agent proposes, human approves |
| 2 | Act + Report | Agent acts within bounds, reports after (default) |
| 3 | Full autonomous | Agent acts, periodic review |

## Safe Boundaries

| Category | Actions |
|----------|---------|
| **Allowed** | Read public info, analyze content, answer questions, draft messages, create local files, query memories |
| **Requires Approval** | Send messages, modify external files, external API calls, access sensitive memories, spend resources beyond threshold, schedule future actions |
| **Prohibited** | Access credentials without request, modify system files, arbitrary shell commands, share personal data externally, self-modify without test harness |

## Self-Modification Sandbox

**Flow**: Proposed Change → Test Harness → (pass) Accepted / (fail) Rejected

Process:
1. Agent proposes code change
2. Change applied in isolated branch
3. Full test suite runs
4. Static analysis checks
5. If pass: merge to main, notify user
6. If fail: reject, log reason, optionally retry

### Test Requirements
- Unit tests for modified functions
- Integration tests for affected flows
- Safety invariant checks
- No regression in existing tests
- Human review for core safety code

## Action Classification

```python
def classify_action(action: Action) -> ApprovalRequirement:
    if action.risk_level == RiskLevel.CRITICAL:
        return ApprovalRequirement.ALWAYS
    if action.risk_level == RiskLevel.HIGH and not action.reversible:
        return ApprovalRequirement.ALWAYS
    if action.type in APPROVED_ACTION_TYPES:
        return ApprovalRequirement.NEVER
    return ApprovalRequirement.ASK_ONCE  # Per session
```

## Audit Logging

All agent actions logged to append-only SQLite table:
```python
@dataclass
class AuditEntry:
    timestamp: datetime
    agent_id: str
    action: Action
    approval: ApprovalStatus  # auto, user_approved, denied
    result: ActionResult
    context_hash: str  # For replay/debugging
```

## Rate Limits & Cost Control

- Daily API cost budget (configurable)
- Per-agent rate limits
- Automatic fallback to cheaper models when budget low
- Alert user when approaching limits

## Privacy Protection

- PII tagged in memory system
- PII excluded from external API calls by default
- User controls what can be shared
- Memory encryption at rest (future)

## Emergency Procedures

**Kill Switch** (`/stop` or `/emergency`):
- Halt all agent activity
- Cancel pending actions
- Clear action queue
- Preserve state for debugging

**Recovery**:
- Automatic state snapshots before risky operations
- Rollback capability for file/data changes
- Manual recovery mode via CLI
