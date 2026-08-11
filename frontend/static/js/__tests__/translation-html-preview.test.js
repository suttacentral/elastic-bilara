const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8');
const translationHtmlContent = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');
const translationCssContent = fs.readFileSync(
    path.resolve(__dirname, '../../css/pages/translation.css'),
    'utf8',
);
const projectHeaderContent = fs.readFileSync(
    path.resolve(__dirname, '../elements/translation/sc-bilara-translation-project-header.js'),
    'utf8',
);

window.DOMPurify = require('dompurify');
eval(translationJsContent);

describe('translation root HTML preview', () => {
    beforeEach(() => {
        jest.restoreAllMocks();
    });

    test('is disabled until the user enables it and persists that choice', () => {
        jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
        const setItem = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {});

        expect(getStoredHtmlPreviewEnabled()).toBe(false);

        setStoredHtmlPreviewEnabled(true);
        expect(setItem).toHaveBeenCalledWith(
            'bilara:translation:html-preview-enabled',
            'true',
        );
    });

    test('renders preview only for root projects when enabled', () => {
        expect(shouldRenderHtmlPreview('root-en-site', true)).toBe(true);
        expect(shouldRenderHtmlPreview('translation-de-site', true)).toBe(false);
        expect(shouldRenderHtmlPreview('root-en-site', false)).toBe(false);
    });

    test('places an accessible preview toggle beside root column titles without triggering column drag', () => {
        expect(projectHeaderContent).not.toContain('HTML Preview');
        expect(translationHtmlContent).toContain('class="translation-grid__html-preview-toggle"');
        expect(translationHtmlContent).toContain("x-show=\"translation.muid && translation.muid.startsWith('root-')\"");
        expect(translationHtmlContent).toContain(':aria-pressed="htmlPreviewEnabled"');
        expect(translationHtmlContent).toContain('@pointerdown.stop');
        expect(translationHtmlContent).toContain("draggable = false");
        expect(translationHtmlContent).toContain("draggable = true");
        expect(translationHtmlContent).toContain('@pointerup.window');
        expect(translationHtmlContent).toContain('@keydown.stop');
        expect(translationHtmlContent).toContain('class="translation-cell__html-preview"');
        expect(translationHtmlContent).toContain('shouldRenderHtmlPreview(translation.muid, htmlPreviewEnabled)');
    });

    test('keeps supported inline markup and removes executable HTML', () => {
        const sanitized = sanitizeBilaraHtml(
            '<a href="#item1" onclick="alert(1)">Background</a>' +
            '<cite>Source</cite><script>alert(1)</script>' +
            '<img src=x onerror="alert(1)"><a href="javascript:alert(1)">Bad link</a>',
        );

        expect(sanitized).toContain('<a href="#item1">Background</a>');
        expect(sanitized).toContain('<cite>Source</cite>');
        expect(sanitized).not.toContain('onclick');
        expect(sanitized).not.toContain('<script');
        expect(sanitized).not.toContain('<img');
        expect(sanitized).not.toContain('javascript:');
    });

    test('allows only web and fragment link protocols', () => {
        const sanitized = sanitizeBilaraHtml(
            '<a href="#item1">Fragment</a>' +
            '<a href="https://suttacentral.net">Web</a>' +
            '<a href="mailto:test@example.com">Email</a>' +
            '<a href="/admin">Relative</a>',
        );

        expect(sanitized).toContain('href="#item1"');
        expect(sanitized).toContain('href="https://suttacentral.net"');
        expect(sanitized).not.toContain('href="mailto:');
        expect(sanitized).not.toContain('href="/admin"');
    });

    test('preview text keeps the root cell typography and wrapping behavior', () => {
        expect(translationCssContent).toMatch(
            /\.translation-cell__html-preview\s*\{[^}]*white-space:\s*pre-wrap;[^}]*overflow-wrap:\s*break-word;/s,
        );
    });

    test('column toggle has visible active and keyboard-focus states', () => {
        expect(translationCssContent).toContain('.translation-grid__html-preview-toggle--active');
        expect(translationCssContent).toContain('.translation-grid__html-preview-toggle:focus-visible');
    });
});
