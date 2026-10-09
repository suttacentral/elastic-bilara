const fs = require('fs');
const path = require('path');
const source = fs.readFileSync(path.resolve(__dirname, '../publications.js'), 'utf8');

function setup(admin = false, overrides = {}) {
    const request = jest.fn();
    const getCurrentUser = jest.fn().mockResolvedValue({ role: admin ? 'administrator' : 'writer', is_active: true, ...overrides });
    const manager = new Function('requestWithTokenRetry', 'getCurrentUser', `${source}; return publicationsManager;`)(request, getCurrentUser)(admin);
    return { manager, request };
}
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => JSON.parse(JSON.stringify(data)) });
const record = (overrides = {}) => ({
    publication_number: 'scpub1', creator_uid: ['alice', 'bob'], creator_name: ['Alice', 'Bob'],
    creator_github_handle: ['alice', 'bob'], translation_title: 'Original',
    source_url: 'https://example.test/existing/path', first_published: '2014',
    editions_url: 'https://example.test/current', _revision: 'revision-1',
    _editions: [{ edition_number: '2', publication_date: '2020', edition_url: 'https://example.test/current' },
        { edition_number: '1', publication_date: '2014', edition_url: ['book', 'ebook'] }], ...overrides,
});

beforeEach(() => { jest.useFakeTimers(); });
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

test('inactive users and reviewers cannot load publication records', async () => {
    for (const overrides of [{ role: 'reviewer' }, { is_active: false }]) {
        const { manager, request } = setup(false, overrides);
        await manager.init();
        expect(request).not.toHaveBeenCalled();
        expect(manager.authorized).toBe(false);
        expect(manager.loadError).toMatch(/active writer/);
    }
});

test('writer loads the server-filtered list and uses a fresh detail revision', async () => {
    const { manager, request } = setup();
    request.mockResolvedValueOnce(response([record()])).mockResolvedValueOnce(response(record()));
    await manager.init();
    await manager.showEditForm(manager.publications[0]);
    expect(manager.isAdmin).toBe(false);
    expect(manager.form.creator_name).toEqual(['Alice', 'Bob']);
    expect(manager.revision).toBe('revision-1');
    expect(request).toHaveBeenLastCalledWith('publications/scpub1');
});

test('writer sends only changed v2 fields and preserves arrays', async () => {
    const { manager, request } = setup();
    request.mockResolvedValueOnce(response(record()));
    await manager.showEditForm(record());
    manager.form.creator_name[1] = 'Bob Updated';
    manager.form.creator_github_handle[0] = 'forged';
    manager.form.is_published = true;
    manager.form.source_url = 'forged';
    manager.form.first_published = '2013';
    expect(manager.buildUpdate()).toEqual({ revision: 'revision-1',
        changes: { creator_name: ['Alice', 'Bob Updated'], first_published: '2013' } });
});

test('legacy false and publication_date do not turn into accidental changes', async () => {
    const { manager, request } = setup(true);
    request.mockResolvedValue(response(record({ first_published: undefined, publication_date: '2021',
        translation_lang_iso: false, license_abbreviation: false })));
    await manager.showEditForm(record());
    expect(manager.form.first_published).toBe('2021');
    expect(manager.form.translation_lang_iso).toBe('');
    expect(manager.buildUpdate().changes).toEqual({});
    manager.autoGenerateSourceUrl();
    expect(manager.form.source_url).toBe('https://example.test/existing/path');
});

test('conflict keeps edits visible and blocks another stale submission', async () => {
    const { manager, request } = setup();
    request.mockResolvedValueOnce(response(record())).mockResolvedValueOnce(response({ detail: 'Reload before saving' }, 409));
    await manager.showEditForm(record());
    manager.form.translation_title = 'Unsaved title';
    await manager.submitForm();
    expect(manager.view).toBe('form');
    expect(manager.form.translation_title).toBe('Unsaved title');
    expect(manager.conflict).toBe(true);
    expect(manager.formError).toBe('Reload before saving');
    await manager.submitForm();
    expect(request).toHaveBeenCalledTimes(2);
});

test('successful edit uses PATCH then refreshes the list', async () => {
    const { manager, request } = setup();
    request.mockResolvedValueOnce(response(record()))
        .mockResolvedValueOnce(response(record({ translation_title: 'New' })))
        .mockResolvedValueOnce(response([record({ translation_title: 'New' })]));
    await manager.showEditForm(record());
    manager.form.translation_title = 'New';
    await manager.submitForm();
    const options = request.mock.calls[1][1];
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(options.body).changes).toEqual({ translation_title: 'New' });
    expect(manager.publications[0].translation_title).toBe('New');
    expect(manager.view).toBe('list');
});

test('writer cannot start create, delete or GitHub submission actions', async () => {
    const { manager, request } = setup();
    await manager.showCreateForm();
    await manager.deletePub('scpub1');
    await manager.publishToGitHub();
    expect(request).not.toHaveBeenCalled();
});

test('queued GitHub submission is not reported as completed', async () => {
    const { manager, request } = setup(true);
    manager.isAdmin = true;
    window.confirm = jest.fn(() => true);
    request.mockResolvedValueOnce(response({ task_id: 'task' }, 202))
        .mockResolvedValueOnce(response({ status: 'SUCCESS', result: true }));
    await manager.publishToGitHub();
    expect(manager.publishStatus).toMatch(/queued/);
    await manager.checkPublishStatus();
    expect(manager.publishStatus).toMatch(/submitted to the unpublished branch/);
});

test('validation details produce readable field errors', () => {
    const { manager } = setup();
    expect(manager.errorMessage({ detail: [{ loc: ['body', 'changes', 'translation_title'], msg: 'Input should be a valid string' }] }))
        .toBe('changes.translation_title: Input should be a valid string');
});

test('duplicate creation leaves the publication number editable for retry', async () => {
    const { manager, request } = setup(true);
    manager.isAdmin = true;
    manager.resetForm();
    manager.form.publication_number = 'scpub10';
    manager.form.creator_uid = 'alice';
    manager.view = 'form';
    request.mockResolvedValueOnce(response({ detail: 'Publication number already exists.' }, 409));
    await manager.submitForm();
    expect(manager.conflict).toBe(false);
    expect(manager.view).toBe('form');
    expect(manager.formError).toMatch(/already exists/);
});

test('new team needs only v2 authors and keeps editing accounts independent', () => {
    const { manager } = setup(true);
    manager.isAdmin = true;
    manager.resetForm();
    Object.assign(manager.form, { publication_number: 'scpub6', creator_uid: 'alice', creator_name: 'Alice', creator_github_handle: 'editor' });
    manager.beginAuthorEdit();
    manager.setAuthorMode('team');
    manager.addAuthor();
    Object.assign(manager.authorRows[1], { uid: 'bob', name: 'Bob' });
    expect(manager.validateForm()).toBe(true);
    const body = manager.buildCreate();
    expect(body.creator_uid).toEqual(['alice', 'bob']);
    expect(body.creator_name).toEqual(['Alice', 'Bob']);
    expect(body.creator_github_handle).toBe('editor');
    expect(body.legacy).toBeUndefined();
    manager.authorRows[1].uid = 'alice';
    expect(manager.validateForm()).toBe(false);
    manager.authorRows[1].uid = ' ';
    expect(manager.validateForm()).toBe(false);
});

test('author editor uses every v2 author with a scalar editor account', async () => {
    const { manager, request } = setup(true);
    manager.isAdmin = true;
    request.mockResolvedValue(response(record({ creator_uid: ['weerakoon', 'medagoda', 'sujato', 'allon'],
        creator_name: ['Deepika', 'Roshini', 'Sujato', 'Mark'], creator_github_handle: 'sujato',
        _legacy_collaborators: [{ collaborator_uid: 'sujato', author_name: 'Sujato' }] })));
    await manager.showEditForm(record());
    manager.beginAuthorEdit();
    expect(manager.authorRows.map(row => row.uid)).toEqual(['weerakoon', 'medagoda', 'sujato', 'allon']);
    manager.addAuthor();
    Object.assign(manager.authorRows[4], { uid: 'carol', name: 'Carol' });
    manager.removeAuthor(2);
    expect(manager.buildUpdate()).toEqual({ revision: 'revision-1', changes: {
        creator_uid: ['weerakoon', 'medagoda', 'allon', 'carol'], creator_name: ['Deepika', 'Roshini', 'Mark', 'Carol'],
    } });
    expect(manager.form.creator_github_handle).toBe('sujato');
    manager.setAuthorMode('single');
    expect(manager.validateForm()).toBe(false);
    manager.singleAuthorIndex = '2';
    expect(manager.validateForm()).toBe(true);
    expect(manager.buildUpdate().changes).toEqual({ creator_uid: 'allon', creator_name: 'Mark' });
});

test('legacy-only authors are never imported and cancelling preserves ordinary edits', async () => {
    const { manager, request } = setup(true);
    manager.isAdmin = true;
    request.mockResolvedValue(response(record({ creator_uid: 'sujato', creator_name: 'Sujato', creator_github_handle: 'sujato',
        _legacy_collaborators: [{ collaborator_uid: 'sujato' }, { collaborator_uid: 'kovilo' }] })));
    await manager.showEditForm(record());
    manager.form.creator_name = 'Updated';
    manager.beginAuthorEdit();
    expect(manager.authorRows).toEqual([{ uid: 'sujato', name: 'Updated' }]);
    manager.setAuthorMode('team');
    manager.addAuthor();
    manager.editingAuthors = false;
    expect(manager.buildUpdate()).toEqual({ revision: 'revision-1', changes: { creator_name: 'Updated' } });
    manager.conflict = true;
    manager.formError = 'Reload before saving';
    manager.beginAuthorEdit();
    expect(manager.formError).toBe('Reload before saving');
});

test('administrator manages editing accounts separately from authors', async () => {
    const { manager, request } = setup(true);
    manager.isAdmin = true;
    request.mockResolvedValue(response(record({ creator_github_handle: 'editor' })));
    await manager.showEditForm(record());
    manager.addEditorHandle();
    manager.form.creator_github_handle[1] = 'second';
    manager.removeEditorHandle(0);
    expect(manager.buildUpdate().changes).toEqual({ creator_github_handle: ['second'] });
    manager.removeEditorHandle(0);
    expect(manager.buildUpdate().changes).toEqual({ creator_github_handle: [] });
});

test('writer cannot edit author structure or editing accounts', async () => {
    const { manager, request } = setup();
    request.mockResolvedValue(response(record()));
    await manager.showEditForm(record());
    manager.beginAuthorEdit();
    manager.addAuthor();
    manager.setAuthorMode('team');
    manager.addEditorHandle();
    manager.removeEditorHandle(0);
    expect(manager.editingAuthors).toBe(false);
    expect(manager.authorRows).toEqual([]);
    expect(manager.form.creator_github_handle).toEqual(['alice', 'bob']);
    manager.editingAuthors = true;
    manager.authorRows = [{ uid: 'hijack', name: 'Hijack' }];
    manager.singleAuthorIndex = '0';
    expect(manager.buildUpdate().changes).toEqual({});
});

test.each(['', ' \t', false, null, [], [' ']])('creation rejects missing or blank UID %p without opening author editor', async uid => {
    const { manager, request } = setup(true);
    manager.isAdmin = true;
    manager.resetForm();
    manager.form.publication_number = 'scpub6';
    manager.form.creator_uid = uid;
    await manager.submitForm();
    expect(request).not.toHaveBeenCalled();
    expect(manager.formErrors.creator_uid).toMatch(/required/);
    manager.form.creator_uid = 'alice';
    expect(manager.validateForm()).toBe(true);
});

test('ordinary edits preserve a historical false creator UID', async () => {
    const { manager, request } = setup(true);
    manager.isAdmin = true;
    request.mockResolvedValue(response(record({ creator_uid: false, creator_name: 'Foundation', creator_github_handle: false })));
    await manager.showEditForm(record());
    manager.form.translation_title = 'Updated';
    expect(manager.validateForm()).toBe(true);
    expect(manager.buildUpdate().changes).toEqual({ translation_title: 'Updated' });
});
