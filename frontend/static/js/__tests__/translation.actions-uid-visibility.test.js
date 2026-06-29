const fs = require('fs');
const path = require('path');

describe('translation root text uid visibility', () => {
    test('does not hide the source uid when the row is not editable', () => {
        const html = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');
        const match = html.match(/<sc-bilara-translation-project-actions[\s\S]*?<\/sc-bilara-translation-project-actions>/);

        expect(match).not.toBeNull();
        expect(match[0]).not.toContain('!translation.canEdit');
    });
});
