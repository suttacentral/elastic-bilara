const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(
    path.resolve(__dirname, '../translation.js'),
    'utf8',
);
eval(translationJsContent);

describe('translation source URL resolution', () => {
    let context;
    let replaceState;

    beforeEach(() => {
        context = fetchTranslation();
        global.requestWithTokenRetry = jest.fn();
        replaceState = jest.spyOn(window.history, 'replaceState').mockImplementation();
    });

    afterEach(() => {
        replaceState.mockRestore();
    });

    test('uses an existing source without making another request', async () => {
        const params = new URLSearchParams(
            'prefix=mn1&muid=translation-en-tester&source=root-pli-ms',
        );

        await expect(context.resolveSource(params)).resolves.toBe('root-pli-ms');

        expect(requestWithTokenRetry).not.toHaveBeenCalled();
        expect(replaceState).not.toHaveBeenCalled();
    });

    test('resolves source from path and canonicalizes the translation URL', async () => {
        const filePath = (
            'translation/en/tester/sutta/mn/mn1/'
            + 'mn1_translation-en-tester.json'
        );
        const params = new URLSearchParams({
            prefix: 'mn1',
            muid: 'translation-en-tester',
            path: filePath,
        });
        requestWithTokenRetry.mockResolvedValue({
            ok: true,
            json: async () => ({ muid: 'root-pli-ms' }),
        });

        await expect(context.resolveSource(params)).resolves.toBe('root-pli-ms');

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            `projects/${filePath}/source/`,
        );
        expect(params.get('source')).toBe('root-pli-ms');
        expect(params.has('path')).toBe(false);
        const canonicalUrl = replaceState.mock.calls[0][2];
        expect(canonicalUrl.searchParams.get('source')).toBe('root-pli-ms');
        expect(canonicalUrl.searchParams.has('path')).toBe(false);
    });

    test('omits a duplicate muid when the selected file is itself the source', async () => {
        const params = new URLSearchParams({
            prefix: 'mn1',
            muid: 'root-pli-ms',
            path: 'root/pli/ms/sutta/mn/mn1/mn1_root-pli-ms.json',
        });
        requestWithTokenRetry.mockResolvedValue({
            ok: true,
            json: async () => ({ muid: 'root-pli-ms' }),
        });

        await context.resolveSource(params);

        expect(params.get('muid')).toBe('');
    });

    test('rejects a source-less URL that has no project path', async () => {
        const params = new URLSearchParams(
            'prefix=mn1&muid=translation-en-tester',
        );

        await expect(context.resolveSource(params)).rejects.toThrow(
            'Translation URL is missing both source and path',
        );
    });
});
