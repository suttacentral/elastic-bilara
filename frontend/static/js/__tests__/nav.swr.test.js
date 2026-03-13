const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadNavRuntime(mocks = {}) {
    const navPath = path.resolve(__dirname, '../nav.js');
    const code = fs.readFileSync(navPath, 'utf8');

    const sandbox = {
        console,
        setTimeout,
        clearTimeout,
        window: { location: {}, open: jest.fn() },
        document: {
            querySelector: jest.fn(),
            querySelectorAll: jest.fn(() => []),
        },
        localStorage: {
            getItem: jest.fn(() => null),
        },
        requestWithTokenRetry: mocks.requestWithTokenRetry,
        getUserInfo: mocks.getUserInfo,
        getMuid: mocks.getMuid,
        getPrefix: mocks.getPrefix,
    };

    vm.createContext(sandbox);
    vm.runInContext(`${code}\nthis.__tree = tree; this.__Element = Element;`, sandbox);

    return {
        treeFactory: sandbox.__tree,
        Element: sandbox.__Element,
        sandbox,
    };
}

describe('nav.js SWR cache behavior', () => {
    let requestWithTokenRetry;
    let getUserInfo;
    let getMuid;
    let getPrefix;

    beforeEach(() => {
        requestWithTokenRetry = jest.fn(async (endpoint) => {
            if (endpoint.startsWith('directories/search/')) {
                return {
                    ok: true,
                    json: async () => ({ matches: [], total_matches: 0 }),
                };
            }

            if (endpoint === 'directories/') {
                return {
                    ok: true,
                    json: async () => ({ directories: [], base: null }),
                };
            }

            if (endpoint.startsWith('directories/')) {
                return {
                    ok: true,
                    json: async () => ({
                        base: 'translation/',
                        directories: [],
                        files: [],
                        files_with_progress: [],
                    }),
                };
            }

            return {
                ok: true,
                json: async () => ({}),
            };
        });
        getUserInfo = jest.fn(() => ({
            getRole: jest.fn().mockResolvedValue(),
            username: 'tester',
            isAdmin: false,
        }));
        getMuid = jest.fn(() => 'muid-test');
        getPrefix = jest.fn((name) => name.split('_')[0] || 'prefix');
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    test('uses fresh cache without sending network request', async () => {
        const { treeFactory, Element } = loadNavRuntime({
            requestWithTokenRetry,
            getUserInfo,
            getMuid,
            getPrefix,
        });

        const tree = treeFactory();
        const root = new Element('translation/', null, false, false);
        tree.data = [root];

        tree.directoryCache.set(root.fullName, {
            data: {
                base: 'translation/',
                directories: ['en/'],
                files: ['mn1_translation-en-test.json'],
                files_with_progress: [
                    {
                        name: 'mn1_translation-en-test.json',
                        progress: 80,
                        total_keys: 10,
                        translated_keys: 8,
                    },
                ],
            },
            timestamp: Date.now(),
            inflightPromise: null,
        });

        await tree.open(root);

        expect(requestWithTokenRetry).not.toHaveBeenCalled();
        expect(root.children.length).toBe(2);
        expect(root.children[0].isFile).toBe(false);
        expect(root.children[1].isFile).toBe(true);
        expect(root.children[1].progress).toBe(80);
        expect(root.loading).toBe(false);
    });

    test('uses stale cache immediately then revalidates in background', async () => {
        requestWithTokenRetry.mockResolvedValue({
            json: async () => ({
                base: 'translation/',
                directories: ['en/'],
                files: ['mn2_translation-en-test.json'],
                files_with_progress: [
                    {
                        name: 'mn2_translation-en-test.json',
                        progress: 90,
                        total_keys: 10,
                        translated_keys: 9,
                    },
                ],
            }),
        });

        const { treeFactory, Element } = loadNavRuntime({
            requestWithTokenRetry,
            getUserInfo,
            getMuid,
            getPrefix,
        });

        const tree = treeFactory();
        const root = new Element('translation/', null, false, false);
        tree.data = [root];

        let revalidatePromise = Promise.resolve();
        const originalRevalidate = tree.revalidateDirectory.bind(tree);
        tree.revalidateDirectory = (fullName) => {
            revalidatePromise = originalRevalidate(fullName);
            return revalidatePromise;
        };

        tree.directoryCache.set(root.fullName, {
            data: {
                base: 'translation/',
                directories: ['en/'],
                files: ['mn1_translation-en-test.json'],
                files_with_progress: [
                    {
                        name: 'mn1_translation-en-test.json',
                        progress: 70,
                        total_keys: 10,
                        translated_keys: 7,
                    },
                ],
            },
            timestamp: Date.now() - tree.cacheTTL - 1,
            inflightPromise: null,
        });

        await tree.open(root);

        // Stale data should be rendered immediately.
        expect(root.children.length).toBe(2);
        expect(root.children[1].name).toBe('mn1_translation-en-test.json');

        await revalidatePromise;

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(root.children[1].name).toBe('mn2_translation-en-test.json');
        expect(root.children[1].progress).toBe(90);
    });

    test('cache miss fetches from network and hydrates node', async () => {
        requestWithTokenRetry.mockResolvedValue({
            json: async () => ({
                base: 'translation/',
                directories: ['fr/'],
                files: ['dn1_translation-fr-test.json'],
                files_with_progress: [],
            }),
        });

        const { treeFactory, Element } = loadNavRuntime({
            requestWithTokenRetry,
            getUserInfo,
            getMuid,
            getPrefix,
        });

        const tree = treeFactory();
        const root = new Element('translation/', null, false, false);

        await tree.open(root);

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(requestWithTokenRetry).toHaveBeenCalledWith('directories/translation/');
        expect(root.children.length).toBe(2);
        expect(root.children[0].name).toBe('fr/');
        expect(root.children[1].name).toBe('dn1_translation-fr-test.json');
    });

    test('deduplicates in-flight requests for the same directory', async () => {
        let resolveJson;
        const jsonPromise = new Promise((resolve) => {
            resolveJson = resolve;
        });

        requestWithTokenRetry.mockResolvedValue({
            json: () => jsonPromise,
        });

        const { treeFactory } = loadNavRuntime({
            requestWithTokenRetry,
            getUserInfo,
            getMuid,
            getPrefix,
        });

        const tree = treeFactory();
        const key = 'translation/en/';

        const p1 = tree.fetchDirectoryData(key, { force: true });
        const p2 = tree.fetchDirectoryData(key, { force: true });

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);

        resolveJson({
            base: 'translation/en/',
            directories: ['dn/'],
            files: [],
            files_with_progress: [],
        });

        const [r1, r2] = await Promise.all([p1, p2]);
        expect(r1).toEqual(r2);
    });

    test('toggleShowAll clears directory cache', () => {
        const { treeFactory } = loadNavRuntime({
            requestWithTokenRetry,
            getUserInfo,
            getMuid,
            getPrefix,
        });

        const tree = treeFactory();
        tree.directoryCache.set('translation/', {
            data: { base: 'translation/', directories: [], files: [], files_with_progress: [] },
            timestamp: Date.now(),
            inflightPromise: null,
        });

        expect(tree.directoryCache.size).toBe(1);

        tree.init = jest.fn();
        tree.toggleShowAll();

        expect(tree.directoryCache.size).toBe(0);
        expect(tree.init).toHaveBeenCalledTimes(1);
    });
});
