function users() {
    return {
        isVisible: false,
        users: [],
        async getUsers() {
            try {
                const response = await requestWithTokenRetry("users/");
                const data = await response.json();
                data["showDetails"] = false;
                this.users = data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async getUser(githubId) {
            try {
                const response = await requestWithTokenRetry(`users/${githubId}/`);
                const data = await response.json();
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async createUser(newUser) {
            const { githubId, username, email, avatarUrl, role } = newUser;
            for (const property in newUser) {
                if (newUser[property] === "" || newUser[property] === null || newUser[property] === undefined) {
                    throw new Error(`Missing required field: ${property}`);
                }
            }
            try {
                const response = await requestWithTokenRetry("users/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        github_id: githubId,
                        username,
                        email,
                        avatar_url: avatarUrl,
                        role,
                    }),
                    credentials: "include",
                });
                const data = await response.json();
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async deleteUser(githubId) {
            try {
                const response = await requestWithTokenRetry(`users/${githubId}/`, {
                    method: "DELETE",
                });
                const data = await response.json();
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async activateUser(githubId, isActive) {
            try {
                const activate = isActive.toLowerCase() === "true" ? "activate" : "deactivate";
                const response = await requestWithTokenRetry(`users/${githubId}/${activate}`, {
                    method: "PATCH",
                });
                const data = await response.json();
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async setUsersRole(githubId, role) {
            try {
                const response = await requestWithTokenRetry(`users/${githubId}/role?role=${role}`, {
                    method: "PATCH",
                });
                const data = await response.json();
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
    };
}
