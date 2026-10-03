---
description: Structured approach to large refactorings using the Mikado Method — try, fail, record prerequisites, revert, work leaves. Use when a change cascades into many breakages, when test coverage needs retrofitting before restructuring, or when a refactoring is too large for a single big-bang PR.
---

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

## Subagents for Context Isolation

Prefer a fresh subagent for each substantial leaf task, including test-writing leaves. A dedicated subagent tool is not required: a separate agent CLI process in tmux also provides context isolation. Keep implementation details in the subagent's context and concise outcomes in the coordinator's context. Tiny tasks can stay with the coordinator when delegation overhead outweighs the benefit. Before concluding that subagents are unavailable, check for tmux and an installed, authenticated agent CLI; if neither delegation route is usable, follow the same loop directly.

- **Coordinator:** owns `mikado.yaml`, selects the next workable leaf, populates its `detail`, and marks it `in-progress`. Reviews the returned changes and verification evidence, commits the green result, then marks the node `done`.
- **Task brief:** give the subagent the node ID, scope, relevant files and dependency outcomes, verification command, and necessary context. Include the Mikado rules explicitly: assess coverage first, stay within this leaf, and revert on failure rather than fixing cascading breakages. Do not forward the entire conversation by default.
- **Subagent:** implements and tests only the assigned leaf. On failure, reverts only its own attempted changes, preserves pre-existing work, and reports newly discovered prerequisites instead of expanding scope. The coordinator records those prerequisites and returns the leaf to `pending`.
- **Handoff:** return a concise change summary, changed file paths, verification commands and results, and any prerequisites or gotchas. State whether the attempt succeeded or was reverted. Keep detailed logs out of the coordinator's context unless needed for review; persist essential context in the graph.
- **Sequential by default:** finish and review one leaf before dispatching the next. Subagents save context; they do not imply parallel changes. Never run changes that might interact concurrently.

### tmux Fallback

If no subagent tool is available, launch a fresh agent CLI session in tmux for the selected leaf. tmux only hosts the process; the separate agent session provides the fresh context.

1. Read the tmux skill if available, and check the installed agent CLI's documentation/help for fresh-session and prompt-input options. Do not resume the coordinator's session or assume a particular CLI syntax.
2. Write a bounded task brief and designate a handoff file outside tracked project files. Include the repository path, the leaf details, verification requirements, and the handoff format above. Tell the worker not to delegate further, edit the graph, or commit; those remain the coordinator's responsibility.
3. Use a dedicated tmux socket and a unique session name for the leaf. Start the agent in the intended repository with a fresh conversation and only the task brief. Preserve existing permission/trust boundaries; do not enable permission-bypass flags. Give the user a concrete attach or capture command to monitor it.
4. Keep one worker active at a time. While it works, do not edit the same worktree. Poll for completion using bounded pane captures or a completion marker, rather than repeatedly importing full logs into the coordinator's context.
5. Read the handoff, inspect the diff, and review verification evidence before committing or updating the graph. A stopped process or completion marker alone does not prove success. If the worker fails or disappears, inspect partial changes and recover only its edits; never blindly reset the worktree.
6. After collecting the result, close only the tmux session created for that worker. Retain any essential findings in `mikado.yaml` before dispatching a fresh worker for the next leaf.

## When to Use

- A change cascades into many breakages across the codebase.
- Poor test coverage needs to be retrofitted before restructuring.
- The refactoring is large enough to need incremental, reviewable progress.

Skip this for small self-contained changes or new code.
