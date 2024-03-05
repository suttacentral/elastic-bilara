const API_URL = param => new URL(`api/v1/${param}`, window.location.origin).href;

async function getToken() {
    const code = new URLSearchParams(window.location.search).get("code");
    if (!code) {
        return;
    }
    try {
        const res = await fetch(API_URL(`token/?code=${code}`));
        if (res.ok) {
            window.location.href = "/nav";
        }
    } catch (error) {
        throw new Error(error);
    }
}

async function logout() {
    try {
        const res = await fetch(API_URL("logout/"), { method: "POST" });
        if (res.ok) {
            window.location.href = "/";
        }
    } catch (error) {
        throw new Error(error);
    }
}

async function getNewAccessToken() {
    try {
        const res = await fetch(API_URL("refresh/"), { method: "POST", credentials: "include" });
        return res.ok;
    } catch (error) {
        throw new Error(error);
    }
}

async function requestWithTokenRetry(
    endpoint,
    options = {
        credentials: "include",
    },
) {
    let response = await fetch(API_URL(endpoint), options);
    if (response.status === 401) {
        try {
            if (await getNewAccessToken()) {
                response = await fetch(API_URL(endpoint), options);
            }
        } catch (error) {
            await logout();
            throw new Error(error);
        }
    }
    return response;
}

let refreshInterval;

function startRefreshTimer() {
    const refreshFrequency = 25 * 60 * 1000; // 25 minutes

    if (refreshInterval) {
        clearInterval(refreshInterval);
    }

    refreshInterval = setInterval(async () => {
        try {
            await getNewAccessToken();
        } catch (error) {
            clearInterval(refreshInterval);
            window.location.href = "/";
            throw new Error(error);
        }
    }, refreshFrequency);
}

startRefreshTimer();

async function redirectNonPrivilegedUserFromAdminToNav() {
    if (window.location.pathname.includes("admin")) {
        const userInfo = getUserInfo();
        await userInfo.getRole();
        if (!userInfo.isActive || !userInfo.isAdmin) {
            window.location.href = "/nav";
        }
    }
}
