const fs = require('fs');
const path = require('path');

const translationJsContent = fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8');
eval(translationJsContent);

describe('Translation initial loading state', () => {
    test('starts in the loading state', () => {
        expect(fetchTranslation().loading).toBe(true);
    });

    test('clears loading after initialization succeeds', async () => {
        const context = fetchTranslation();
        context.initialize = jest.fn().mockResolvedValue();

        await context.init();

        expect(context.initialize).toHaveBeenCalledTimes(1);
        expect(context.loading).toBe(false);
    });

    test('clears loading after initialization fails', async () => {
        const context = fetchTranslation();
        const error = new Error('load failed');
        context.initialize = jest.fn().mockRejectedValue(error);

        await expect(context.init()).rejects.toThrow('load failed');
        expect(context.loading).toBe(false);
    });
});
