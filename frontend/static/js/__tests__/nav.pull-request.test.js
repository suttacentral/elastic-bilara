const fs = require('fs');
const path = require('path');
const vm = require('vm');

function loadNav(requestWithTokenRetry, toast) {
    const navSource = fs.readFileSync(path.resolve(__dirname, '../nav.js'), 'utf8');
    const pullRequestSource = fs.readFileSync(
        path.resolve(__dirname, '../pullRequest.js'),
        'utf8',
    );
    const sandbox = {
        console,
        URL,
        requestWithTokenRetry,
        setTimeout: jest.fn(() => 1),
        clearTimeout: jest.fn(),
        window: { location: {}, open: jest.fn() },
        document: {
            getElementById: jest.fn(),
            querySelector: jest.fn(selector => selector === 'sc-bilara-toast' ? toast : null),
            querySelectorAll: jest.fn(() => []),
        },
        localStorage: {
            getItem: jest.fn(() => null),
        },
        ROLES: {
            admin: 'administrator',
            superuser: 'superuser',
        },
        getUserInfo: jest.fn(() => ({
            getRole: jest.fn().mockResolvedValue(),
            username: 'tester',
            isAdmin: false,
        })),
        getMuid: jest.fn(() => 'translation-en-tester'),
        getPrefix: jest.fn(() => 'mn1'),
        addLoadingAttribute: jest.fn(),
        removeLoadingAttribute: jest.fn(),
        displayMessage: jest.fn(),
    };

    vm.createContext(sandbox);
    vm.runInContext(
        `${navSource}\n${pullRequestSource}\nthis.__tree = tree;`,
        sandbox,
    );
    return sandbox.__tree();
}

async function flushMicrotasks(count = 8) {
    for (let index = 0; index < count; index += 1) {
        await Promise.resolve();
    }
}

describe('navigation pull request notifications', () => {
    test('directory publishing shows every exact pull request link', async () => {
        let scheduledTask = 0;
        const requestWithTokenRetry = jest.fn(async endpoint => {
            if (endpoint === 'pr/') {
                scheduledTask += 1;
                return {
                    ok: true,
                    json: async () => ({ task_id: `task-${scheduledTask}` }),
                };
            }
            const taskNumber = endpoint === 'tasks/task-1/' ? 1 : 2;
            return {
                ok: true,
                json: async () => ({
                    status: 'SUCCESS',
                    result: `https://github.com/suttacentral/bilara-data/pull/${1233 + taskNumber}`,
                }),
            };
        });
        const toast = { show: jest.fn() };
        const nav = loadNav(requestWithTokenRetry, toast);
        nav.publishingFile = 'translation/';
        nav.showPublishModal = true;
        nav.getElementByName = jest.fn(() => ({ isFile: false }));
        nav.getModifiedFiles = jest.fn().mockResolvedValue([
            'translation/en/alice/sutta/mn/mn1_translation-en-alice.json',
            'translation/fr/bob/sutta/sn/sn1_translation-fr-bob.json',
        ]);

        await nav.confirmPublish();
        await flushMicrotasks();

        expect(nav.isPublishing).toBe(false);
        expect(toast.show).toHaveBeenNthCalledWith(
            1,
            'Pull Requests scheduled for 2 file(s).',
            'success',
            10000,
            [],
        );
        expect(toast.show).toHaveBeenLastCalledWith(
            '2 Pull Requests created.',
            'success',
            0,
            [
                {
                    label: 'View Pull Request 1 ↗',
                    href: 'https://github.com/suttacentral/bilara-data/pull/1234',
                },
                {
                    label: 'View Pull Request 2 ↗',
                    href: 'https://github.com/suttacentral/bilara-data/pull/1235',
                },
            ],
        );
    });

    test('directory publishing keeps successful PR links when another group cannot be scheduled', async () => {
        let scheduleRequest = 0;
        const requestWithTokenRetry = jest.fn(async endpoint => {
            if (endpoint === 'pr/') {
                scheduleRequest += 1;
                return scheduleRequest === 1
                    ? { ok: true, json: async () => ({ task_id: 'task-1' }) }
                    : {
                        ok: false,
                        status: 503,
                        json: async () => ({ detail: 'Queue unavailable' }),
                    };
            }
            return {
                ok: true,
                json: async () => ({
                    status: 'SUCCESS',
                    result: 'https://github.com/suttacentral/bilara-data/pull/1234',
                }),
            };
        });
        const toast = { show: jest.fn() };
        const nav = loadNav(requestWithTokenRetry, toast);
        nav.publishingFile = 'translation/';
        nav.getElementByName = jest.fn(() => ({ isFile: false }));
        nav.getModifiedFiles = jest.fn().mockResolvedValue([
            'translation/en/alice/sutta/mn/mn1_translation-en-alice.json',
            'translation/fr/bob/sutta/sn/sn1_translation-fr-bob.json',
        ]);

        await nav.confirmPublish();
        await flushMicrotasks();

        expect(toast.show).toHaveBeenLastCalledWith(
            'Pull Request created. 1 failed.',
            'error',
            0,
            [{
                label: 'View Pull Request ↗',
                href: 'https://github.com/suttacentral/bilara-data/pull/1234',
            }],
        );
    });

    test("superuser can publish another user's modified translation", async () => {
        const otherUserPath = 'translation/en/alice/sutta/mn/mn1_translation-en-alice.json';
        const requestWithTokenRetry = jest.fn(async (endpoint, options) => {
            if (endpoint === 'git/status') {
                return {
                    ok: true,
                    json: async () => ({
                        files: [{ path: 'translation/en/tester/sutta/sn/sn1_translation-en-tester.json' }],
                    }),
                };
            }
            if (endpoint === 'git/status?include_other_users=true') {
                return {
                    ok: true,
                    json: async () => ({ files: [{ path: otherUserPath }] }),
                };
            }
            if (endpoint === 'pr/') {
                return {
                    ok: true,
                    json: async () => ({ task_id: 'task-1' }),
                };
            }
            return {
                ok: true,
                json: async () => ({
                    status: 'SUCCESS',
                    result: 'https://github.com/suttacentral/bilara-data/pull/1234',
                }),
            };
        });
        const toast = { show: jest.fn() };
        const nav = loadNav(requestWithTokenRetry, toast);
        nav.userRole = 'superuser';
        nav.publishingFile = 'translation/en/alice/';
        nav.getElementByName = jest.fn(() => ({ isFile: false }));

        await nav.confirmPublish();

        expect(requestWithTokenRetry).toHaveBeenCalledWith(
            'pr/',
            expect.objectContaining({
                body: JSON.stringify({ paths: [otherUserPath] }),
            }),
        );
    });
});


test('publishing KN files across vaggas schedules exactly one PR', async () => {
    const paths = [
        'translation/de/sabbamitta/sutta/kn/ud/vagga1/ud1.1.json',
        'translation/de/sabbamitta/sutta/kn/iti/vagga2/iti11.json',
        'translation/de/sabbamitta/sutta/kn/kp/kp1.json',
    ];
    const request = jest.fn(async endpoint => ({
        ok: true,
        json: async () => endpoint === 'pr/'
            ? { task_id: 'kn-task' }
            : { status: 'SUCCESS', result: 'https://github.com/example/pull/1' },
    }));
    const toast = { show: jest.fn() };
    const nav = loadNav(request, toast);
    nav.publishingFile = 'translation/de/sabbamitta/sutta/kn';
    nav.getElementByName = jest.fn(() => ({ isFile: false }));
    nav.getModifiedFiles = jest.fn().mockResolvedValue(paths);
    await nav.confirmPublish();
    await flushMicrotasks();
    const submissions = request.mock.calls.filter(([endpoint]) => endpoint === 'pr/');
    expect(submissions).toHaveLength(1);
    expect(JSON.parse(submissions[0][1].body)).toEqual({ paths });
});
