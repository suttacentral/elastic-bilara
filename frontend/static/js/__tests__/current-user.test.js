const fs = require('fs');
const path = require('path');

const utilsJsContent = fs.readFileSync(
    path.resolve(__dirname, '../utils.js'),
    'utf8',
);

function loadUserApi(requestWithTokenRetry) {
    const loadUtils = new Function(
        'requestWithTokenRetry',
        'window',
        'document',
        'CustomEvent',
        `${utilsJsContent}; return { getCurrentUser, getUserInfo };`,
    );
    return loadUtils(requestWithTokenRetry, window, document, CustomEvent);
}

function deferred() {
    let resolve;
    const promise = new Promise(resolvePromise => {
        resolve = resolvePromise;
    });
    return { promise, resolve };
}

describe('current user loading', () => {
    test('concurrent consumers share one users/me request', async () => {
        const response = deferred();
        const requestWithTokenRetry = jest.fn(() => response.promise);
        const { getCurrentUser } = loadUserApi(requestWithTokenRetry);

        const first = getCurrentUser();
        const second = getCurrentUser();

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(requestWithTokenRetry).toHaveBeenCalledWith('users/me');

        response.resolve({
            ok: true,
            status: 200,
            json: jest.fn().mockResolvedValue({ username: 'user' }),
        });

        await expect(Promise.all([first, second])).resolves.toEqual([
            { username: 'user' },
            { username: 'user' },
        ]);
    });

    test('a failed request is not cached', async () => {
        const requestWithTokenRetry = jest.fn()
            .mockResolvedValueOnce({
                ok: false,
                status: 503,
                json: jest.fn(),
            })
            .mockResolvedValueOnce({
                ok: true,
                status: 200,
                json: jest.fn().mockResolvedValue({ username: 'user' }),
            });
        const { getCurrentUser } = loadUserApi(requestWithTokenRetry);

        await expect(getCurrentUser()).rejects.toThrow('Failed to load current user: 503');
        await expect(getCurrentUser()).resolves.toEqual({ username: 'user' });

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(2);
    });

    test('getUserInfo shares the cached user and preserves its public fields', async () => {
        const user = {
            role: 'administrator',
            is_active: true,
            username: 'admin-user',
            avatar_url: 'https://example.test/avatar.png',
            github_id: 123,
        };
        const requestWithTokenRetry = jest.fn().mockResolvedValue({
            ok: true,
            status: 200,
            json: jest.fn().mockResolvedValue(user),
        });
        const { getCurrentUser, getUserInfo } = loadUserApi(requestWithTokenRetry);
        const userInfo = getUserInfo();

        await Promise.all([getCurrentUser(), userInfo.getRole()]);

        expect(requestWithTokenRetry).toHaveBeenCalledTimes(1);
        expect(userInfo).toMatchObject({
            isAdmin: true,
            isActive: true,
            username: 'admin-user',
            avatarURL: 'https://example.test/avatar.png',
            role: 'administrator',
            githubId: 123,
        });
    });
});
