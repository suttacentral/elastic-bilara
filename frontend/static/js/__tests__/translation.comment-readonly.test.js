const fs = require('fs');
const path = require('path');
const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');
const createEditor = new Function(read('../translation.js') + '\nreturn fetchTranslation();');
const createSearch = new Function(read('../search.js') + '\nreturn search();');
const page = new DOMParser().parseFromString(read('../../../translation.html'), 'text/html');
function find(root, selector) {
    const found = root.querySelector(selector);
    if (found) return found;
    for (const template of root.querySelectorAll('template')) {
        const nested = find(template.content, selector);
        if (nested) return nested;
    }
}
const textarea = find(page, '.translation-cell__textarea');
const readonlyBinding = new Function('scope', `with (scope) { return ${textarea.getAttribute('x-bind:readonly')}; }`);
const searchEditable = find(page, 'template[x-if="canEditSearchSegment(seg.muid, entry.uid, isAdmin)"]');
const searchBinding = new Function('scope', `with (scope) { return ${searchEditable.getAttribute('x-if')}; }`);
const muid = 'comment-en-tester';
const lockedUids = ['an1.1:0.1', 'an1.1:0.2', 'an1.1:0.3', 'an1.1:1.0', 'an1.1:2.0', 'an1.1:1.0.2', 'an1.1:0', 'an1.1:00.1'];

beforeEach(() => { global.requestWithTokenRetry = jest.fn(); });

test.each(lockedUids)('%s stays visible but cannot be edited or saved', async uid => {
    const editor = createEditor();
    const translation = { muid, canEdit: true, data: { [uid]: 'existing comment' } };
    editor.translations = [translation];
    expect(readonlyBinding({ ...editor, translation, uid })).toBe(true);
    editor.setValue(translation, uid, 'changed');
    expect(translation.data[uid]).toBe('existing comment');
    expect(editor.dirtySegments).toEqual({});
    await editor.handleEnter({ shiftKey: true, target: { value: 'existing comment' } }, uid, 'changed', translation);
    await expect(editor.updateHandler(muid, { [uid]: 'changed', 'an1.1:1.1': 'allowed' })).rejects.toThrow(uid);
    expect(requestWithTokenRetry).not.toHaveBeenCalled();
});

test.each(['an1.1:10.1', 'an1.1:1.20', 'an10.0:1.1', 'an1.1:1.2', 'an1.1:10'])(
    '%s remains editable with project permission', uid => {
        const editor = createEditor();
        const translation = { muid, canEdit: true, data: { [uid]: 'old' } };
        expect(readonlyBinding({ ...editor, translation, uid })).toBe(false);
        editor.setValue(translation, uid, 'new');
        expect(translation.data[uid]).toBe('new');
        translation.canEdit = false;
        expect(readonlyBinding({ ...editor, translation, uid })).toBe(true);
        editor.setValue(translation, uid, 'denied');
        expect(translation.data[uid]).toBe('new');
    },
);

test.each(['translation-en-tester', 'root-pli-ms', 'html-pli-ms', 'tag-en-tester', 'remarks:1'])(
    '%s is unaffected by comment restrictions', otherMuid => {
        const editor = createEditor();
        const translation = { muid: otherMuid, canEdit: true, data: {} };
        const uid = 'an1.1:0.1';
        expect(editor.canEditSegment(translation, uid)).toBe(true);
        editor.setValue(translation, uid, 'new');
        expect(translation.data[uid]).toBe('new');
    },
);

test.each(lockedUids)('search cannot edit, replace or submit %s even with admin permission', async uid => {
    const s = createSearch();
    s.editableMusids[muid] = true;
    s.results = { [uid]: { [muid]: 'term' } };
    s._buildResultEntries();
    const seg = s.resultEntries[0].segments[0];
    expect(searchBinding({ ...s, seg, entry: { uid }, isAdmin: true })).toBe(false);
    await s.searchResultFocus(uid, muid);
    s.searchResultInput(uid, muid, 'changed');
    s.fields[muid] = 'term';
    s.replacementText = 'replacement';
    await s.replaceSegment(uid, muid, seg);
    expect(seg.segment).toBe('term');
    expect(s.results[uid][muid]).toBe('term');
    expect(s.replacedItems).toEqual({});
    await expect(s.searchResultSave(uid, muid, 'changed')).rejects.toThrow(uid);
    await expect(s.submitReplacement(uid, muid, 'changed')).rejects.toThrow(uid);
    expect(s.submittedItems).toEqual({});
    expect(requestWithTokenRetry).not.toHaveBeenCalled();
});

test('normal comment search edits still save with an authoritative snapshot', async () => {
    const s = createSearch();
    const uid = 'an1.1:10.1';
    s.editableMusids[muid] = true;
    s.results = { [uid]: { [muid]: 'old' } };
    s.resultPrefixes = { [uid]: { [muid]: 'an1.1' } };
    s._buildResultEntries();
    expect(s.canEditSearchSegment(muid, uid, true)).toBe(true);
    expect(s.canEditSearchSegment(muid, uid, false)).toBe(false);
    requestWithTokenRetry.mockResolvedValueOnce({ ok: true, json: async () => ({
        can_edit: true, structure_revision: 'v1', data: { [uid]: 'old' },
    }) });
    await s.searchResultFocus(uid, muid);
    s.searchResultInput(uid, muid, 'new');
    global.displayBadge = jest.fn();
    global.BadgeStatus = { PENDING: 'pending', COMMITTED: 'committed', ERROR: 'error' };
    requestWithTokenRetry.mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await s.searchResultSave(uid, muid, 'new');
    expect(JSON.parse(requestWithTokenRetry.mock.calls[1][1].body)).toEqual({ [uid]: 'new' });
});

test('structure previews lock zero comments and reject manually injected edits', async () => {
    const editor = createEditor();
    const uid = 'an1.1:0.1';
    const translation = { muid, canEdit: true, data: { [uid]: 'automatic result' } };
    editor.translations = [translation];
    editor.structureDraft = { reviewed: [], preview: {
        uid, operation: 'merge', manual_projects: [], projects: [{ muid, data: { ...translation.data } }],
    } };
    expect(editor.canEditSegment(translation, uid)).toBe(false);
    expect(editor.structureResultLabel(muid, uid)).toContain('Read-only');
    editor.setValue(translation, uid, 'manual');
    expect(translation.data[uid]).toBe('automatic result');
    translation.data[uid] = 'injected';
    await expect(editor.confirmStructureDraft('root-pli-ms', 'an1.1')).rejects.toThrow(uid);
    expect(requestWithTokenRetry).not.toHaveBeenCalled();
});

test('readonly textarea keydown never creates an edit status badge', () => {
    const ensureBadge = new Function(read('../utils.js') + '\nreturn ensureStatusBadge;')();
    const target = document.createElement('textarea');
    target.readOnly = true;
    document.body.appendChild(target);
    ensureBadge(target, muid, 'an1.1:0.1');
    expect(document.getElementsByTagName('sc-bilara-translation-edit-status')).toHaveLength(0);
    target.remove();
});
