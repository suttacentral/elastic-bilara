const fs = require('fs');
const path = require('path');

const createSearch = new Function(
    fs.readFileSync(path.join(__dirname, '../search.js'), 'utf8') + '\nreturn search();',
);
const createTranslation = new Function(
    fs.readFileSync(path.join(__dirname, '../translation.js'), 'utf8') + '\nreturn fetchTranslation();',
);
const page = new DOMParser().parseFromString(
    fs.readFileSync(path.join(__dirname, '../../../translation.html'), 'utf8'),
    'text/html',
);
const panelInit = page.querySelector('.project-container__detail-panel__search').getAttribute('x-init');
const SOURCE = 'root-pli-ms';
const TARGET = 'translation-en-user';
const response = data => ({ ok: true, json: async () => data });

function deferred() {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
    return { promise, resolve, reject };
}

function setup(params = { prefix: 'mn1', muid: TARGET, path: 'translation/en/user/mn1.json' }) {
    window.history.replaceState({}, '', `/translation.html?${new URLSearchParams(params)}`);
    const sourceRequest = deferred();
    const projectsRequest = deferred();
    requestWithTokenRetry.mockImplementation(endpoint => {
        if (endpoint === 'projects/') return projectsRequest.promise;
        if (endpoint.endsWith('/source/')) return sourceRequest.promise;
        throw new Error(`Unexpected request: ${endpoint}`);
    });
    const translation = createTranslation();
    // Keep source resolution and page initialization real; stub unrelated data loads.
    translation.loadCurrentUserForTranslation = jest.fn().mockResolvedValue({});
    translation.loadHyphenatedPrefixRanges = jest.fn().mockResolvedValue();
    translation.fetchRelatedProjects = jest.fn().mockResolvedValue([SOURCE, TARGET]);
    translation.fetchRemarkUsers = jest.fn().mockResolvedValue([]);
    translation.loadAvailableTags = jest.fn().mockResolvedValue();
    translation.fetchData = jest.fn().mockResolvedValue({ data: {}, can_edit: false });
    return { translation, sourceRequest, projectsRequest };
}

function mountPanel(translation) {
    const panel = createSearch();
    Object.setPrototypeOf(panel, translation);
    // Execute the actual HTML binding with a small adapter for Alpine's watcher.
    panel.$watch = (key, callback) => {
        let value = translation[key];
        Object.defineProperty(translation, key, {
            configurable: true,
            get: () => value,
            set(next) {
                const previous = value;
                value = next;
                if (next !== previous) callback(next, previous);
            },
        });
    };
    const initialized = panel.init();
    new Function('scope', `with (scope) { ${panelInit || ''} }`)(panel);
    return { panel, initialized };
}

beforeEach(() => {
    localStorage.clear();
    global.requestWithTokenRetry = jest.fn();
});

test.each(['projects', 'source'])('includes the resolved source when %s finishes first', async first => {
    const { translation, sourceRequest, projectsRequest } = setup();
    const loading = translation.initialize();
    const { panel, initialized } = mountPanel(translation);
    if (first === 'projects') {
        projectsRequest.resolve(response({ projects: [SOURCE, TARGET] }));
        await initialized;
        sourceRequest.resolve(response({ muid: SOURCE }));
        await loading;
    } else {
        sourceRequest.resolve(response({ muid: SOURCE }));
        await loading;
        expect(panel.fields[SOURCE]).toBe('');
        projectsRequest.resolve(response({ projects: [SOURCE, TARGET] }));
        await initialized;
    }
    expect(translation.sourceMuid).toBe(SOURCE);
    expect(panel.fields).toEqual({ uid: '', [TARGET]: '', [SOURCE]: '' });
    expect(panel.selectedProjects[SOURCE]).toBe(true);
});

test('includes a source resolved before the search panel mounts', async () => {
    const { translation, sourceRequest, projectsRequest } = setup();
    sourceRequest.resolve(response({ muid: SOURCE }));
    await translation.initialize();
    // The binding must use page state even without source in the URL.
    window.history.replaceState({}, '', `/translation.html?prefix=mn1&muid=${TARGET}`);
    const { panel, initialized } = mountPanel(translation);
    projectsRequest.resolve(response({ projects: [SOURCE, TARGET] }));
    await initialized;
    expect(panel.fields[SOURCE]).toBe('');
});

test.each([TARGET, SOURCE, ''])('keeps the source for an explicit source URL with muid=%s', async muid => {
    const { translation, projectsRequest } = setup({ prefix: 'mn1', muid, source: SOURCE });
    const loading = translation.initialize();
    const { panel, initialized } = mountPanel(translation);
    projectsRequest.resolve(response({ projects: [SOURCE, TARGET] }));
    await Promise.all([loading, initialized]);
    expect(panel.fields[SOURCE]).toBe('');
    expect(Object.keys(panel.fields).filter(key => key === SOURCE)).toHaveLength(1);
});

test('does not clear an existing query when source resolution or the picker finishes', async () => {
    const { translation, sourceRequest, projectsRequest } = setup();
    const loading = translation.initialize();
    const { panel, initialized } = mountPanel(translation);
    panel.toggleSelectedProjects(SOURCE);
    panel.fields[SOURCE] = 'dhamma';
    sourceRequest.resolve(response({ muid: SOURCE }));
    await loading;
    projectsRequest.resolve(response({ projects: [SOURCE, TARGET] }));
    await initialized;
    expect(panel.fields[SOURCE]).toBe('dhamma');
});

test('preserves manual removal while the project picker is loading', async () => {
    const { translation, sourceRequest, projectsRequest } = setup();
    const loading = translation.initialize();
    const { panel, initialized } = mountPanel(translation);
    sourceRequest.resolve(response({ muid: SOURCE }));
    await loading;
    expect(panel.fields[SOURCE]).toBe('');
    panel.toggleSelectedProjects(SOURCE);
    projectsRequest.resolve(response({ projects: [SOURCE, TARGET] }));
    await initialized;
    expect(panel.fields).not.toHaveProperty(SOURCE);
    expect(panel.selectedProjects[SOURCE]).toBe(false);
});

test('keeps the resolved source field when the project picker request fails', async () => {
    const { translation, sourceRequest, projectsRequest } = setup();
    const loading = translation.initialize();
    const { panel, initialized } = mountPanel(translation);
    const failed = expect(initialized).rejects.toThrow('Picker unavailable');
    projectsRequest.reject(new Error('Picker unavailable'));
    await failed;
    sourceRequest.resolve(response({ muid: SOURCE }));
    await loading;
    expect(panel.fields[SOURCE]).toBe('');
});
