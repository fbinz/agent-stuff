# Annotate

Annotate Pi's last answer in your existing external editor. Add inline questions, clarifications, corrections, or direct edits in any format. Save and quit to send a unified diff to Pi automatically:

```text
I've annotated your last answer with inline questions, clarifications, and edits. Here is the diff:
--- original-answer.md
+++ annotated-answer.md
...

Treat the changes as feedback on your answer, not as a patch to apply. Answer any questions, address clarifications and corrections, and revise your answer where appropriate. Do not implement anything unless I explicitly ask you to.
```

## Load

From this repository:

```sh
pi -e ./extensions/annotate/index.ts
```

For persistent installation:

```sh
pi install ./extensions/annotate/index.ts
```

Alternatively, add the absolute path to `extensions/annotate/index.ts` to the `extensions` array in `~/.pi/agent/settings.json`, or copy the `annotate` directory to `~/.pi/agent/extensions/`.

## Use

1. Wait for Pi to finish an answer (not necessarily a plan).
2. Run `/annotate` (or its alias `/an`).
3. Edit the answer directly, delete passages, or add inline comments in any format you prefer.
4. Save and exit your editor. Pi receives the diff and responds to your feedback.

The entire latest completed assistant response is used; no special heading or format is required. Only text is included, not thinking blocks or tool calls. This sends a new user message; it does not rewrite the original answer in the conversation history.

Uses Pi's configured `externalEditor`, then `$VISUAL`, `$EDITOR`, or Pi's default. GUI editors must wait for the buffer to close (for example, configure `code --wait`). Closing the external editor submits immediately; there is no extra Pi confirmation dialog.

Unchanged text sends nothing. Quit without saving to discard unsaved edits. If you already saved changes, quitting will submit them; use a nonzero editor exit (e.g. Vim's `:cq`) to prevent submission. Failed edits/diffs leave the temporary files in place and report their location. Successful and unchanged annotations remove them.

Requires interactive Pi on Linux/macOS, plus `diff` on PATH. No additional npm dependencies. Annotations request answers and revisions, not implicit approval to implement; the command does not enforce read-only tool permissions.

## Tests

From the repository root, with Node.js 24+:

```sh
node --test tests/annotate.test.ts
```
