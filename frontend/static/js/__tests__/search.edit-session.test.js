const fs = require('fs');
const path = require('path');
const createSearch = new Function(fs.readFileSync(path.join(__dirname, '../search.js'), 'utf8') + '\nreturn search();');
const uid = 'dn1:1.1';
const muid = 'translation-en-u';
const key = uid + '::' + muid;
const response = (data, ok = true) => ({ ok, json: async () => data });
let s;
beforeEach(() => {
    global.requestWithTokenRetry = jest.fn();
    global.displayBadge = jest.fn();
    global.BadgeStatus = { PENDING: 'pending', COMMITTED: 'committed', ERROR: 'error' };
    s = createSearch();
    s.results = { [uid]: { [muid]: 'stale term' } };
    s._buildResultEntries();
});
const snapshot = (revision = 'v1') => response({ can_edit: true, data: { [uid]: 'current term', 'dn1:1.2': 'second term' }, structure_revision: revision });

test('focus loads authoritative content before enabling edits and pins its version', async () => {
    requestWithTokenRetry.mockResolvedValueOnce(snapshot());
    await s.searchResultFocus(uid, muid);
    expect(s.results[uid][muid]).toBe('current term');
    expect(s.originalValues[key]).toBe('current term');
    s.searchResultInput(uid, muid, 'edited');
    await s.searchResultFocus(uid, muid);
    expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
    requestWithTokenRetry.mockResolvedValueOnce(response({}));
    await s.searchResultSave(uid, muid, 'edited');
    expect(requestWithTokenRetry.mock.calls[1][1].headers['X-Structure-Revision']).toBe('v1');
});

test('save without an edit snapshot never sends PATCH', async () => {
    await expect(s.searchResultSave(uid, muid, 'edited')).rejects.toThrow();
    await expect(s.submitReplacement(uid, muid, 'edited')).rejects.toThrow();
    expect(requestWithTokenRetry).not.toHaveBeenCalled();
});

test('unchanged edits skip saving but replacement submissions still save and mark success', async () => {
    s.originalValues[key] = 'unchanged';
    s.editStructureRevisions[key] = 'v1';
    await s.searchResultSave(uid, muid, 'unchanged');
    expect(requestWithTokenRetry).not.toHaveBeenCalled();
    expect(s.submittedItems[key]).toBeUndefined();

    requestWithTokenRetry.mockResolvedValueOnce(response({}));
    await s.submitReplacement(uid, muid, 'unchanged');
    expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
    expect(s.submittedItems[key]).toBe(true);
});

test.each(['searchResultSave', 'submitReplacement'])('%s preserves the draft and save state on conflict', async method => {
    s.originalValues[key] = 'original';
    s.editStructureRevisions[key] = 'v1';
    s.searchResultInput(uid, muid, 'draft');
    requestWithTokenRetry.mockResolvedValueOnce(response({ detail: 'Structure changed' }, false));

    await expect(s[method](uid, muid, 'draft')).rejects.toThrow('Structure changed');

    expect(s.results[uid][muid]).toBe('draft');
    expect(s.originalValues[key]).toBe('original');
    expect(s.editStructureRevisions[key]).toBe('v1');
    expect(s.submittedItems[key]).toBeUndefined();
    expect(displayBadge).toHaveBeenLastCalledWith(`search-badge-${muid}-${uid}`, BadgeStatus.ERROR);
});

test('another segment loading a newer version cannot relabel an existing draft', async () => {
    requestWithTokenRetry.mockResolvedValueOnce(snapshot());
    await s.searchResultFocus(uid, muid);
    requestWithTokenRetry.mockResolvedValueOnce(snapshot('v2'));
    await s.searchResultFocus('dn1:1.2', muid);
    requestWithTokenRetry.mockResolvedValueOnce(response({ detail: 'Structure changed' }, false));
    await expect(s.searchResultSave(uid, muid, 'edited')).rejects.toThrow('Structure changed');
    expect(requestWithTokenRetry.mock.calls[2][1].headers['X-Structure-Revision']).toBe('v1');
    expect(s.originalValues[key]).toBe('current term');
});

test('replace operates on authoritative content and submits its version', async () => {
    s.fields[muid] = 'term';
    s.replacementText = 'replacement';
    requestWithTokenRetry.mockResolvedValueOnce(snapshot());
    const seg = s.resultEntries[0].segments[0];
    await s.replaceSegment(uid, muid, seg);
    expect(seg.segment).toBe('current replacement');
    requestWithTokenRetry.mockResolvedValueOnce(response({}));
    await s.submitReplacement(uid, muid, seg.segment);
    expect(requestWithTokenRetry.mock.calls[1][1].headers['X-Structure-Revision']).toBe('v1');
});

test.each([
    { can_edit: false, data: { [uid]: 'text' }, structure_revision: 'v1' },
    { can_edit: true, data: {}, structure_revision: 'v1' },
    { can_edit: true, data: { [uid]: 'text' } },
])('invalid editing snapshot cannot enable a save: %j', async data => {
    requestWithTokenRetry.mockResolvedValueOnce(response(data));
    await expect(s.searchResultFocus(uid, muid)).rejects.toThrow();
    expect(s.editStructureRevisions[key]).toBeUndefined();
});

test('a pending edit load cannot overwrite a different result page', async () => {
    let resolve;
    requestWithTokenRetry.mockReturnValueOnce(new Promise(r => { resolve = r; }));
    const pending = s.searchResultFocus(uid, muid);
    s.results = { [uid]: { [muid]: 'new page' } };
    s._buildResultEntries();
    resolve(snapshot());
    await expect(pending).rejects.toThrow();
    expect(s.results[uid][muid]).toBe('new page');
    expect(s.editStructureRevisions[key]).toBeUndefined();
});

test('repeated focus shares a pending request; failed loads can be retried', async () => {
    let resolve;
    requestWithTokenRetry.mockReturnValueOnce(new Promise(r => { resolve = r; }));
    const first = s.searchResultFocus(uid, muid);
    const second = s.searchResultFocus(uid, muid);
    expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
    expect(s.editStructureRevisions[key]).toBeUndefined();
    resolve(response({ detail: 'Operation pending' }, false));
    await expect(first).rejects.toThrow('Operation pending');
    await expect(second).rejects.toThrow('Operation pending');
    requestWithTokenRetry.mockResolvedValueOnce(snapshot());
    await s.searchResultFocus(uid, muid);
    expect(s.editStructureRevisions[key]).toBe('v1');
});

test('search and prefetch do not load editing snapshots', async () => {
    s.fields[muid] = 'term';
    s.editableMusids[muid] = true;
    requestWithTokenRetry.mockResolvedValue(response({ results: s.results }));
    await s.searchHandler();
    expect(requestWithTokenRetry).toHaveBeenCalledTimes(2);
    expect(requestWithTokenRetry.mock.calls.every(([url]) => url.startsWith('search/?'))).toBe(true);
    expect(s.editStructureRevisions).toEqual({});
});
