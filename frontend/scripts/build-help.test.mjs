import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, writeFileSync, readFileSync, existsSync, rmSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {buildHelp} from './build-help.mjs';

test('builds current Markdown and preserves relative assets/downloads for a frontend-only context', () => {
    const root = mkdtempSync(path.join(os.tmpdir(), 'agoge-help-'));
    try {
        const frontend = path.join(root, 'frontend');
        const docs = path.join(frontend, '.help-docs');
        mkdirSync(path.join(docs, 'guides'), {recursive: true});
        mkdirSync(path.join(docs, 'assets'), {recursive: true});
        writeFileSync(path.join(docs, 'README.md'), '# Help\n[Guide](guides/start.md)');
        writeFileSync(path.join(docs, 'guides/start.md'), '# Start here\nExample.');
        writeFileSync(path.join(docs, 'example.json'), '{"public":true}');
        writeFileSync(path.join(docs, 'assets/picture.png'), Buffer.from([1, 2, 3]));
        writeFileSync(path.join(docs, '.private.md'), '# Excluded');
        let result = buildHelp(frontend);
        assert.equal(result.articles.length, 2);
        assert.equal(result.articles.find(page => page.path === 'guides/start.md').title, 'Start here');
        assert.deepEqual(readFileSync(path.join(frontend, 'public/help-content/assets/picture.png')), Buffer.from([1, 2, 3]));
        assert.equal(existsSync(path.join(frontend, 'public/help-content/example.json')), true);
        assert.equal(existsSync(path.join(frontend, 'public/help-content/.private.md')), false);
        writeFileSync(path.join(docs, 'guides/start.md'), '# Updated guide\nCurrent source.');
        result = buildHelp(frontend);
        assert.equal(result.articles.find(page => page.path === 'guides/start.md').title, 'Updated guide');
        const manifest = JSON.parse(readFileSync(path.join(frontend, 'public/help-content/index.json')));
        assert.equal(manifest.articles.length, 2);
        assert.ok(manifest.files.includes('example.json'));
    } finally { rmSync(root, {recursive: true, force: true}); }
});

test('missing documentation fails the build instead of shipping an empty help app', () => {
    const root = mkdtempSync(path.join(os.tmpdir(), 'agoge-help-'));
    try { assert.throws(() => buildHelp(root), /documentation is missing/); }
    finally { rmSync(root, {recursive: true, force: true}); }
});
