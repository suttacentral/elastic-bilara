const fs = require('fs');
const path = require('path');

const page = new DOMParser().parseFromString(
    fs.readFileSync(path.join(__dirname, '../../../translation.html'), 'utf8'),
    'text/html',
);

function findInTemplates(root, selector) {
    const match = root.querySelector(selector);
    if (match) return match;
    for (const template of root.querySelectorAll('template')) {
        const nested = findInTemplates(template.content, selector);
        if (nested) return nested;
    }
}

const cellTemplate = findInTemplates(page, '.translation-cell');
const dropdownTemplate = findInTemplates(cellTemplate, '.translation-cell__hints-item');
const textareaTemplate = cellTemplate.querySelector('textarea');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const run = (expression, scope) => new AsyncFunction('scope', `with (scope) { ${expression} }`)(scope);
const originalExecCommand = document.execCommand;

afterEach(() => {
    document.body.innerHTML = '';
    document.execCommand = originalExecCommand;
    delete window.userSettings;
});

test.each(['dropdown', 'inline', 'keyboard'])(
    '%s hint selection replaces the owning textarea and updates its data',
    async (mode) => {
        window.userSettings = {};
        const cell = cellTemplate.cloneNode(true);
        const item = dropdownTemplate.cloneNode(true);
        cell.appendChild(item);
        document.body.appendChild(cell);
        const textarea = cell.querySelector('textarea');
        const otherCell = document.createElement('div');
        otherCell.innerHTML = '<textarea>Other translation</textarea>';
        document.body.prepend(otherCell);
        textarea.value = 'Previous translation';
        const translation = { canEdit: true, muid: 'translation-en-test', data: {} };
        const scope = { translation, uid: 'dn1:1.1', rowIndex: 0, colIndex: 1,
            canEditStructureSegment: () => true,
            translations: [],
            setValue: (target, uid, value) => { target.data[uid] = value; },
        };
        Object.defineProperties(scope, Object.getOwnPropertyDescriptors(
            new Function('scope', `with (scope) { return (${cellTemplate.getAttribute('x-data')}); }`)(scope),
        ));
        // Alpine's $el is the element whose expression is being evaluated.
        scope.$el = mode === 'dropdown' ? item : mode === 'keyboard' ? textarea : cell;
        scope.hints = [{ uid: 'hint', translation_hints: 'Suggested translation' }];
        scope.showHints = true;
        scope.selectedHintIndex = 0;
        scope.hintSelectionViaKeyboard = true;
        scope.hintIndex = 0;
        scope.handleEnter = jest.fn();
        textarea.addEventListener('input', (event) => {
            run(textareaTemplate.getAttribute('x-on:input'), { ...scope, $event: event });
        });
        // jsdom has no editing commands; emulate insertText on the focused selection.
        document.execCommand = jest.fn((command, ui, value) => {
            document.activeElement.setRangeText(value);
            return true;
        });

        if (mode === 'inline') {
            let callback;
            scope.$dispatch = (name, detail) => { callback = detail.selectCallback; };
            await run(cellTemplate.getAttribute('x-effect'), scope);
            callback(0);
        } else {
            await run(mode === 'dropdown'
                ? dropdownTemplate.getAttribute('@click')
                : textareaTemplate.getAttribute('x-on:keydown.enter.prevent'), scope);
        }

        expect(textarea.value).toBe('Suggested translation');
        expect(translation.data[scope.uid]).toBe('Suggested translation');
        expect(otherCell.querySelector('textarea').value).toBe('Other translation');
        expect(document.activeElement).toBe(textarea);
        expect(scope.showHints).toBe(false);
        expect(scope.selectedHintIndex).toBe(-1);
        expect(scope.hintSelectionViaKeyboard).toBe(false);
        expect(scope.handleEnter).not.toHaveBeenCalled();
    },
);
