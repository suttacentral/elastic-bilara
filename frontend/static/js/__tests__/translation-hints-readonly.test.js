const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '../../../translation.html'), 'utf8');
const page = new DOMParser().parseFromString(html, 'text/html');
// Cells are nested inside Alpine template elements.
function findCell(root) {
    const cell = root.querySelector('.translation-cell');
    if (cell) return cell;
    for (const template of root.querySelectorAll('template')) {
        const nested = findCell(template.content);
        if (nested) return nested;
    }
}
const cell = findCell(page);
const textarea = cell.querySelector('textarea');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const focus = new AsyncFunction('scope', `with (scope) { ${textarea.getAttribute('x-on:focus')} }`);
const syncHints = new Function('scope', `with (scope) { ${cell.getAttribute('x-effect')} }`);

function createScope() {
    const target = document.createElement('textarea');
    document.body.appendChild(target);
    target.focus();
    return {
        translation: { canEdit: true, muid: 'translation-en-test', isSource: false },
        canEditStructureSegment: jest.fn(() => true),
        uid: 'dn1:1.1', muid: 'translation-en-test', sourceMuid: 'root-pli-test', sourceValue: 'source',
        getValue: () => 'text', getHints: jest.fn(async () => [{ uid: 'hint', translation_hints: 'hint' }]),
        hints: [], visibleHints: [], showHints: false, hintClicked: false, originalValue: '',
        selectedHintIndex: -1, hintSelectionViaKeyboard: false,
        isTag: false, showTagSuggestions: false, tagSuggestions: [], selectedTagIndex: -1,
        filterTagSuggestions: jest.fn(),
        closeTagSuggestions() {
            this.showTagSuggestions = false;
            this.tagSuggestions = [];
            this.selectedTagIndex = -1;
        },
        hintStyle: 'inline', colIndex: 1, $dispatch: jest.fn(), $event: { target },
    };
}

afterEach(() => { document.body.innerHTML = ''; });

test.each(['structure', 'permission'])('readonly focus does not request or open hints (%s)', async (reason) => {
    const scope = createScope();
    if (reason === 'structure') scope.canEditStructureSegment.mockReturnValue(false);
    else scope.translation.canEdit = false;
    await focus(scope);
    expect(scope.getHints).not.toHaveBeenCalled();
    expect(scope.showHints).toBe(false);
});

test('readonly tag focus does not open suggestions', async () => {
    const scope = createScope();
    scope.isTag = true;
    scope.canEditStructureSegment.mockReturnValue(false);
    await focus(scope);
    expect(scope.filterTagSuggestions).not.toHaveBeenCalled();
});

test('editable focus still fetches and opens hints', async () => {
    const scope = createScope();
    await focus(scope);
    expect(scope.hints).toHaveLength(1);
    expect(scope.showHints).toBe(true);
});

test('a pending hints response cannot reopen hints after the cell becomes readonly', async () => {
    const scope = createScope();
    let resolveHints;
    scope.getHints.mockReturnValue(new Promise(resolve => { resolveHints = resolve; }));
    const pending = focus(scope);
    scope.canEditStructureSegment.mockReturnValue(false);
    resolveHints([{ uid: 'hint' }]);
    await pending;
    expect(scope.showHints).toBe(false);
});

test.each(['dropdown', 'inline'])('becoming readonly closes existing %s hints and tag suggestions', (style) => {
    const scope = createScope();
    Object.assign(scope, {
        hintStyle: style, hints: [{ uid: 'hint' }], showHints: true,
        selectedHintIndex: 0, hintSelectionViaKeyboard: true,
        showTagSuggestions: true, tagSuggestions: [{ tag: 'test' }], selectedTagIndex: 0,
    });
    scope.canEditStructureSegment.mockReturnValue(false);
    syncHints(scope);
    expect(scope.showHints).toBe(false);
    expect(scope.showTagSuggestions).toBe(false);
    expect(scope.selectedHintIndex).toBe(-1);
    expect(scope.hintSelectionViaKeyboard).toBe(false);
    expect(scope.$dispatch).toHaveBeenCalledWith('sync-row-hints', expect.objectContaining({ show: false }));
});
