const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadNav() {
    const sandbox = {
        getMuid: value => value.split('/').filter(Boolean).slice(0, 3).join('-'),
        getPrefix: value => value.split('_')[0],
        ROLES: { writer: 'writer', admin: 'administrator', superuser: 'superuser' },
    };
    vm.createContext(sandbox);
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
