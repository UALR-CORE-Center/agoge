// @vitest-environment jsdom
import React from 'react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {MemoryRouter, Route, Routes} from 'react-router-dom';
import {HelpApp} from './HelpApp';
import {headingId, helpStaticUrl, resolveHelpLink} from './helpDocuments';

const guide = {path: 'guides/instructor-guide.md', title: 'Instructor guide', markdown: '# Instructor guide\n## Build a lab\nStart here.\n[Setup](../operations/setup.md#project)\n![Overview](../assets/overview.png)\n[Download](../examples/lab.json)\n[Source](../../README.md)\n\n```powershell\npython setup.py\n```\n\n<script>unsafe()</script>'};
const manifest = {version: 1, articles: [
    {path: 'README.md', title: 'Documentation home', markdown: '# Documentation home\n[Instructor guide](guides/instructor-guide.md)'},
    guide,
    {path: 'operations/setup.md', title: 'Project setup', markdown: '# Project setup\n## Project\nSecret Manager configuration.'},
], files: ['README.md', guide.path, 'operations/setup.md', 'assets/overview.png', 'examples/lab.json']};

beforeEach(() => vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok: true, json: async () => manifest})));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function show(path = '/test-dev/help') {
    return render(<MemoryRouter basename="/test-dev" initialEntries={[path]}><Routes>
        <Route path="/help/*" element={<HelpApp />} />
    </Routes></MemoryRouter>);
}

describe('public documentation application', () => {
    it('loads documentation without an authentication or API provider, searches full text, and navigates within a tenant', async () => {
        show();
        await screen.findByRole('heading', {name: 'Documentation home'});
        const instructor = screen.getAllByRole('link', {name: 'Instructor guide'})[0];
        expect(instructor.getAttribute('href')).toBe('/test-dev/help/guides/instructor-guide');
        fireEvent.click(instructor);
        await screen.findByRole('heading', {name: 'Build a lab'});
        expect(screen.getByRole('heading', {name: 'Build a lab'}).id).toBe('build-a-lab');
        expect(screen.getByText('python setup.py').closest('pre')).not.toBeNull();
        expect(document.querySelector('script')).toBeNull();
        fireEvent.change(screen.getByLabelText('Search documentation'), {target: {value: 'Secret Manager'}});
        expect(screen.queryByRole('link', {name: /Instructor guide.*guides/})).toBeNull();
        expect(screen.getByRole('link', {name: /Project setup/}).getAttribute('href')).toBe('/test-dev/help/operations/setup');
    });

    it('keeps Markdown links, images, downloads, and repository links usable', async () => {
        show('/test-dev/help/guides/instructor-guide');
        await screen.findByRole('heading', {name: 'Build a lab'});
        expect(screen.getByRole('link', {name: 'Setup'}).getAttribute('href')).toBe('/test-dev/help/operations/setup#project');
        expect(screen.getByRole('img', {name: 'Overview'}).getAttribute('src')).toBe('/help-content/assets/overview.png');
        expect(screen.getByRole('link', {name: 'Download'}).getAttribute('href')).toBe('/help-content/examples/lab.json');
        expect(screen.getByRole('link', {name: 'Source'}).getAttribute('href')).toBe('https://github.com/UALR-CORE-Center/agoge/blob/main/README.md');
        expect(resolveHelpLink('../assets/overview.png', guide, manifest, '/test-dev/', true).href)
            .toBe('/test-dev/help-content/assets/overview.png');
        expect(helpStaticUrl('index.json', '/test-dev/')).toBe('/test-dev/help-content/index.json');
        expect(headingId('Build a **new** lab!')).toBe('build-a-new-lab');
    });

    it('offers navigation for missing articles instead of a broken blank screen', async () => {
        show('/test-dev/help/missing');
        await screen.findByText(/That article was not found/);
        expect(screen.getByRole('link', {name: /Project setup/})).not.toBeNull();
    });

    it('reports missing build content clearly', async () => {
        vi.mocked(fetch).mockResolvedValue({ok: false} as Response);
        show();
        await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Help documentation could not be loaded'));
    });
});
