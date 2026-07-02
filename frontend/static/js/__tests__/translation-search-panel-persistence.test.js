const fs = require('fs');
const path = require('path');

const translationHtml = fs.readFileSync(
    path.join(__dirname, '../../../translation.html'),
    'utf8'
);

const projectHeaderJs = fs.readFileSync(
    path.join(__dirname, '../elements/translation/sc-bilara-translation-project-header.js'),
    'utf8'
);

describe('translation search panel persistence', () => {
    test('translation page stores explicit search panel toggles', () => {
        expect(translationHtml).toContain("searchPanelPreferenceKey: 'bilara:translation:search-panel-visible'");
        expect(translationHtml).toContain('getStoredSearchPanelVisible()');
        expect(translationHtml).toContain('localStorage.getItem(this.searchPanelPreferenceKey)');
        expect(translationHtml).toContain("stored === null ? window.innerWidth >= 1280 : stored === 'true'");
        expect(translationHtml).toContain('toggleSearchPanel() {');
        expect(translationHtml).toContain('localStorage.setItem(this.searchPanelPreferenceKey, String(this.searchPanelVisible));');
    });

    test('temporary search panel opens do not overwrite the saved preference', () => {
        expect(translationHtml).toContain('showSearchPanelTemporarily() {');
        expect(translationHtml).toContain('@show-search-panel.window="showSearchPanelTemporarily()"');
        expect(translationHtml).toContain('@resize.window="if(localStorage.getItem(searchPanelPreferenceKey) === null && window.innerWidth >= 1280) searchPanelVisible = true"');
    });

    test('header search toggle uses the same persisted visibility state', () => {
        expect(projectHeaderJs).toContain("searchPanelPreferenceKey: 'bilara:translation:search-panel-visible'");
        expect(projectHeaderJs).toContain('getStoredSearchPanelVisible()');
        expect(projectHeaderJs).toContain('togglePanelVisible() {');
        expect(projectHeaderJs).toContain('localStorage.setItem(this.searchPanelPreferenceKey, String(this.panelVisible));');
        expect(projectHeaderJs).toContain('@show-search-panel.window="panelVisible = true"');
    });
});
