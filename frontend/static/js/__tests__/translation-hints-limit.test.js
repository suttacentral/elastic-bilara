const fs = require('fs');
const path = require('path');

describe('translation hints limit wiring', () => {
  const translationHtml = fs.readFileSync(
    path.join(__dirname, '../../../translation.html'),
    'utf8'
  );
  const utilsJs = fs.readFileSync(
    path.join(__dirname, '../utils.js'),
    'utf8'
  );

  test('uses the user hint_count setting instead of a hard-coded limit', () => {
    expect(translationHtml).toContain('hintCount');
    expect(translationHtml).toContain('this.hints.slice(0, this.hintCount)');
    expect(translationHtml).not.toContain('this.hints.slice(0, 5)');
  });

  test('updates hint count when settings are saved', () => {
    expect(translationHtml).toContain('hintCount = Number($event.detail.hint_count) || 5');
    expect(translationHtml).toContain('@settings-loaded.window');
  });

  test('notifies initialized cells when user settings load', () => {
    expect(utilsJs).toContain("new CustomEvent('settings-loaded'");
  });
});
