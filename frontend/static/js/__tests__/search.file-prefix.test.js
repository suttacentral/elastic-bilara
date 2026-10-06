const fs = require('fs');
const path = require('path');
const createSearch = new Function(fs.readFileSync(path.join(__dirname, '../search.js'), 'utf8') + '\nreturn search();');
const muid = 'translation-en-sujato';
const response = data => ({ ok: true, json: async () => data });
const page = (uid, prefix) => ({ results: { [uid]: { [muid]: 'for life ends in death. ' } }, prefixes: { [uid]: { [muid]: prefix } } });
let s;
beforeEach(() => {
    global.requestWithTokenRetry = jest.fn();
    global.displayBadge = jest.fn();
    global.BadgeStatus = { PENDING: 'pending', COMMITTED: 'committed', ERROR: 'error' };
    window.history.replaceState({}, '', '/translation?prefix=mn1&muid=translation-en-sujato&source=root-pli-ms');
    s = createSearch();
    s.editableMusids[muid] = true;
});

test.each(['searchResultSave', 'submitReplacement'])('range file is used for loading, %s and navigation', async save => {
    const result = page('dhp148:4', 'dhp146-156');
    requestWithTokenRetry.mockResolvedValueOnce(response(result)).mockResolvedValueOnce(response({ results: {}, prefixes: {} }));
    await s.searchHandler();
    expect(s.isNextPage).toBe(false);
    requestWithTokenRetry.mockResolvedValueOnce(response({ can_edit: true, data: { 'dhp148:4': 'for life ends in death. ' }, structure_revision: 'v1' }));
    if (save === 'submitReplacement') {
        s.fields[muid] = 'death';
        s.replacementText = 'rest';
        await s.replaceSegment('dhp148:4', muid, s.resultEntries[0].segments[0]);
        expect(s.results['dhp148:4'][muid]).toBe('for life ends in rest. ');
    } else {
        await s.searchResultFocus('dhp148:4', muid);
    }
    expect(requestWithTokenRetry.mock.calls[2][0]).toBe(`projects/${muid}/dhp146-156/`);
    requestWithTokenRetry.mockResolvedValueOnce(response({}));
    await s[save]('dhp148:4', muid, 'edited');
    expect(requestWithTokenRetry.mock.calls[3][0]).toBe(`projects/${muid}/dhp146-156/`);
    expect(requestWithTokenRetry.mock.calls[3][1].headers['X-Structure-Revision']).toBe('v1');
    const url = new URL(s.getResultUrl(s.resultEntries[0]), window.location.href);
    expect(url.searchParams.get('prefix')).toBe('dhp146-156');
    expect(url.searchParams.get('uid')).toBe('dhp148:4');
});

test('prefetch and previous-page navigation keep prefixes paired with their results', async () => {
    const first = page('dhp148:4', 'dhp146-156');
    const second = page('sn3.22:4.2', 'sn3.22');
    requestWithTokenRetry.mockResolvedValueOnce(response(first)).mockResolvedValueOnce(response(second));
    await s.searchHandler();
    expect(s.getResultPrefix('dhp148:4', muid)).toBe('dhp146-156');
    expect(s.isNextPage).toBe(true);
    requestWithTokenRetry.mockResolvedValueOnce(response({ results: {}, prefixes: {} }));
    await s.nextHandler();
    expect(s.getResultPrefix('sn3.22:4.2', muid)).toBe('sn3.22');
    expect(s.isNextPage).toBe(false);
    requestWithTokenRetry.mockResolvedValueOnce(response(first)).mockResolvedValueOnce(response(second));
    await s.previousHandler();
    expect(s.getResultPrefix('dhp148:4', muid)).toBe('dhp146-156');
});

test('each project uses its own file prefix', () => {
    s.resultPrefixes = { 'dhp148:4': { [muid]: 'dhp146-156', 'translation-xx-other': 'dhp148' } };
    expect(s.getResultPrefix('dhp148:4', muid)).toBe('dhp146-156');
    expect(s.getResultPrefix('dhp148:4', 'translation-xx-other')).toBe('dhp148');
});
