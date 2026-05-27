# Mikado Method for Agentic Refactoring

Never push through cascading failures. Let failures reveal prerequisites, record them in a dependency graph, revert to green, and work bottom-up from leaf nodes.

## The Loop

1. **Set the goal.** State the refactoring as a single concrete change. This is the root node.
2. **Ensure failure detection.** Verify test coverage over affected code paths. If inadequate, add test-writing as the first prerequisite layer — this is often the largest phase.
3. **Try the change naively.** Apply it, run the test suite, observe what breaks.
4. **Record prerequisites.** For each failure, add a node to the graph. Prerequisites may have sub-prerequisites — the graph grows downward.
5. **Revert.** Return to the last green state. Do not fix things in-flight.
6. **Work a leaf.** Pick a node whose deps are all `done`. Implement it, verify green, commit. If it unexpectedly breaks something, revert and record the new prerequisites.
7. **Repeat** until only the root goal remains, then apply it.

## The Mikado Graph

Maintain as a YAML file (`mikado.yaml`) in the repository root. A node is a **leaf** when all its deps are `done`.

```yaml
goal: Extract PaymentProcessor into its own module

nodes:
  goal:
    desc: Extract PaymentProcessor into its own module
    deps: [move-validator, fix-circular-import]
    status: pending

  move-validator:
    desc: Move PaymentValidator to shared/validation
    deps: [validator-unit-tests]
    status: pending

  validator-unit-tests:
    desc: Add unit tests for PaymentValidator
    deps: []
    status: done
    detail:
      files: [billing/payment_validator.py, tests/test_payment_validator.py]
      change: Add tests for validate_amount, validate_currency, and validate_card_token.
      verify: pytest tests/test_payment_validator.py
      context: |
        validate_card_token calls Stripe in prod but uses a stub in test
        (see conftest.py:stripe_mock fixture).

  fix-circular-import:
    desc: Remove circular import between billing and orders
    deps: [extract-shared-types]
    status: pending

  extract-shared-types:
    desc: Extract shared types to billing/types
    deps: []
    status: in-progress
    detail:
      files: [billing/models.py, billing/types.py, billing/__init__.py]
      change: Move OrderRef, PaymentStatus, Currency into billing/types.py.
      verify: pytest tests/billing/
```

### Node fields

| Field | Required | Description |
|-------|----------|-------------|
| `desc` | yes | What this node accomplishes. |
| `deps` | yes | Node IDs that must be `done` first. `[]` for none. |
| `status` | yes | `pending`, `in-progress`, or `done`. |
| `detail` | no | Populate when the node becomes a leaf. |
| `detail.files` | no | Files to create, modify, or move. |
| `detail.change` | no | What specifically to do. |
| `detail.verify` | no | Command to confirm green. |
| `detail.context` | no | Free-form notes — gotchas, failed approaches, code pointers. |

### Graph rules

- **Leaf** = all deps are `done`. Only leaves are workable.
- **After a failed naive attempt:** revert, add new prerequisite nodes, wire their IDs into deps.
- **After a successful commit:** mark the node `done`. Don't remove it — other nodes reference it.
- Multiple nodes can share a dependency (DAG, not tree).
- Populate `detail` when a node becomes a leaf. Leave it off blocked nodes — their context may shift.
- Update `mikado.yaml` after every revert or commit. It is the source of truth.

## Agent Protocol

1. **Assess test coverage first.** If the affected paths aren't tested, add test nodes before anything else.
2. **Always revert on failure.** No "just one more fix."
3. **Commit at every green state.** Small, independently reviewable commits.
4. **Update the graph** after every revert or commit.
5. **Work one leaf at a time.** No parallel changes that might interact.
6. **Name commits after graph nodes.**

## When to Use

- A change cascades into many breakages across the codebase.
- Poor test coverage needs to be retrofitted before restructuring.
- The refactoring is large enough to need incremental, reviewable progress.

Skip this for small self-contained changes or new code.
