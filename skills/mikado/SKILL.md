---
description: Refactor incrementally with the Mikado Method — try, record prerequisites, revert, work leaves. Use for cascading breakages, test coverage retrofits before restructuring, or refactorings too large for one PR.
---

# Mikado Method

Never push through cascading failures. Skip this workflow for small self-contained changes or new code.

## Loop

1. State one concrete refactoring goal as the graph's root.
2. **Assess coverage first.** Verify affected paths are tested; add test-writing prerequisites before restructuring where coverage is inadequate.
3. Try the change naively and run tests. On failure, record prerequisites, **revert to green**, and wire new nodes into the graph. Never fix cascading failures in-flight. Revert only your attempted edits; preserve pre-existing work.
4. Work one **leaf** (all deps `done`) at a time. Implement, verify green, and make a small, independently reviewable commit named after the node. Unexpected failures repeat step 3; prerequisites can have prerequisites.
5. Update the graph after every revert or commit. Repeat bottom-up, applying the root goal last.

## Graph: `mikado.yaml`

Keep this source of truth in the repository root:

```yaml
goal: Extract PaymentProcessor
nodes:
  goal:
    desc: Extract PaymentProcessor
    deps: [cover-payments]
    status: pending
  cover-payments:
    desc: Test payment behavior before extraction
    deps: []
    status: in-progress
    detail:
      files: [billing/payments.py, tests/test_payments.py]
      change: Cover validation and charge behavior
      verify: pytest tests/test_payments.py
      context: Use the existing Stripe stub in conftest.py
```

- Required per node: `desc`, `deps` (node IDs; `[]` for none), `status` (`pending`, `in-progress`, `done`). Shared dependencies are allowed: a DAG, not necessarily a tree.
- Optional `detail`: `files` to create/modify/move, `change`, `verify` command, `context` (gotchas, failed approaches, code pointers). Populate when a node becomes a leaf, not while blocked.
- Only leaves are workable. Mark the selected leaf `in-progress`; after failure, add prerequisites and return it to `pending`; after a successful commit, mark it `done`. Retain completed nodes because others reference them.

## Subagents: Save Context

Prefer a fresh subagent per substantial leaf, including test-writing leaves. Keep tiny tasks local when delegation costs more than it saves. Without a subagent tool, **check for tmux and an installed, authenticated agent CLI**: a separate agent process provides fresh context. Work directly only if neither route is usable.

- **Coordinator:** owns the graph, selects and prepares leaves, reviews diffs and verification evidence, commits green results, and updates status. Persist essential findings in the graph.
- **Brief:** provide repository path, node ID, scope, relevant files/dependency outcomes, verification command, and necessary context—not the full conversation. Explicitly require coverage assessment, leaf-only work, and reverting on failure. Workers must not delegate further, edit the graph, or commit.
- **Worker:** implements/tests only its leaf. On failure, reverts only its own edits and reports prerequisites instead of expanding scope.
- **Handoff:** concise outcome (success or reverted), change summary, changed paths, test commands/results, prerequisites, and gotchas. Read detailed logs only when review requires them.
- **Sequential execution:** finish and review one leaf before dispatching the next. Context isolation does not imply parallelism; never run interacting changes concurrently.

### tmux Fallback

1. Read the tmux skill if available and the agent CLI's help/docs for fresh-session and prompt-input options. Do not assume CLI syntax or resume the coordinator's conversation.
2. Store each leaf's brief and handoff file outside tracked project files. Create one dedicated tmux session/pane on a dedicated socket and reuse it sequentially. For each leaf, launch a new agent process with a fresh conversation in the intended repository, using only its brief; reusing the pane must not resume prior agent context. Preserve permission/trust boundaries; no permission-bypass flags. Give the user a concrete attach/capture command.
3. Keep one worker active; do not edit its worktree while it runs. Poll with bounded pane captures or a leaf-specific completion marker, not full logs; ignore stale output from previous workers.
4. Review the handoff, diff, and verification evidence before committing/updating the graph. Process exit or a completion marker is not proof of success. If the worker fails/disappears, inspect partial changes and recover only its edits—never blindly reset the worktree.
5. Collect the result, preserve essential findings in the graph, and ensure the worker process has exited before launching the next fresh worker in the same pane. Keep the pane alive between leaves; close only the workflow-owned tmux session when the workflow ends.
