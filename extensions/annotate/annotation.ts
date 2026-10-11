import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

/** Ignore editor-added BOM, CRLF, and a single missing final newline. */
export function normalizeAnswer(text: string): string {
	const normalized = text.replace(/^\uFEFF/, "").replace(/\r\n/g, "\n");
	return normalized && !normalized.endsWith("\n") ? `${normalized}\n` : normalized;
}

export function formatAnnotation(diff: string): string {
	return `I've annotated your last answer with inline questions, clarifications, and edits. Here is the diff:\n${diff.trimEnd()}\n\nTreat the changes as feedback on your answer, not as a patch to apply. Answer any questions, address clarifications and corrections, and revise your answer where appropriate. Do not implement anything unless I explicitly ask you to.`;
}

/** diff exits 1 for differences, not failure. Never submit truncated output. */
export async function createAnswerDiff(originalPath: string, annotatedPath: string): Promise<string> {
	try {
		const result = await execFileAsync("diff", [
			"-u", "-L", "original-answer.md", "-L", "annotated-answer.md", originalPath, annotatedPath,
		], { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 });
		return result.stdout;
	} catch (error) {
		const result = error as { code?: number | string; stdout?: string; stderr?: string };
		if (result.code === 1 && result.stdout) return result.stdout;
		throw error;
	}
}

/** Only the trusted editor setting is shell syntax; the filename is a positional argument. */
export function runEditor(command: string, filePath: string, cwd: string): Promise<number | null> {
	return new Promise((resolve, reject) => {
		const child = spawn(process.env.SHELL || "/bin/sh", [
			"-c", `${command} "$1"`, "pi-annotate", filePath,
		], { stdio: "inherit", cwd });
		child.once("error", reject);
		child.once("close", resolve);
	});
}
