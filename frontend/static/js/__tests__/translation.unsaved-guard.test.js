const fs = require('fs');
const path = require('path');

const utilsSource = fs.readFileSync(path.resolve(__dirname, '../utils.js'), 'utf8');
const translationSource = fs.readFileSync(path.resolve(__dirname, '../translation.js'), 'utf8');

const { fetchTranslation } = new Function(
    `${utilsSource}\n${translationSource}\nreturn { fetchTranslation };`,
)();

const MUID = 'translation-en-tester';
const UID = 'mn1:1.1';

function createEditor() {
    const editor = fetchTranslation();
    editor.prefix = 'mn1';
    editor.translations = [{ muid: MUID, canEdit: true, isSource: false, data: { [UID]: 'original' } }];
    return editor;
}

function beforeUnloadEvent() {
    return { preventDefault: jest.fn(), returnValue: undefined };
}

describe('unsaved changes guard', () => {
    beforeEach(() => {
        global.requestWithTokenRetry = jest.fn();
        // updateHandler reports save status on the segment badge.
        document.body.innerHTML = `<span id="translation-badge-${MUID}-${UID}"></span>`;
    });

    test('does not block leaving without changes', () => {
        const editor = createEditor();
        const event = beforeUnloadEvent();

        editor.handleBeforeUnload(event);

        expect(event.preventDefault).not.toHaveBeenCalled();
        expect(event.returnValue).toBeUndefined();
    });

    test('blocks leaving with an unsaved segment edit', () => {
        const editor = createEditor();
        editor.setValue(editor.translations[0], UID, 'changed');
        const event = beforeUnloadEvent();

        editor.handleBeforeUnload(event);

        expect(event.preventDefault).toHaveBeenCalled();
        expect(event.returnValue).toBe('');
    });

    test('does not block when the edit is reverted to its original text', () => {
        const editor = createEditor();
        editor.setValue(editor.translations[0], UID, 'changed');
        editor.setValue(editor.translations[0], UID, 'original');

        expect(editor.hasUnsavedChanges()).toBe(false);
    });

    test('stops blocking after the edit is saved', async () => {
        requestWithTokenRetry.mockResolvedValue({ ok: true, json: async () => ({ materialized: true }) });
        const editor = createEditor();
        editor.setValue(editor.translations[0], UID, 'changed');

        await editor.updateHandler(MUID, { [UID]: 'changed' }, null);

        expect(editor.hasUnsavedChanges()).toBe(false);
    });

    test('keeps blocking after a failed save', async () => {
        requestWithTokenRetry.mockResolvedValue({
            ok: false, status: 500, json: async () => ({ detail: 'Save failed' }),
        });
        const editor = createEditor();
        editor.setValue(editor.translations[0], UID, 'changed');

        await expect(editor.updateHandler(MUID, { [UID]: 'changed' }, null)).rejects.toThrow('Save failed');

        expect(editor.hasUnsavedChanges()).toBe(true);
    });

    test('blocks leaving with an unconfirmed split or merge draft', () => {
        const editor = createEditor();
        editor.structureDraft = { preview: { operation: 'split' }, reviewed: [], submission: null };

        expect(editor.hasUnsavedChanges()).toBe(true);
    });

    test('init registers one beforeunload handler across retries', async () => {
        const addSpy = jest.spyOn(window, 'addEventListener');
        const editor = createEditor();
        editor.initialize = jest.fn().mockResolvedValue();

        await editor.init();
        await editor.init();

        const handlers = addSpy.mock.calls.filter(([type]) => type === 'beforeunload').map(([, handler]) => handler);
        expect(handlers).toHaveLength(2);
        expect(handlers[0]).toBe(handlers[1]);
        addSpy.mockRestore();
        window.removeEventListener('beforeunload', handlers[0]);
    });
});
