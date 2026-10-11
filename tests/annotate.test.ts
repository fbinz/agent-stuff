import assert from "node:assert/strict";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { createAnswerDiff, formatAnnotation, normalizeAnswer, runEditor } from "../extensions/annotate/annotation.ts";

async function withAnswers(original: string, annotated: string, fn: (a: string, b: string) => Promise<void>) {
	const directory = await mkdtemp(join(tmpdir(), "annotate-test-"));
	try {
		const a = join(directory, "original.md");
		const b = join(directory, "annotated.md");
		await writeFile(a, original);
		await writeFile(b, annotated);
		await fn(a, b);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
}

test("normalizes editor formatting without discarding meaningful whitespace", () => {
	assert.equal(normalizeAnswer("\uFEFFCache\r\n"), "Cache\n");
	assert.equal(normalizeAnswer("Cache"), "Cache\n");
	assert.equal(normalizeAnswer(""), "");
	assert.equal(normalizeAnswer("Cache\n\n"), "Cache\n\n");
	assert.equal(normalizeAnswer("  Cache  \n"), "  Cache  \n");
});

test("no diff for an unchanged answer", async () => {
	await withAnswers("Cache\n", "Cache\n", async (a, b) => {
		assert.equal(await createAnswerDiff(a, b), "");
	});
});

test("submits inline questions, clarifications, and edits as feedback on any answer", async () => {
	await withAnswers("A persistent cache is useful.\nRetry failures.\n", "An in-memory cache is useful.\n> Why? Only transient failures, please.\nRetry failures.\n", async (a, b) => {
		const diff = await createAnswerDiff(a, b);
		assert.equal(diff, "--- original-answer.md\n+++ annotated-answer.md\n@@ -1,2 +1,3 @@\n-A persistent cache is useful.\n+An in-memory cache is useful.\n+> Why? Only transient failures, please.\n Retry failures.\n");
		assert.equal(formatAnnotation(diff), `I've annotated your last answer with inline questions, clarifications, and edits. Here is the diff:\n${diff.trimEnd()}\n\nTreat the changes as feedback on your answer, not as a patch to apply. Answer any questions, address clarifications and corrections, and revise your answer where appropriate. Do not implement anything unless I explicitly ask you to.`);
		assert.ok(!diff.includes(tmpdir()));
	});
});

test("deletions, including deleting the entire answer, are represented", async () => {
	await withAnswers("Cache\n", "", async (a, b) => {
		assert.match(await createAnswerDiff(a, b), /@@ -1 \+0,0 @@\n-Cache/);
	});
});

test("diff failures do not produce annotations", async () => {
	await withAnswers("answer\n", "answer\n", async (a, b) => {
		await rm(b);
		await assert.rejects(createAnswerDiff(a, b));
	});
});

test("editor supports quoted arguments and safely passes filenames with shell characters", async () => {
	const directory = await mkdtemp(join(tmpdir(), "annotate-editor-"));
	try {
		const script = join(directory, "fake editor.mjs");
		const answer = join(directory, "answer ' $HOME; annotated.md");
		await writeFile(script, 'import { writeFileSync } from "node:fs"; writeFileSync(process.argv[2], "Annotated\\n");');
		const quote = (value: string) => `'${value.replaceAll("'", "'\\''")}'`;
		assert.equal(await runEditor(`${quote(process.execPath)} ${quote(script)}`, answer, directory), 0);
		assert.equal(await readFile(answer, "utf8"), "Annotated\n");
		assert.equal(await runEditor(`${quote(process.execPath)} -e 'process.exit(7)'`, answer, directory), 7);
	} finally {
		await rm(directory, { recursive: true, force: true });
	}
});
