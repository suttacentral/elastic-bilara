const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadNav() {
    const sandbox = {
        window: { history: { state: null } },
        document: { addEventListener: jest.fn() },
    };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../utils.js'), 'utf8'), sandbox);
    vm.runInContext(fs.readFileSync(path.resolve(__dirname, '../nav.js'), 'utf8') +
        '\nthis.nav = tree(); this.Node = Element;', sandbox);
    sandbox.nav.filterUsername = 'ayyasoma';
    sandbox.nav.userRole = 'writer';
    return sandbox;
}

test.each([true, false])('directory response controls publishing: %s', allowed => {
    const { nav, Node } = loadNav();
    const parent = new Node('sutta/', 'translation/it/soma/', false, false);
    nav.hydrateElementFromData(parent, {
        base: parent.fullName,
        directories: ['sn/'],
        files: ['sn1_translation-it-soma.json'],
        virtual_directories: ['an/'],
        virtual_files: [{ name: 'sn2_translation-it-soma.json', target_muid: 'translation-it-soma' }],
        publish_permissions: { 'translation-it-soma': allowed },
    });
    for (const element of [parent, ...parent.children]) {
        expect(nav.renderNode(element).includes('btn--publish')).toBe(allowed && !element.isVirtual);
    }
});

test('username and administrator role do not override backend denial', () => {
    const { nav, Node } = loadNav();
    const node = new Node('sutta/', 'translation/it/ayyasoma/', false, false);
    nav.userRole = 'administrator';
    expect(nav.renderNode(node)).not.toContain('btn--publish');
});

test.each([true, false])('search initialization uses backend permission: %s', async allowed => {
    const sandbox = loadNav();
    sandbox.window = { history: { state: null } };
    sandbox.getUserInfo = () => ({
        username: 'ayyasoma', role: 'writer', getRole: async () => {},
    });
    sandbox.requestWithTokenRetry = jest.fn(async () => ({
        json: async () => ({
            matches: [{ path: 'translation/it/soma/sutta/' }],
            publish_permissions: { 'translation-it-soma': allowed },
        }),
    }));
    sandbox.nav.addData = jest.fn(async () => {});
    await sandbox.nav.init();
    const projectDirectory = sandbox.nav.data[0].children[0].children[0].children[0];
    expect(sandbox.nav.renderNode(projectDirectory).includes('btn--publish')).toBe(allowed);
});

async function loadProjectTree(showAllContent, allowed = true, savedState = null) {
    const sandbox = loadNav();
    const responses = {
        'directories/search/ayyasoma/': {
            matches: [
                { path: 'translation/it/soma/' },
                { path: 'translation/it/soma/sutta/' },
            ],
            publish_permissions: { 'translation-it-soma': allowed },
        },
        'directories/': { base: null, directories: ['translation/'] },
        'directories/translation/': { base: 'translation/', directories: ['it/'] },
        'directories/translation/it/': { base: 'translation/it/', directories: ['soma/'] },
        'directories/translation/it/soma/': {
            base: 'translation/it/soma/', directories: ['sutta/'],
        },
        'directories/translation/it/soma/sutta/': {
            base: 'translation/it/soma/sutta/',
            directories: ['mn/'],
            virtual_directories: ['sn/'],
            files: ['mn1_translation-it-soma.json'],
            virtual_files: [{ name: 'mn2_translation-it-soma.json', target_muid: 'translation-it-soma' }],
        },
    };
    sandbox.window.history.state = savedState;
    sandbox.window.scrollTo = jest.fn();
    sandbox.getUserInfo = () => ({
        username: 'ayyasoma', role: 'writer', getRole: async () => {},
    });
    sandbox.requestWithTokenRetry = jest.fn(async endpoint => {
        if (!Object.hasOwn(responses, endpoint)) throw new Error(`Unexpected request: ${endpoint}`);
        return {
            ok: true,
            json: async () => ({
                publish_permissions: { 'translation-it-soma': allowed },
                ...responses[endpoint],
            }),
        };
    });
    sandbox.nav.$nextTick = jest.fn(async () => {});
    sandbox.nav.showAllContent = showAllContent;
    await sandbox.nav.init();
    if (showAllContent) {
        for (const directory of [
            'translation/', 'translation/it/', 'translation/it/soma/', 'translation/it/soma/sutta/',
        ]) {
            await sandbox.nav.open(sandbox.nav.getElementByName(directory));
        }
    }
    return sandbox;
}

function summarizeTree(nav) {
    const nodes = [];
    const visit = elements => {
        for (const element of elements) {
            const container = document.createElement('div');
            container.innerHTML = nav.renderNode(element);
            nodes.push({
                path: element.fullName,
                muid: element.muid,
                publish: Boolean(container.firstElementChild.querySelector('.btn--publish')),
            });
            visit(element.children);
        }
    };
    visit(nav.data);
    return nodes;
}

test.each([true, false])('both content modes use the same paths, MUIDs and publish buttons: %s', async allowed => {
    const mine = await loadProjectTree(false, allowed);
    const all = await loadProjectTree(true, allowed);
    const nodes = summarizeTree(mine.nav);
    expect(nodes).toEqual(summarizeTree(all.nav));
    expect(nodes).toEqual([
        { path: 'translation/', muid: null, publish: false },
        { path: 'translation/it/', muid: null, publish: false },
        { path: 'translation/it/soma/', muid: 'translation-it-soma', publish: false },
        { path: 'translation/it/soma/sutta/', muid: 'translation-it-soma', publish: allowed },
        { path: 'translation/it/soma/sutta/mn/', muid: 'translation-it-soma', publish: allowed },
        { path: 'translation/it/soma/sutta/sn/', muid: 'translation-it-soma', publish: false },
        { path: 'translation/it/soma/sutta/mn1_translation-it-soma.json', muid: 'translation-it-soma', publish: allowed },
        { path: 'translation/it/soma/sutta/mn2_translation-it-soma.json', muid: 'translation-it-soma', publish: false },
    ]);
});

test.each([
    ['translation/it/soma/', false],
    ['translation//it/soma//', false],
    ['translation/it/soma/sutta/', true],
    ['translation/it/soma/sutta', true],
])('publish directory depth counts actual path segments: %s', (directory, expected) => {
    const { nav, Node } = loadNav();
    const node = new Node(directory, null, false, false);
    nav.applyPublishPermission(node, { 'translation-it-soma': true });
    expect(nav.renderNode(node).includes('btn--publish')).toBe(expected);
});

test('my texts restores legacy paths and saves canonical directory paths', async () => {
    const savedState = {
        bilaraNav: {
            version: 1,
            showAllContent: false,
            openDirectories: ['translation//it/soma//', 'translation//', 'translation/it//'],
            scrollY: 120,
        },
    };
    const { nav, window } = await loadProjectTree(false, true, savedState);
    for (const directory of ['translation/', 'translation/it/', 'translation/it/soma/']) {
        expect(nav.getElementByName(directory).isOpen).toBe(true);
    }
    expect(nav.getElementByName('translation/it/soma/sutta/').isOpen).toBe(false);
    expect(nav.createHistoryState().openDirectories).toEqual([
        'translation/', 'translation/it/', 'translation/it/soma/',
    ]);
    expect(savedState.bilaraNav.openDirectories[0]).toBe('translation//it/soma//');
    expect(window.scrollTo).toHaveBeenCalledWith(0, 120);
});

test.each([false, true])('directory publishing selects its modified files in content mode %s', async showAllContent => {
    const sandbox = await loadProjectTree(showAllContent);
    const { nav } = sandbox;
    const directory = nav.data[0].children[0].children[0].children[0];
    const included = [
        'translation/it/soma/sutta/mn1_translation-it-soma.json',
        'translation/it/soma/sutta/mn/mn2_translation-it-soma.json',
    ];
    nav.getModifiedFiles = jest.fn(async () => [
        ...included,
        'translation/it/soma/sutta-other/mn3_translation-it-soma.json',
        'translation/it/other/sutta/mn4_translation-it-other.json',
    ]);
    nav.showToast = jest.fn();
    sandbox.groupPublicationPathsByProject = paths => [paths];
    sandbox.showPullRequestTaskResults = jest.fn();
    sandbox.requestWithTokenRetry.mockImplementation(async () => ({
        ok: true,
        json: async () => ({ task_id: 'publish-task' }),
    }));
    nav.openPublishModal(directory.fullName);
    await nav.confirmPublish();
    expect(sandbox.requestWithTokenRetry).toHaveBeenCalledWith('pr/', expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ paths: included }),
    }));
});


describe('site and blurb directory publishing', () => {
    test.each(['site', 'blurb'])('%s root uses directory response permissions', project => {
        for (const allowed of [true, false]) {
            const { nav, Node } = loadNav();
            const node = new Node(`${project}/`, 'translation/de/', false, false);
            nav.hydrateElementFromData(node, {
                base: node.fullName,
                directories: ['name/'],
                files: ['example.json'],
                virtual_directories: ['virtual/'],
                publish_permissions: { [`translation-de-${project}`]: allowed },
            });
            for (const item of [node, ...node.children]) {
                expect(nav.renderNode(item).includes('btn--publish')).toBe(allowed && !item.isVirtual);
            }
        }
    });

    test.each([
        ['translation/de/site', true],
        ['translation/de/site/', true],
        ['translation/de/site/name/sutta/', true],
        ['translation/de/blurb', true],
        ['translation/de/blurb/', true],
        ['root/misc/site/', true],
        ['translation/de/sabbamitta/', false],
        ['translation/de/', false],
        ['translation/', false],
    ])('button eligibility at %s', (directory, expected) => {
        const { nav, Node } = loadNav();
        const node = new Node(directory, null, false, false);
        node.canPublish = true;
        expect(nav.renderNode(node).includes('btn--publish')).toBe(expected);
        node.isVirtual = true;
        expect(nav.renderNode(node)).not.toContain('btn--publish');
        node.isVirtual = false;
        node.canPublish = false;
        expect(nav.renderNode(node)).not.toContain('btn--publish');
    });

    test.each(['site', 'blurb'])('search results expose the %s root only when allowed', async project => {
        for (const allowed of [true, false]) {
            const sandbox = loadNav();
            sandbox.getUserInfo = () => ({ username: 'tester', role: 'writer', getRole: async () => {} });
            sandbox.requestWithTokenRetry = jest.fn(async () => ({
                json: async () => ({
                    matches: [{ path: `translation/de/${project}/` }],
                    publish_permissions: { [`translation-de-${project}`]: allowed },
                }),
            }));
            sandbox.nav.addData = jest.fn(async () => {});
            await sandbox.nav.init();
            const node = sandbox.nav.getElementByName(`translation/de/${project}/`);
            expect(sandbox.nav.renderNode(node).includes('btn--publish')).toBe(allowed);
        }
    });
});
