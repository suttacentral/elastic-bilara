const fs = require('fs');
const path = require('path');

const authJsContent = fs.readFileSync(path.resolve(__dirname, '../auth.js'), 'utf8');
const utilsJsContent = fs.readFileSync(path.resolve(__dirname, '../utils.js'), 'utf8');

function loadAuth(search = '') {
    const window = {
        location: { origin: 'https://bilara.test', search, href: '/', replace: jest.fn() },
    };
    const fetch = jest.fn();
    const load = new Function(
        'window', 'fetch', 'setInterval',
        `${authJsContent}; ${utilsJsContent}; return { getToken, getUserInfo };`,
    );
    return { ...load(window, fetch, jest.fn()), window, fetch };
}

const response = status => ({ status, ok: status >= 200 && status < 300 });

describe('home page authentication', () => {
    test('redirects an existing session to the navigation page without an OAuth code', async () => {
        const { getToken, window, fetch } = loadAuth();
        fetch.mockResolvedValue(response(200));

        await getToken();

        expect(fetch).toHaveBeenCalledWith('https://bilara.test/api/v1/users/me', {
            credentials: 'include',
        });
        expect(window.location.href).toBe('/nav');
    });

    test('refreshes an expired access token and verifies the session before redirecting', async () => {
        const { getToken, window, fetch } = loadAuth();
        fetch.mockResolvedValueOnce(response(401))
            .mockResolvedValueOnce(response(200))
            .mockResolvedValueOnce(response(200));

        await getToken();

        expect(fetch).toHaveBeenNthCalledWith(2, 'https://bilara.test/api/v1/refresh/', {
            method: 'POST', credentials: 'include',
        });
        expect(fetch).toHaveBeenNthCalledWith(3, 'https://bilara.test/api/v1/users/me', {
            credentials: 'include',
        });
        expect(window.location.href).toBe('/nav');
    });

    test('keeps visitors without a valid session on the login page', async () => {
        const { getToken, window, fetch } = loadAuth();
        fetch.mockResolvedValue(response(401));

        await getToken();

        expect(fetch).toHaveBeenCalledTimes(2);
        expect(window.location.href).toBe('/');
    });

    test('does not redirect if the session is still invalid after refreshing', async () => {
        const { getToken, window, fetch } = loadAuth();
        fetch.mockResolvedValueOnce(response(401))
            .mockResolvedValueOnce(response(200))
            .mockResolvedValueOnce(response(401));

        await getToken();

        expect(window.location.href).toBe('/');
    });

    test('does not redirect when the identity endpoint fails', async () => {
        const { getToken, window, fetch } = loadAuth();
        fetch.mockResolvedValue(response(503));

        await getToken();

        expect(fetch).toHaveBeenCalledTimes(1);
        expect(window.location.href).toBe('/');
    });

    test.each([200, 401])('preserves OAuth callback behavior for status %s', async status => {
        const { getToken, window, fetch } = loadAuth('?code=github-code');
        fetch.mockResolvedValue(response(status));

        await getToken();

        expect(fetch).toHaveBeenCalledTimes(1);
        expect(fetch).toHaveBeenCalledWith('https://bilara.test/api/v1/token/?code=github-code');
        expect(window.location.href).toBe(status === 200 ? '/nav' : '/');
    });
});

describe('navigation page authentication', () => {
    test('returns a logged-out visitor to the home page when loading their role', async () => {
        const { getUserInfo, window, fetch } = loadAuth();
        window.location.href = '/nav.html';
        fetch.mockResolvedValue(response(401));

        await expect(getUserInfo().getRole()).rejects.toThrow('Failed to load current user: 401');

        expect(fetch).toHaveBeenCalledTimes(2);
        expect(window.location.replace).toHaveBeenCalledWith('/');
    });

    test('loads the user without redirecting when token refresh succeeds', async () => {
        const { getUserInfo, window, fetch } = loadAuth();
        const user = { username: 'translator', role: 'writer', is_active: true };
        fetch.mockResolvedValueOnce(response(401))
            .mockResolvedValueOnce(response(200))
            .mockResolvedValueOnce({ ...response(200), json: async () => user });

        const userInfo = getUserInfo();
        await userInfo.getRole();

        expect(userInfo).toMatchObject({ username: 'translator', role: 'writer', isActive: true });
        expect(window.location.replace).not.toHaveBeenCalled();
    });

    test('returns to the home page if the refreshed session is still unauthorized', async () => {
        const { getUserInfo, window, fetch } = loadAuth();
        fetch.mockResolvedValueOnce(response(401))
            .mockResolvedValueOnce(response(200))
            .mockResolvedValueOnce(response(401));

        await expect(getUserInfo().getRole()).rejects.toThrow('Failed to load current user: 401');

        expect(window.location.replace).toHaveBeenCalledWith('/');
    });

    test.each([403, 503])('does not treat HTTP %s as a logged-out session', async status => {
        const { getUserInfo, window, fetch } = loadAuth();
        fetch.mockResolvedValue(response(status));

        await expect(getUserInfo().getRole()).rejects.toThrow(`Failed to load current user: ${status}`);

        expect(window.location.replace).not.toHaveBeenCalled();
    });

    test('does not redirect when the user request fails due to a network error', async () => {
        const { getUserInfo, window, fetch } = loadAuth();
        fetch.mockRejectedValue(new Error('Network unavailable'));

        await expect(getUserInfo().getRole()).rejects.toThrow('Network unavailable');

        expect(window.location.replace).not.toHaveBeenCalled();
    });
});
