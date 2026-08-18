const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8');
const translationHtmlContent = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');

eval(translationJsContent);

describe('whole-file Bilara HTML validation', () => {
    beforeEach(() => {
        global.requestWithTokenRetry = jest.fn();
        global.hideBadge = jest.fn();
        global.displayBadge = jest.fn();
        global.BadgeStatus = { PENDING: 'pending', COMMITTED: 'committed', ERROR: 'error' };
        document.body.innerHTML = '<sl-dialog class="dialog-html-validation"></sl-dialog>';
    });

    test('validates the server file with only the current unsaved HTML drafts', async () => {
        requestWithTokenRetry.mockResolvedValue({
            ok: true,
            json: async () => ({
                valid: false,
                checked_segments: 2,
                errors: [{ code: 'unclosed-tag', uid: 'mn1:1.2', offset: 0, message: 'Unclosed <p> tag' }],
                warnings: [],
            }),
        });
        const context = fetchTranslation();
        context.prefix = 'mn1';
        context.htmlProjectName = 'html-pli-ms';
        context.htmlDraftOverrides = { 'mn1:1.2': '<p>{}' };

        await context.validateHtmlProject();

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            'projects/html-pli-ms/mn1/html-validation/',
            expect.objectContaining({
                method: 'POST',
                body: JSON.stringify({ overrides: { 'mn1:1.2': '<p>{}' } }),
            }),
        );
        expect(context.htmlValidation.status).toBe('invalid');
        expect(context.htmlValidation.errors[0].uid).toBe('mn1:1.2');
    });

    test('exposes an accessible validation action and result dialog on the HTML column', () => {
        expect(translationHtmlContent).toContain('class="translation-grid__html-validation-button"');
        expect(translationHtmlContent).toContain('Validate whole HTML file');
        expect(translationHtmlContent).toContain('class="dialog-html-validation"');
        expect(translationHtmlContent).toContain('focusHtmlValidationIssue(issue)');
    });

    test('editing an HTML segment records a draft and invalidates the previous result', () => {
        const context = fetchTranslation();
        const htmlProject = {
            muid: 'html-pli-ms',
            data: { 'mn1:1.1': '<p>{}</p>' },
        };
        context.htmlValidation.status = 'valid';

        context.setValue(htmlProject, 'mn1:1.1', '<blockquote>{}</blockquote>');

        expect(context.htmlDraftOverrides).toEqual({
            'mn1:1.1': '<blockquote>{}</blockquote>',
        });
        expect(context.htmlValidation.status).toBe('idle');
    });

    test('an issue opens HTML source and focuses its segment at the reported offset', () => {
        const textarea = document.createElement('textarea');
        textarea.id = 'translation-textarea-html-pli-ms-mn1:1.2';
        textarea.value = 'abcdef';
        document.body.appendChild(textarea);
        textarea.scrollIntoView = jest.fn();
        jest.spyOn(window, 'requestAnimationFrame').mockImplementation(callback => callback());
        const dispatchEvent = jest.spyOn(window, 'dispatchEvent');
        const context = fetchTranslation();
        context.htmlProjectName = 'html-pli-ms';

        context.focusHtmlValidationIssue({ uid: 'mn1:1.2', offset: 3 });

        expect(dispatchEvent).toHaveBeenCalledWith(expect.objectContaining({ type: 'show-html-source' }));
        expect(document.activeElement).toBe(textarea);
        expect(textarea.selectionStart).toBe(3);
    });

    test('a successfully saved HTML segment is removed from draft overrides', async () => {
        requestWithTokenRetry.mockResolvedValue({
            ok: true,
            json: async () => ({ task_id: null }),
        });
        const context = fetchTranslation();
        context.prefix = 'mn1';
        context.htmlDraftOverrides = { 'mn1:1.1': '<p>{}</p>' };

        await context.updateHandler(
            'html-pli-ms',
            { 'mn1:1.1': '<p>{}</p>' },
            null,
        );

        expect(context.htmlDraftOverrides).toEqual({});
    });
});
