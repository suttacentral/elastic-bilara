function users() {
    return {
        isVisible: false,
        users: [],
        currentUserRole: "",
        searchQuery: '',
        filterStatus: '',
        filterRole: '',
        usersLoaded: false,
        operationMessage: '',
        operationError: '',
        async init() {
            const userInfo = getUserInfo();
            await userInfo.getRole();
            this.currentUserRole = userInfo.role;
            await this.getUsers();
        },
        canViewUserEmail() {
            return this.currentUserRole === ROLES.admin;
        },
        get filteredUsers() {
            const query = this.searchQuery.trim().toLowerCase();
            return this.users.filter(user => {
                if (this.filterStatus && String(user.is_active) !== this.filterStatus) return false;
                if (this.filterRole && user.role !== this.filterRole) return false;
                if (!query) return true;
                const fields = [user.username, String(user.github_id)];
                if (this.canViewUserEmail()) fields.push(user.email || '');
                return fields.some(value => value.toLowerCase().includes(query));
            });
        },
        get hasFilters() {
            return this.searchQuery !== '' || this.filterStatus !== '' || this.filterRole !== '';
        },
        clearFilters() {
            this.searchQuery = '';
            this.filterStatus = '';
            this.filterRole = '';
        },
        sortUsers() {
            this.users.sort((left, right) =>
                Number(left.is_active) - Number(right.is_active)
                || left.username.localeCompare(right.username, 'en', { sensitivity: 'base' })
                || left.id - right.id
            );
        },
        async getUsers() {
            try {
                const response = await requestWithTokenRetry("users/");
                if (!response.ok) {
                    throw new Error(`Unable to load users (HTTP ${response.status}).`);
                }
                const data = await response.json();
                const existingUsers = new Map(this.users.map(user => [user.id, user]));
                this.users = data.map(user => {
                    const existing = existingUsers.get(user.id);
                    const record = Object.assign(existing || {
                        showDetails: false,
                        isUpdatingStatus: false,
                        statusError: '',
                        isUpdatingRole: false,
                        roleError: '',
                    }, user);
                    if (!record.isUpdatingStatus) {
                        record.selectedStatus = String(record.is_active);
                    }
                    if (!record.isUpdatingRole) record.selectedRole = record.role;
                    return record;
                });
                this.sortUsers();
                this.usersLoaded = true;
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
                const activate = isActive ? "activate" : "deactivate";
                const response = await requestWithTokenRetry(`users/${githubId}/${activate}`, {
                    method: "PATCH",
                });
                if (!response.ok) {
                    throw new Error(`Unable to update account status (HTTP ${response.status}). Please try again.`);
                }
                const data = await response.json();
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async changeUserStatus(user) {
            if (user.isUpdatingStatus || user.isUpdatingRole) return;
            user.isUpdatingStatus = true;
            user.statusError = '';
            this.operationMessage = '';
            this.operationError = '';
            let saved = false;
            try {
                const updated = await this.activateUser(user.github_id, user.selectedStatus === 'true');
                Object.assign(user, updated);
                user.selectedStatus = String(user.is_active);
                user.selectedRole = user.role;
                this.sortUsers();
                saved = true;
                this.operationMessage = `${user.username}: account ${user.is_active ? 'activated' : 'deactivated'}.`;
                await redirectNonPrivilegedUserFromAdminToNav();
            } catch (error) {
                user.statusError = saved
                    ? 'Account status saved, but your access could not be refreshed. Please reload the page.'
                    : error.message;
                this.operationError = `${user.username}: ${user.statusError}`;
            } finally {
                user.selectedStatus = String(user.is_active);
                user.isUpdatingStatus = false;
            }
        },
        async setUsersRole(githubId, role) {
            try {
                const response = await requestWithTokenRetry(`users/${githubId}/role?role=${role}`, {
                    method: "PATCH",
                });
                if (!response.ok) {
                    throw new Error(`Unable to update user role (HTTP ${response.status}). Please try again.`);
                }
                const data = await response.json();
                return data;
            } catch (error) {
                throw new Error(error);
            }
        },
        async changeUserRole(user) {
            if (user.isUpdatingRole || user.isUpdatingStatus) return;
            user.isUpdatingRole = true;
            user.roleError = '';
            this.operationMessage = '';
            this.operationError = '';
            let saved = false;
            try {
                const updated = await this.setUsersRole(user.github_id, user.selectedRole);
                Object.assign(user, updated);
                user.selectedStatus = String(user.is_active);
                user.selectedRole = user.role;
                user.showDetails = false;
                this.sortUsers();
                saved = true;
                this.operationMessage = `${user.username}: role changed to ${user.role}.`;
                await redirectNonPrivilegedUserFromAdminToNav();
            } catch (error) {
                user.roleError = saved
                    ? 'User role saved, but your access could not be refreshed. Please reload the page.'
                    : error.message;
                this.operationError = `${user.username}: ${user.roleError}`;
            } finally {
                user.selectedRole = user.role;
                user.isUpdatingRole = false;
            }
        },
    };
}
