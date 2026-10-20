const fs = require('fs');
const path = require('path');
const source = fs.readFileSync(path.resolve(__dirname, '../tags.js'), 'utf8');
const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const record = (tag = 'old') => ({ tag, expansion: '', definition: '' });

function setup() {
    const request = jest.fn().mockResolvedValue(response({ status: 'idle' }));
    const alert = jest.fn();
    const confirm = jest.fn(() => true);
    const manager = new Function('requestWithTokenRetry', 'alert', 'confirm', `${source}; return tagsManager();`)(request, alert, confirm);
    return { manager, request, alert, confirm };
}

beforeEach(() => jest.useFakeTimers());
afterEach(() => { jest.clearAllTimers(); jest.useRealTimers(); });

it('loads persisted failed sync status on page initialization and permits retry', async () => {
    const { manager, request } = setup();
    request.mockResolvedValueOnce(response([record()])).mockResolvedValueOnce(response({
        status: 'failed', error: 'Push rejected', can_retry: true,
    }));
    await manager.init();
    expect(manager.tags).toEqual([record()]);
    expect(manager.syncStatus).toMatch(/failed.*Push rejected/);
    expect(manager.canRetrySync).toBe(true);
    request.mockResolvedValueOnce(response({ status: 'pending', can_retry: false }, 202));
    await manager.retrySync();
    expect(request).toHaveBeenCalledWith('tags/sync/retry/', { method: 'POST', credentials: 'include' });
});

it.each(['add', 'edit', 'delete'])('%s consumes sync metadata separately from tag records', async action => {
    const { manager, request } = setup();
    manager.tags = [record()];
    request.mockResolvedValueOnce(response(action === 'delete'
        ? { detail: 'deleted', _sync: { status: 'pending' } }
        : { ...record('new'), _sync: { status: 'pending' } }));
    request.mockResolvedValue(response({ status: 'queued' }));
    if (action === 'add') {
        manager.newTag = record('new');
        await manager.addTag();
        expect(manager.tags[1]).toEqual(record('new'));
    } else if (action === 'edit') {
        manager.startEdit(record());
        manager.editingTag.tag = 'new';
        await manager.saveEdit();
        expect(manager.tags[0]).toEqual(record('new'));
        expect(manager.editingTag).toBeNull();
    } else {
        await manager.deleteTag('old');
        expect(manager.tags).toEqual([]);
    }
    expect(manager.syncStatus).not.toMatch(/Saved and synced/);
    expect(manager.saving).toBe(false);
    expect(manager.tags.every(tag => !Object.hasOwn(tag, '_sync'))).toBe(true);
});

it('shows success only from the durable synced state', async () => {
    const { manager, request } = setup();
    for (const status of ['pending', 'queued', 'syncing', 'retrying']) {
        manager.setSyncStatus({ status });
        expect(manager.syncStatus).not.toMatch(/Saved and synced/);
    }
    request.mockResolvedValue(response({ status: 'synced', can_retry: false }));
    await manager.checkSyncStatus();
    expect(manager.syncStatus).toMatch(/synced to the unpublished branch/);
    expect(jest.getTimerCount()).toBe(0);
});

it('ignores a stale status response after a newer save', async () => {
    const { manager, request } = setup();
    let complete;
    request.mockReturnValueOnce(new Promise(resolve => { complete = resolve; }));
    const checking = manager.checkSyncStatus();
    manager.beginSave();
    manager.setSyncStatus({ status: 'pending', generation: 'newer' });
    manager.saving = false;
    complete(response({ status: 'synced', generation: 'old' }));
    await checking;
    expect(manager.syncState).toBe('pending');
});

it('blocks duplicate mutations while an HTTP save is in flight', async () => {
    const { manager, request } = setup();
    let complete;
    manager.newTag = record('new');
    request.mockReturnValueOnce(new Promise(resolve => { complete = resolve; }));
    const saving = manager.addTag();
    await manager.addTag();
    await manager.deleteTag('old');
    expect(request).toHaveBeenCalledTimes(1);
    complete(response({ ...record('new'), _sync: { status: 'pending' } }));
    await saving;
});

it('retains the draft on validation/storage failure and checks recovery status', async () => {
    const { manager, request, alert } = setup();
    manager.tags = [record()];
    manager.startEdit(record());
    manager.editingTag.tag = 'new';
    request.mockResolvedValueOnce(response({ detail: 'Storage unavailable; reload before retrying.' }, 503));
    request.mockResolvedValue(response({ status: 'pending' }));
    await manager.saveEdit();
    expect(manager.editingTag.tag).toBe('new');
    expect(manager.tags[0].tag).toBe('old');
    expect(alert).toHaveBeenCalledWith(expect.stringContaining('reload'));
    expect(request).toHaveBeenLastCalledWith('tags/sync/');
});

it('stops polling on lost authorization or component destruction', async () => {
    const { manager, request } = setup();
    manager.setSyncStatus({ status: 'queued' });
    request.mockResolvedValue(response({ detail: 'Forbidden' }, 403));
    await manager.checkSyncStatus();
    expect(jest.getTimerCount()).toBe(0);
    expect(manager.canRetrySync).toBe(false);
    manager.setSyncStatus({ status: 'pending' });
    manager.destroy();
    expect(jest.getTimerCount()).toBe(0);
});

it('keeps polling when the status service is temporarily unavailable', async () => {
    const { manager, request } = setup();
    request.mockRejectedValue(new Error('offline'));
    await manager.checkSyncStatus();
    expect(manager.syncStatus).toMatch(/Unable to check.*offline/);
    expect(jest.getTimerCount()).toBe(1);
});
