import React, {useEffect, useMemo, useState} from 'react';
import {Alert, Box, CircularProgress, Divider, Link, List, ListItemButton, ListItemText,
    Paper, TextField, Typography} from '@mui/material';
import {Link as RouterLink, useLocation} from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {headingId, HelpArticle, HelpManifest, helpArticleRoute, helpStaticUrl, resolveHelpLink} from './helpDocuments';

const textContent = (children: React.ReactNode): string => React.Children.toArray(children).map(child =>
    typeof child === 'string' || typeof child === 'number' ? String(child)
        : React.isValidElement<{children?: React.ReactNode}>(child) ? textContent(child.props.children) : '').join('');

export const HelpApp: React.FC = () => {
    const location = useLocation();
    const [manifest, setManifest] = useState<HelpManifest | null>(null);
    const [error, setError] = useState(false);
    const [query, setQuery] = useState('');
    useEffect(() => {
        const abort = new AbortController();
        fetch(helpStaticUrl('index.json'), {signal: abort.signal}).then(response => {
            if (!response.ok) throw new Error('Help content unavailable');
            return response.json();
        }).then(data => {
            if (!Array.isArray(data.articles) || !Array.isArray(data.files)) throw new Error('Invalid help content');
            setManifest(data);
        }).catch(() => { if (!abort.signal.aborted) setError(true); });
        return () => abort.abort();
    }, []);
    const pagePath = location.pathname.replace(/^\/help\/?/, '').replace(/\/$/, '');
    const article = manifest?.articles.find(page => helpArticleRoute(page.path) === (pagePath ? `/help/${pagePath}` : '/help'));
    const pages = useMemo(() => {
        const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
        return manifest?.articles.filter(page => terms.every(term => `${page.title} ${page.markdown}`.toLowerCase().includes(term))) || [];
    }, [manifest, query]);
    useEffect(() => {
        if (!article) return;
        document.title = `${article.title} | Agoge Help`;
        if (location.hash) requestAnimationFrame(() => document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView?.());
    }, [article, location.hash]);

    if (error) return <Alert severity="error">Help documentation could not be loaded. Reload this page or contact the project administrator.</Alert>;
    if (!manifest) return <Box sx={{p: 4}}><CircularProgress aria-label="Loading help documentation" /></Box>;
    const markdown = (page: HelpArticle) => {
        const counts = new Map<string, number>();
        const heading = (tag: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6') => ({children}: {children?: React.ReactNode}) => {
            const slug = headingId(textContent(children));
            const number = counts.get(slug) || 0;
            counts.set(slug, number + 1);
            return React.createElement(tag, {id: slug + (number ? `-${number}` : '')}, children);
        };
        return <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{
            h1: heading('h1'), h2: heading('h2'), h3: heading('h3'), h4: heading('h4'), h5: heading('h5'), h6: heading('h6'),
            a: ({href = '', children}) => {
                const target = resolveHelpLink(href, page, manifest);
                return target.internal ? <Link component={RouterLink} to={target.href}>{children}</Link>
                    : <Link href={target.href} rel="noopener noreferrer">{children}</Link>;
            },
            img: ({src = '', alt}) => <Box component="img" src={resolveHelpLink(src, page, manifest, import.meta.env.BASE_URL, true).href}
                alt={alt || ''} sx={{maxWidth: '100%', height: 'auto'}} />,
            table: ({children}) => <Box sx={{overflowX: 'auto'}}><table>{children}</table></Box>,
        }}>{page.markdown}</ReactMarkdown>;
    };
    return <Box sx={{width: '100%', maxWidth: 1440, pb: 4}}>
        <Typography variant="h4" component="h1" gutterBottom>Agoge Help</Typography>
        <Typography color="text.secondary" sx={{mb: 3}}>Guides, setup instructions, and troubleshooting.</Typography>
        <Box sx={{display: 'grid', gridTemplateColumns: {xs: '1fr', md: 'minmax(230px, 290px) minmax(0, 1fr)'}, gap: 3, alignItems: 'start'}}>
            <Paper component="aside" variant="outlined" sx={{p: 2, position: {md: 'sticky'}, top: {md: 80}}}>
                <TextField fullWidth size="small" label="Search documentation" value={query} onChange={event => setQuery(event.target.value)} />
                <List component="nav" aria-label="Help articles" sx={{maxHeight: {xs: 240, md: '70vh'}, overflow: 'auto', mt: 1}}>
                    {pages.map(page => <ListItemButton key={page.path} component={RouterLink} to={helpArticleRoute(page.path)}
                        selected={article?.path === page.path}>
                        <ListItemText primary={page.title} secondary={page.path.split('/')[0] === 'README.md' ? 'Overview' : page.path.split('/')[0]} />
                    </ListItemButton>)}
                </List>
                {!pages.length && <Typography sx={{mt: 2}}>No matching articles.</Typography>}
            </Paper>
            <Paper component="article" variant="outlined" sx={{p: {xs: 2, md: 4}, minWidth: 0, overflowWrap: 'anywhere',
                '& h1, & h2, & h3, & h4': {scrollMarginTop: 90}, '& h1': {fontSize: '2rem'},
                '& h2': {mt: 4}, '& pre': {p: 2, bgcolor: 'action.hover', borderRadius: 1, overflowX: 'auto'},
                '& code': {fontFamily: 'monospace'}, '& td, & th': {border: 1, borderColor: 'divider', p: 1},
                '& table': {borderCollapse: 'collapse', width: '100%'}, '& blockquote': {ml: 0, pl: 2, borderLeft: 3, borderColor: 'divider'}}}>
                {article ? <>{markdown(article)}<Divider sx={{mt: 4, mb: 2}} />
                    <Typography variant="caption" color="text.secondary">Built from docs/{article.path} with this application release.</Typography></>
                    : <Alert severity="info">That article was not found. Choose a guide from the documentation list.</Alert>}
            </Paper>
        </Box>
    </Box>;
};
