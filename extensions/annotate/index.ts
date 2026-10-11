import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { SettingsManager, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { createAnswerDiff, formatAnnotation, normalizeAnswer, runEditor } from "./annotation.ts";

export default function annotate(pi: ExtensionAPI): void {
	let annotating = false;

	const command: Parameters<ExtensionAPI["registerCommand"]>[1] = {
		description: "Annotate the last assistant answer in your external editor and submit inline feedback",
		handler: async (_args, ctx) => {
			if (ctx.mode !== "tui" || process.platform === "win32") {
				ctx.ui.notify("Annotate requires interactive Pi on Linux/macOS.", "error");
				return;
			}
			if (annotating || !ctx.isIdle()) {
				ctx.ui.notify("Wait until Pi is idle before annotating an answer.", "warning");
				return;
			}

			const branch = ctx.sessionManager.getBranch();
			const entry = [...branch].reverse().find((entry) =>
				entry.type === "message" && entry.message.role === "assistant",
			);
			if (!entry || entry.type !== "message" || entry.message.role !== "assistant") {
				ctx.ui.notify("No assistant answer to annotate yet.", "info");
				return;
			}
			const message = entry.message;
			if (message.stopReason !== "stop") {
				ctx.ui.notify("The latest assistant response is incomplete. Wait for a complete answer first.", "warning");
				return;
			}
			const original = normalizeAnswer(message.content
				.filter((part) => part.type === "text")
				.map((part) => part.text).join("\n"));
			if (!original.trim()) {
				ctx.ui.notify("The latest assistant response has no text to annotate.", "info");
				return;
			}

			annotating = true;
			let directory: string | undefined;
			let keepFiles = false;
			const leafId = ctx.sessionManager.getLeafId();
			try {
				const editor = SettingsManager.create(ctx.cwd).getExternalEditorCommand();
				directory = await mkdtemp(join(tmpdir(), "pi-annotate-"));
				const originalPath = join(directory, "original-answer.md");
				const annotatedPath = join(directory, "annotated-answer.md");
				await writeFile(originalPath, original);
				await writeFile(annotatedPath, original);

				const exitCode = await ctx.ui.custom<number | null>((tui, _theme, _kb, done) => {
					tui.stop();
					process.stdout.write("Annotate the answer with questions, clarifications, or edits, then save and quit to submit. Quit without saving to cancel.\n");
					void runEditor(editor, annotatedPath, ctx.cwd).catch(() => null).then((code) => {
						tui.start();
						tui.requestRender(true);
						done(code);
					});
					return { render: () => [], invalidate: () => {} };
				});
				if (exitCode !== 0) {
					throw new Error(`Editor exited unsuccessfully (${exitCode ?? "could not launch"}); no annotations submitted.`);
				}

				const annotated = normalizeAnswer(await readFile(annotatedPath, "utf8"));
				if (annotated === original) {
					ctx.ui.notify("Answer unchanged; no annotations submitted.", "info");
					return;
				}
				await writeFile(annotatedPath, annotated);
				const diff = await createAnswerDiff(originalPath, annotatedPath);
				if (ctx.sessionManager.getLeafId() !== leafId || !ctx.isIdle()) {
					throw new Error("The conversation changed during annotation; no annotations submitted.");
				}
				pi.sendUserMessage(formatAnnotation(diff));
			} catch (error) {
				keepFiles = true;
				ctx.ui.notify(`${error instanceof Error ? error.message : String(error)}${directory ? `\nAnnotation files kept at ${directory}` : ""}`, "error");
			} finally {
				annotating = false;
				if (directory && !keepFiles) {
					await rm(directory, { recursive: true, force: true }).catch(() => {});
				}
			}
		},
	};

	for (const name of ["annotate", "an"]) {
		pi.registerCommand(name, command);
	}
}
