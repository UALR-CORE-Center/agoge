export type HelpArticle = {path: string; title: string; markdown: string};
export type HelpManifest = {version: number; articles: HelpArticle[]; files: string[]};

export const helpArticleRoute = (path: string): string =>
    '/help' + (path === 'README.md' ? '' : '/' + path.replace(/\.md$/i, ''));

export const helpStaticUrl = (path: string, base = import.meta.env.BASE_URL): string =>
    `${base.replace(/\/$/, '')}/help-content/${path.split('/').map(encodeURIComponent).join('/')}`;

export function resolveHelpLink(href: string, article: HelpArticle, manifest: HelpManifest,
                                base = import.meta.env.BASE_URL, image = false): {href: string; internal: boolean} {
    if (!href || href.startsWith('#')) return {href: href || '#', internal: false};
    const target = new URL(href, `https://agoge-help.invalid/docs/${article.path}`);
    if (target.origin !== 'https://agoge-help.invalid') return {href, internal: false};
    const suffix = target.search + target.hash;
    const documentPath = decodeURIComponent(target.pathname.replace(/^\/docs\//, ''));
    if (target.pathname.startsWith('/docs/')) {
        const page = manifest.articles.find(item => item.path === documentPath
            || item.path === `${documentPath}.md` || item.path === `${documentPath.replace(/\/$/, '')}/README.md`);
        if (page && !image) return {href: helpArticleRoute(page.path) + suffix, internal: true};
        if (manifest.files.includes(documentPath)) return {href: helpStaticUrl(documentPath, base) + suffix, internal: false};
    }
    // Links outside docs/ (source code, contribution guides) remain available in
    // the repository rather than becoming nonexistent application routes.
    const repositoryPath = target.pathname.replace(/^\//, '');
    return {href: `https://github.com/UALR-CORE-Center/agoge/blob/main/${repositoryPath}${suffix}`, internal: false};
}

export function headingId(text: string): string {
    return text.toLowerCase().trim().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s/g, '-');
}
