const fs = require('fs');
const path = require('path');

const translationHtml = fs.readFileSync(
    path.join(__dirname, '../../../translation.html'),
    'utf8'
);

describe('translation hint Enter behavior', () => {
    test('accepts TM hints through the focused textarea edit path', () => {
        expect(translationHtml).toContain('applyHintToTextarea(value) {');
        expect(translationHtml).toContain("document.execCommand('insertText', false, value)");
        expect(translationHtml).toContain("textarea.dispatchEvent(new Event('input', { bubbles: true }))");
    });

    test('accepts TM hints on Enter only after explicit keyboard navigation', () => {
        expect(translationHtml).toContain('hintSelectionViaKeyboard');
        expect(translationHtml).toContain('hintSelectionViaKeyboard && showHints && selectedHintIndex >= 0 && selectedHintIndex < visibleHints.length');
    });

    test('mouse hover over TM hints does not make Enter accept that hint', () => {
        expect(translationHtml).not.toContain('@mouseenter="hintSelectionViaKeyboard = false; selectedHintIndex = hintIndex"');
        expect(translationHtml).not.toContain('rowHintsHoverCallback');
        expect(translationHtml).not.toContain('hoverCallback:');
    });
});
