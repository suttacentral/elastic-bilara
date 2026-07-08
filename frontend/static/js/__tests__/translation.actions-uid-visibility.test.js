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

    test('only renders split and merge action component for active admins on source cells when structure editing is enabled', () => {
        const html = fs.readFileSync(path.resolve(__dirname, '../../../translation.html'), 'utf8');
        const match = html.match(/<template x-if="isAdmin && isActive && translation\.isSource && structureEditingEnabled">[\s\S]*?<sc-bilara-translation-project-actions><\/sc-bilara-translation-project-actions>[\s\S]*?<\/template>/);

        expect(match).not.toBeNull();
    });

    test('does not require source canEdit permission for split and merge confirmation buttons', () => {
        const actionsJs = fs.readFileSync(path.resolve(__dirname, '../elements/translation/sc-bilara-translation-project-actions.js'), 'utf8');
        const splitMatch = actionsJs.match(/class="project-header__nav-button btn--split btn--confirm-split-merge"[\s\S]*?x-show="([^"]+)"/);
        const mergeMatch = actionsJs.match(/class="project-header__nav-button btn--merge btn--confirm-split-merge"[\s\S]*?x-show="([^"]+)"/);

        expect(splitMatch).not.toBeNull();
        expect(mergeMatch).not.toBeNull();
        expect(splitMatch[1]).toContain('isAdmin');
        expect(mergeMatch[1]).toContain('isAdmin');
        expect(splitMatch[1]).not.toContain('translation.canEdit');
        expect(mergeMatch[1]).not.toContain('translation.canEdit');
    });

    test('stores structure editing in the settings dialog for active admins', () => {
        const settingsDialogJs = fs.readFileSync(path.resolve(__dirname, '../elements/addons/sc-bilara-settings-dialog.js'), 'utf8');

        expect(settingsDialogJs).toContain("this._structureEditingPreferenceKey = 'bilara:translation:structure-editing-enabled'");
        expect(settingsDialogJs).toContain('this._canUseStructureEditing = !!userInfo.isActive');
        expect(settingsDialogJs).toContain('Structure Editing');
        expect(settingsDialogJs).toContain('this._canUseStructureEditing');
        expect(settingsDialogJs).toContain('structure_editing_enabled');
    });
});
