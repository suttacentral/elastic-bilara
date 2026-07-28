const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadNavRuntime({
    historyState = { existing: 'value' },
    directoryResponses = {},
} = {}) {
    const code = fs.readFileSync(path.resolve(__dirname, '../nav.js'), 'utf8');
    const replaceState = jest.fn();
    const requestWithTokenRetry = jest.fn(async (endpoint) => {
        if (directoryResponses[endpoint]) {
            return {
                ok: true,
                json: async () => directoryResponses[endpoint],
            };
        }
        if (endpoint === 'directories/') {
            return {
                ok: true,
                json: async () => ({ directories: [], base: null }),
            };
        }
        if (endpoint.startsWith('directories/search/')) {
            return {
                ok: true,
                json: async () => ({ matches: [], total_matches: 0 }),
            };
        }
        return {
            ok: true,
            json: async () => ({ muid: 'root-pli-ms' }),
        };
    });
    const sandbox = {
        console,
        setTimeout,
        clearTimeout,
        window: {
            location: {},
            scrollY: 640,
            scrollTo: jest.fn(),
            history: {
                state: historyState,
                replaceState,
            },
            open: jest.fn(),
        },
        document: {
            querySelector: jest.fn(),
            querySelectorAll: jest.fn(() => []),
        },
        requestWithTokenRetry,
        getUserInfo: jest.fn(() => ({
            getRole: jest.fn().mockResolvedValue(),
            username: 'tester',
            role: 'writer',
        })),
        getMuid: jest.fn(() => 'translation-en-tester'),
        getPrefix: jest.fn(() => 'mn1'),
        ROLES: {
            admin: 'administrator',
            superuser: 'superuser',
            writer: 'writer',
        },
    };

    vm.createContext(sandbox);
    vm.runInContext(`${code}\nthis.__tree = tree; this.__Element = Element;`, sandbox);

    return {
        treeFactory: () => {
            const navigation = sandbox.__tree();
            navigation.$nextTick = jest.fn(() => Promise.resolve());
            return navigation;
        },
        Element: sandbox.__Element,
        replaceState,
        requestWithTokenRetry,
        sandbox,
    };
}

describe('navigation history state', () => {
    test('saves the current navigation view before opening a translation', async () => {
        const { treeFactory, Element, replaceState, sandbox } = loadNavRuntime();
        const navigation = treeFactory();
        navigation.showAllContent = true;

        const root = new Element('translation/', null, true, false);
        const language = new Element('en/', 'translation/', true, false);
        const user = new Element('tester/', 'translation/en/', false, false);
        const file = new Element(
            'mn1_translation-en-tester.json',
            'translation/en/tester/',
            false,
            true,
        );
        root.add(language);
        language.add(user);
        user.add(file);
        navigation.data = [root];

        await navigation.redirectToFile(file);

        expect(replaceState).toHaveBeenCalledWith(
            {
                existing: 'value',
                bilaraNav: {
                    version: 1,
                    showAllContent: true,
                    openDirectories: ['translation/', 'translation/en/'],
                    scrollY: 640,
                },
            },
            '',
        );
        expect(sandbox.window.location.href).toBe(
            '/translation?prefix=mn1&muid=translation-en-tester&source=root-pli-ms',
        );
    });

    test('restores the saved content mode before loading directories', async () => {
        const { treeFactory, requestWithTokenRetry } = loadNavRuntime({
            historyState: {
                bilaraNav: {
                    version: 1,
                    showAllContent: true,
                    openDirectories: [],
                    scrollY: 0,
                },
            },
        });
        const navigation = treeFactory();

        await navigation.init();

        expect(navigation.showAllContent).toBe(true);
        expect(requestWithTokenRetry).toHaveBeenCalledWith('directories/');
        expect(requestWithTokenRetry).not.toHaveBeenCalledWith(
            'directories/search/tester/',
        );
    });

    test('reopens saved directories from parent to child', async () => {
        const { treeFactory, requestWithTokenRetry } = loadNavRuntime({
            historyState: {
                bilaraNav: {
                    version: 1,
                    showAllContent: true,
                    openDirectories: ['translation/en/', 'translation/'],
                    scrollY: 0,
                },
            },
            directoryResponses: {
                'directories/': {
                    directories: ['translation/'],
                    base: null,
                },
                'directories/translation/': {
                    base: 'translation/',
                    directories: ['en/'],
                    files: [],
                    files_with_progress: [],
                },
                'directories/translation/en/': {
                    base: 'translation/en/',
                    directories: ['tester/'],
                    files: [],
                    files_with_progress: [],
                },
            },
        });
        const navigation = treeFactory();

        await navigation.init();

        const root = navigation.getElementByName('translation/');
        const language = navigation.getElementByName('translation/en/');
        const user = navigation.getElementByName('translation/en/tester/');
        expect(root.isOpen).toBe(true);
        expect(language.isOpen).toBe(true);
        expect(user.isOpen).toBe(false);
        expect(requestWithTokenRetry.mock.calls.map(([endpoint]) => endpoint)).toEqual([
            'directories/',
            'directories/translation/',
            'directories/translation/en/',
        ]);
    });

    test('restores the scroll position after Alpine updates the directory tree', async () => {
        const { treeFactory, sandbox } = loadNavRuntime({
            historyState: {
                bilaraNav: {
                    version: 1,
                    showAllContent: true,
                    openDirectories: [],
                    scrollY: 380,
                },
            },
        });
        const navigation = treeFactory();

        await navigation.init();

        expect(navigation.$nextTick).toHaveBeenCalledTimes(1);
        expect(sandbox.window.scrollTo).toHaveBeenCalledWith(0, 380);
    });

    test('restores the view when my-text search falls back to all directories', async () => {
        const { treeFactory } = loadNavRuntime({
            historyState: {
                bilaraNav: {
                    version: 1,
                    showAllContent: false,
                    openDirectories: ['translation/'],
                    scrollY: 120,
                },
            },
            directoryResponses: {
                'directories/': {
                    directories: ['translation/'],
                    base: null,
                },
                'directories/translation/': {
                    base: 'translation/',
                    directories: [],
                    files: [],
                    files_with_progress: [],
                },
            },
        });
        const navigation = treeFactory();

        await navigation.init();

        expect(navigation.getElementByName('translation/').isOpen).toBe(true);
        expect(navigation.$nextTick).toHaveBeenCalledTimes(1);
    });
});
