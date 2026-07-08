const fs = require('fs');
const path = require('path');

describe('translation root text uid visibility', () => {
    test('does not hide the source uid when the row is not editable', () => {
        const html = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');
        const match = html.match(/<span class="project-container__content-body__text-uid"[\s\S]*?<\/span>/);

        expect(match).not.toBeNull();
        expect(match[0]).not.toContain('!translation.canEdit');
        expect(match[0]).toContain('!translation.isSource');
    });

    test('only renders split and merge action component for active admins on source cells', () => {
        const html = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');
        const match = html.match(/<template x-if="isAdmin && isActive && translation\.isSource">[\s\S]*?<sc-bilara-translation-project-actions><\/sc-bilara-translation-project-actions>[\s\S]*?<\/template>/);

        expect(match).not.toBeNull();
    });
});
