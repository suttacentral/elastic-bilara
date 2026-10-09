const fs = require('fs');
const path = require('path');
const read = name => fs.readFileSync(path.join(__dirname, name), 'utf8');
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

function binding(selector, attribute) {
    const expression = find(page, selector).getAttribute(attribute);
    return new Function('scope', `with (scope) { return (${expression}); }`);
}

function click(selector, scope) {
    const expression = find(page, selector).getAttribute('@click');
    return new Function('scope', `with (scope) { return (async () => { ${expression}; })(); }`)(scope);
}

const showReplace = binding('.search__replace-btn', 'x-show');
const showSubmit = binding('.search__submit-btn', 'x-show');
const showEditor = binding('template[x-if^="canEditSearchSegment("]', 'x-if');
const uid = 'dn1:1.1';
const muid = 'translation-en-author';
const response = data => ({ ok: true, json: async () => data });

function setup(role = 'writer', target = muid, segmentUid = uid) {
    const s = createSearch();
    s.role = role;
    s.isAdmin = ['administrator', 'superuser'].includes(role);
    s.results = { [segmentUid]: { [target]: 'old old' } };
    s.resultPrefixes = { [segmentUid]: { [target]: 'dn1' } };
    s.fields[target] = 'old';
    s.replacementText = 'new';
    s._buildResultEntries();
    s.entry = s.resultEntries[0];
    s.seg = s.entry.segments[0];
    return s;
}

beforeEach(() => {
    global.requestWithTokenRetry = jest.fn();
    global.displayBadge = jest.fn();
    global.BadgeStatus = { PENDING: 'pending', COMMITTED: 'committed', ERROR: 'error' };
});

test.each([
    ['writer', muid, true, uid, true],
    ['writer', 'translation-en-other', false, uid, false],
    ['writer', muid, undefined, uid, false],
    ['writer', 'comment-en-author', true, uid, false],
    ['writer', 'html-pli-ms', true, uid, false],
    ['writer', 'tag-en-author', true, uid, false],
    ['writer', 'root-pli-ms', true, uid, false],
    ['reviewer', muid, true, uid, false],
    ['', muid, true, uid, false],
    ['administrator', muid, true, uid, true],
    ['superuser', muid, true, uid, true],
    ['superuser', muid, false, uid, false],
    ['administrator', 'comment-en-author', true, 'dn1:0.1', false],
    ['administrator', 'comment-en-author', true, uid, true],
])('%s with %s access=%s at %s has search editing=%s', (role, target, access, segmentUid, allowed) => {
    const s = setup(role, target, segmentUid);
    s.editableMusids[target] = access;
    expect(Boolean(showReplace(s))).toBe(allowed);
    expect(showEditor(s)).toBe(allowed);
    s.replacedItems[segmentUid + '::' + target] = true;
    expect(Boolean(showSubmit(s))).toBe(allowed);
});

test.each(['administrator', 'superuser'])('%s cannot replace root text in search', role => {
    const s = setup(role, 'root-pli-ms');
    s.editableMusids['root-pli-ms'] = true;
    expect(Boolean(showReplace(s))).toBe(false);
    expect(binding('.search__results-textarea', ':readonly')(s)).toBe(true);
});

test('writer can replace and submit a translation authorized by the server', async () => {
    const s = setup();
    requestWithTokenRetry.mockResolvedValueOnce(response({ can_edit: true }));
    await s._fetchEditPermissions(s.results);
    expect(requestWithTokenRetry).toHaveBeenLastCalledWith(`projects/${muid}/can-edit/`);
    expect(Boolean(showReplace(s))).toBe(true);
    expect(Boolean(showSubmit(s))).toBe(false);

    requestWithTokenRetry.mockResolvedValueOnce(response({
        can_edit: true, structure_revision: 'v1', data: { [uid]: 'current old old' },
    }));
    await click('.search__replace-btn', s);
    expect(s.seg.segment).toBe('current new new');
    expect(Boolean(showReplace(s))).toBe(false);
    expect(Boolean(showSubmit(s))).toBe(true);
    expect(requestWithTokenRetry.mock.calls.every(([, options]) => !options?.method)).toBe(true);

    requestWithTokenRetry.mockResolvedValueOnce(response({}));
    await click('.search__submit-btn', s);
    expect(requestWithTokenRetry).toHaveBeenLastCalledWith(`projects/${muid}/dn1/`, expect.objectContaining({
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', 'X-Structure-Revision': 'v1' },
        body: JSON.stringify({ [uid]: 'current new new' }),
    }));
    expect(Boolean(showSubmit(s))).toBe(false);
});

test('server denial keeps a writer translation result read-only', async () => {
    const s = setup();
    requestWithTokenRetry.mockResolvedValueOnce(response({ can_edit: false }));
    await s._fetchEditPermissions(s.results);
    expect(Boolean(showReplace(s))).toBe(false);
    expect(showEditor(s)).toBe(false);
});
