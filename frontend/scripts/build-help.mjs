import {existsSync, readdirSync, readFileSync, mkdirSync, rmSync, copyFileSync, writeFileSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

export function buildHelp(frontendRoot, sourceRoot) {
    const source = sourceRoot || [path.resolve(frontendRoot, '../docs'), path.join(frontendRoot, '.help-docs')]
        .find(candidate => existsSync(path.join(candidate, 'README.md')));
    if (!source || !existsSync(path.join(source, 'README.md'))) {
        throw new Error('Help documentation is missing. Build from the repository checkout, or stage docs/ as frontend/.help-docs before submitting the frontend build.');
    }
    const files = [];
    function visit(directory, prefix = '') {
        for (const item of readdirSync(directory, {withFileTypes: true}).sort((a, b) => a.name.localeCompare(b.name))) {
            if (item.name.startsWith('.')) continue;
            const relative = prefix + item.name;
            if (item.isDirectory()) visit(path.join(directory, item.name), relative + '/');
            else if (item.isFile()) files.push(relative);
        }
    }
    visit(source);
    const output = path.join(frontendRoot, 'public/help-content');
    rmSync(output, {recursive: true, force: true});
    mkdirSync(output, {recursive: true});
    for (const relative of files) {
        const destination = path.join(output, relative);
        mkdirSync(path.dirname(destination), {recursive: true});
        copyFileSync(path.join(source, relative), destination);
    }
    const articles = files.filter(file => /\.md$/i.test(file)).map(file => {
        const markdown = readFileSync(path.join(source, file), 'utf8');
        return {path: file, title: markdown.match(/^#\s+(.+)$/m)?.[1]?.replace(/[*`]/g, '').trim()
            || path.basename(file, '.md').replace(/-/g, ' '), markdown};
    });
    writeFileSync(path.join(output, 'index.json'), JSON.stringify({version: 1, articles, files}) + '\n');
    return {articles, files};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
    const result = buildHelp(frontendRoot);
    console.log(`Built Agoge help: ${result.articles.length} Markdown pages.`);
}
