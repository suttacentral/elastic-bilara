const fs = require('fs');
const path = require('path');

const translationCss = fs.readFileSync(
    path.join(__dirname, '../../css/pages/translation.css'),
    'utf8'
);

describe('translation focus and hover affordances', () => {
    test('editable segment cells have a clear focus-within treatment', () => {
        expect(translationCss).toContain('.translation-cell--editable:focus-within {');
        expect(translationCss).toContain('box-shadow: inset 0 0 0 2px var(--color-primary)');
    });

    test('focused textarea has a visible focused surface', () => {
        expect(translationCss).toContain('.translation-cell__textarea:focus {');
        expect(translationCss).toContain('background-color: color-mix(in srgb, var(--color-primary) 7%, var(--color-background))');
    });
});
