const fs = require('fs');
const path = require('path');
const vm = require('vm');

const panelHtml = fs.readFileSync(
    path.resolve(__dirname, '../../../git_status_panel.html'),
    'utf8',
);

function loadPanel(requestWithTokenRetry, toast = { show: jest.fn() }) {
    const pullRequestSource = fs.readFileSync(
        path.resolve(__dirname, '../pullRequest.js'),
        'utf8',
    );
    const panelSource = fs.readFileSync(
        path.resolve(__dirname, '../git_status_panel.js'),
        'utf8',
    );
    const sandbox = {
        console,
        URL,
        requestWithTokenRetry,
        setTimeout: jest.fn(() => 1),
        clearTimeout: jest.fn(),
        window: { location: { search: '' } },
        document: {
            getElementById: jest.fn(),
            querySelector: jest.fn(selector => selector === 'sc-bilara-toast' ? toast : null),
        },
        localStorage: {
            getItem: jest.fn(() => null),
            setItem: jest.fn(),
        },
        addLoadingAttribute: jest.fn(),
        removeLoadingAttribute: jest.fn(),
        displayMessage: jest.fn(),
        getUserInfo: jest.fn(),
        fetch: jest.fn(),
    };

    vm.createContext(sandbox);
    vm.runInContext(
        `${pullRequestSource}\n${panelSource}\nthis.__gitStatusPanel = gitStatusPanel;`,
        sandbox,
    );
    return { panel: sandbox.__gitStatusPanel(), sandbox, toast };
}

async function flushMicrotasks(count = 8) {
    for (let index = 0; index < count; index += 1) {
        await Promise.resolve();
    }
}

describe('git status pull request notifications', () => {
    test('uses the shared toast component instead of Alpine toast markup', () => {
        expect(panelHtml).toContain(
            '<script type="module" src="./static/js/elements/addons/sc-bilara-toast.js"></script>',
        );
        expect(panelHtml).toContain('<sc-bilara-toast></sc-bilara-toast>');
        expect(panelHtml).not.toContain('x-show="toast.show"');
    });

    test('single-file publishing replaces the generic PR list with the exact PR link', async () => {
        const requestWithTokenRetry = jest.fn(async endpoint => {
            if (endpoint === 'pr/') {
                return {
                    ok: true,
                    json: async () => ({ task_id: 'task-1' }),
                };
            }
            if (endpoint === 'tasks/task-1/') {
                return {
                    ok: true,
                    json: async () => ({
                        status: 'SUCCESS',
                        result: 'https://github.com/suttacentral/bilara-data/pull/1234',
                    }),
                };
            }
            throw new Error(`Unexpected endpoint: ${endpoint}`);
        });
        const { panel, toast } = loadPanel(requestWithTokenRetry);
        panel.fetchStatus = jest.fn().mockResolvedValue();

        await panel.publishFile({ path: 'translation/en/user/mn1.json' });
        await flushMicrotasks();

        expect(panel.publishing).toBe(false);
        expect(toast.show).toHaveBeenNthCalledWith(
            1,
            'Pull Request scheduled for: translation/en/user/mn1.json.',
            'success',
            10000,
            [],
        );
        expect(toast.show).toHaveBeenLastCalledWith(
            'Pull Request created.',
            'success',
            0,
            [{
                label: 'View Pull Request ↗',
                href: 'https://github.com/suttacentral/bilara-data/pull/1234',
            }],
        );
    });

    test('batch publishing shows every created pull request in one notification', async () => {
        let scheduledTask = 0;
        const requestWithTokenRetry = jest.fn(async endpoint => {
            if (endpoint === 'pr/') {
                scheduledTask += 1;
                return {
                    ok: true,
                    json: async () => ({ task_id: `task-${scheduledTask}` }),
                };
            }
            if (endpoint === 'tasks/task-1/') {
                return {
                    ok: true,
                    json: async () => ({
                        status: 'SUCCESS',
                        result: 'https://github.com/suttacentral/bilara-data/pull/1234',
                    }),
                };
            }
            if (endpoint === 'tasks/task-2/') {
                return {
                    ok: true,
                    json: async () => ({
                        status: 'SUCCESS',
                        result: 'https://github.com/suttacentral/bilara-data/pull/1235',
                    }),
                };
            }
            throw new Error(`Unexpected endpoint: ${endpoint}`);
        });
        const { panel, toast } = loadPanel(requestWithTokenRetry);
        panel.fetchStatus = jest.fn().mockResolvedValue();
        panel.selectedFiles = [
            'translation/en/alice/sutta/mn/mn1_translation-en-alice.json',
            'translation/fr/bob/sutta/sn/sn1_translation-fr-bob.json',
        ];

        await panel.batchPublish();
        await flushMicrotasks();

        expect(panel.batchPublishing).toBe(false);
        expect(toast.show).toHaveBeenNthCalledWith(
            1,
            'Pull Requests scheduled for 2 file(s) across 2 projects.',
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

    test('a batch scheduling failure does not hide successfully created pull requests', async () => {
        let scheduleRequest = 0;
        const requestWithTokenRetry = jest.fn(async endpoint => {
            if (endpoint === 'pr/') {
                scheduleRequest += 1;
                if (scheduleRequest === 1) {
                    return {
                        ok: true,
                        json: async () => ({ task_id: 'task-1' }),
                    };
                }
                return {
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
        const { panel, toast } = loadPanel(requestWithTokenRetry);
        panel.fetchStatus = jest.fn().mockResolvedValue();
        panel.selectedFiles = [
            'translation/en/alice/sutta/mn/mn1_translation-en-alice.json',
            'translation/fr/bob/sutta/sn/sn1_translation-fr-bob.json',
        ];

        await panel.batchPublish();
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
    const { panel } = loadPanel(request);
    panel.fetchStatus = jest.fn().mockResolvedValue();
    panel.selectedFiles = [...paths];
    await panel.batchPublish();
    await flushMicrotasks();
    const submissions = request.mock.calls.filter(([endpoint]) => endpoint === 'pr/');
    expect(submissions).toHaveLength(1);
    expect(JSON.parse(submissions[0][1].body)).toEqual({ paths });
});
