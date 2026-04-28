function projects() {
    return {
        isVisible: false,
        showAdd: false,
        showRemove: false,
        showFileManager: false,
        toggleAdd() {
            if (this.showAdd) {
                this.showAdd = false;
                this.showRemove = false;
            } else {
                this.showAdd = true;
                this.showRemove = false;
            }
        },
        toggleRemove() {
            if (this.showRemove) {
                this.showRemove = false;
                this.showAdd = false;
            } else {
                this.showRemove = true;
                this.showAdd = false;
            }
        },
    };
}

function addNewProject() {
    return {
        loading: false,
        progress: { current: 0, total: 0, phase: 'creating' },
        elapsedSeconds: 0,
        _elapsedTimer: null,
        errorMessage: '',
        base: "root/",
        directories: [],
        files: [],
        users: [],
        languages: {},
        user: null,
        languageCode: "",
        projectName: "",
        validLanguageCode: true,
        invalidData: false,
        created: { status: false, username: "", paths: [] },
        async init() {
            await this.getProjects(this.base);
            await this.getUsers();
            await this.getLanguages();
        },
        async getProjects(base) {
            try {
                const response = await requestWithTokenRetry(
                    `directories/${this.base.endsWith(".json") ? base + "/" : base}`,
                );
                const data = await response.json();
                if (response.status === 404) {
                    throw new Error(data.detail);
                }
                this.directories = data.directories?.map(dir => data.base + dir);
                this.files = data.files?.map(file => data.base + file);
            } catch (error) {
                this.directories = [];
                this.files = [];
            }
        },
        async handleInput() {
            this.clearCreatedData();
            if (!this.base.startsWith("root/")) {
                this.base = "root/";
            }
            if (this.base.endsWith("/") || this.base.endsWith(".json")) {
                await this.getProjects(this.base);
            }
        },
        async handleKeyUp(event) {
            this.clearCreatedData();
            if (event.key === "Backspace") {
                if (this.base[this.base.length - 1] !== "/") {
                    await this.getProjects(this.base.slice(0, this.base.lastIndexOf("/") + 1));
                }
            }
        },
        async getUsers() {
            const response = await requestWithTokenRetry("users/");
            const data = await response.json();
            this.users = data;
        },
        async getLanguages() {
            try {
                const response = await requestWithTokenRetry("languages/");
                const data = await response.json();
                this.languages = data;
            } catch (error) {
                console.error("Failed to load languages:", error);
                this.languages = {};
            }
        },
        checkLanguageCode() {
            this.validLanguageCode = this.languageCode && this.languageCode.length > 0;
        },
        clearCreatedData() {
            this.created.status = false;
            this.created.username = "";
            this.created.paths = [];
        },
        async handleSubmit() {
            this.clearCreatedData();
            this.invalidData = false;
            this.errorMessage = '';
            if (this.user === null || this.user === "") return (this.invalidData = true);
            this.checkLanguageCode();
            if (!this.validLanguageCode) return (this.invalidData = true);
            this.loading = true;
            this.progress = { current: 0, total: 0, phase: 'creating' };
            this.elapsedSeconds = 0;
            clearInterval(this._elapsedTimer);
            this._elapsedTimer = setInterval(() => { this.elapsedSeconds++; }, 1000);
            const params = new URLSearchParams({
                user_github_id: this.user,
                root_path: this.base,
                translation_language: this.languageCode,
            });
            try {
                const response = await requestWithTokenRetry(`projects/create/?${params.toString()}`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                });
                if (!response.ok) {
                    const errData = await response.json().catch(() => ({}));
                    throw new Error(errData.detail || `API error (${response.status})`);
                }
                const { task_id, user } = await response.json();

                // Poll task status until completion
                const taskResult = await this.pollTask(task_id);

                if (taskResult && taskResult.status === "success") {
                    // Also write project entry to _project-v2.json
                    const rootPathClean = this.base.replace(/\/$/, '');
                    const rootParts = rootPathClean.split('/');
                    const rootLang = rootParts.length >= 3 ? rootParts[2] : rootParts[1] || '';
                    const lastPart = rootParts[rootParts.length - 1] || '';
                    const selectedUser = this.users.find(u => String(u.github_id) === String(this.user));
                    const authorId = selectedUser ? selectedUser.username : '';
                    const projectEntry = {
                        project_uid: `${this.languageCode}_${rootLang}_translation_${authorId}`,
                        name: this.projectName,
                        root_path: rootPathClean,
                        translation_path: `translation/${this.languageCode}/${authorId}/${lastPart}`,
                        translation_muids: `translation-${this.languageCode}-${authorId}`,
                        creator_github_handle: authorId,
                    };
                    try {
                        await requestWithTokenRetry('projects/project-entries/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(projectEntry),
                        });
                    } catch (e) {
                        console.error('Failed to create project entry:', e);
                    }

                    this.created.status = true;
                    this.created.username = user;
                    this.created.paths = taskResult.new_project_paths || [];
                } else {
                    this.errorMessage = taskResult?.error || (taskResult?.status === 'error' ? 'Project creation task failed.' : 'Project creation failed.');
                    this.invalidData = true;
                }
            } catch (error) {
                console.error("Failed to create project:", error);
                this.errorMessage = error.message || 'Project creation failed.';
                this.invalidData = true;
            } finally {
                clearInterval(this._elapsedTimer);
                this._elapsedTimer = null;
                this.loading = false;
            }
        },
        async pollTask(taskId) {
            const POLL_INTERVAL = 2000;
            const MAX_POLLS = 900; // 900 polls × 2s = 1800s (30 minutes)
            for (let i = 0; i < MAX_POLLS; i++) {
                try {
                    const response = await requestWithTokenRetry(`tasks/${taskId}/`);
                    const data = await response.json();
                    if (data.status === "SUCCESS") {
                        this.progress = { current: 1, total: 1, phase: 'done' };
                        return data.result;
                    } else if (data.status === "FAILURE") {
                        return { status: 'error', error: data.error || 'Project creation task failed.' };
                    } else if (data.status === "PROGRESS" && data.info) {
                        this.progress = {
                            current: data.info.current || 0,
                            total: data.info.total || 0,
                            phase: data.info.phase || 'creating',
                        };
                    }
                } catch (pollError) {
                    console.warn("Poll request failed, retrying:", pollError);
                }
                await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
            }
            return { status: 'error', error: 'Project creation timed out.' };
        },
    };
}

function removeProject() {
    return {
        base: "",
        validPath: true,
        directories: [],
        files: [],
        isRoot: false,
        message: false,
        loading: false,
        data: [],
        async init() {
            await this.getProjects(this.base);
        },
        async getProjects(base) {
            this.loading = true;
            try {
                const response = await requestWithTokenRetry(
                    `directories/${this.base.endsWith(".json") ? base + "/" : base}`,
                );
                const data = await response.json();
                if (response.status === 404) {
                    throw new Error(data.detail);
                }
                this.directories = data.directories?.map(dir => (data.base || "") + dir);
                this.files = data.files?.map(file => (data.base || "") + file);
            } catch (error) {
                this.directories = [];
                this.files = [];
            }
            this.loading = false;
        },
        async handleInput() {
            if (this.base.endsWith("/")) {
                await this.getProjects(this.base);
            }
            this.validPath = this.validateBase();
        },
        async handleKeyUp(event) {
            if (event.key === "Backspace") {
                if (this.base[this.base.length - 1] !== "/") {
                    await this.getProjects(this.base.slice(0, this.base.lastIndexOf("/") + 1));
                    this.validateBase();
                }
            }
        },
        validateBase() {
            return (
                this.files?.some(file => file.includes(this.base)) ||
                this.directories?.some(dir => dir.includes(this.base))
            );
        },
        async handleSubmit(dry) {
            if (this.base === "") return;
            this.loading = true;
            this.message = false;
            if (!dry) {
                this.loading = false;
                this.data = [];
                this.showMessage();
            }
            const params = new URLSearchParams({ dry_run: dry });
            const response = await requestWithTokenRetry(`directories/${this.base}/?${params.toString()}`, {
                method: "DELETE",
                credentials: "include",
            });
            if (!dry) {
                this.base = "";
                await this.getProjects(this.base);
                return;
            }
            const data = await response.json();
            this.data = data.results;
            this.loading = false;
        },
        showMessage() {
            this.message = true;
            setTimeout(() => {
                this.message = false;
            }, 5000);
        },
    };
}

function projectsListManager() {
    return {
        entries: [],
        loading: false,
        view: 'list',
        editingEntry: null,
        searchQuery: '',
        filterLang: '',
        sortField: '',
        sortAsc: true,
        form: {
            project_uid: '',
            name: '',
            root_path: '',
            translation_path: '',
            translation_muids: '',
            creator_github_handle: '',
        },
        formErrors: {},
        saving: false,
        publishing: false,
        toast: { show: false, message: '', type: 'success' },

        async init() {
            await this.loadEntries();
        },

        async loadEntries() {
            this.loading = true;
            try {
                const res = await requestWithTokenRetry('projects/project-entries/');
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Failed to load');
                this.entries = data;
            } catch (e) {
                this.showToast('Failed to load project entries: ' + e.message, 'error');
            } finally {
                this.loading = false;
            }
        },

        get filteredEntries() {
            let list = [...this.entries];
            if (this.searchQuery) {
                const q = this.searchQuery.toLowerCase();
                list = list.filter(e =>
                    String(e.project_uid || '').toLowerCase().includes(q) ||
                    String(e.name || '').toLowerCase().includes(q) ||
                    String(e.creator_github_handle || '').toLowerCase().includes(q) ||
                    String(e.translation_path || '').toLowerCase().includes(q)
                );
            }
            if (this.filterLang) {
                list = list.filter(e => {
                    const lang = e.translation_muids ? e.translation_muids.split('-')[1] || '' : '';
                    return lang === this.filterLang;
                });
            }
            if (this.sortField) {
                list.sort((a, b) => {
                    let va = a[this.sortField] ?? '';
                    let vb = b[this.sortField] ?? '';
                    if (typeof va === 'string') va = va.toLowerCase();
                    if (typeof vb === 'string') vb = vb.toLowerCase();
                    if (va < vb) return this.sortAsc ? -1 : 1;
                    if (va > vb) return this.sortAsc ? 1 : -1;
                    return 0;
                });
            }
            return list;
        },

        get uniqueLanguages() {
            const langs = new Set();
            this.entries.forEach(e => {
                if (e.translation_muids) {
                    const parts = e.translation_muids.split('-');
                    if (parts[1]) langs.add(parts[1]);
                }
            });
            return [...langs].sort();
        },

        toggleSort(field) {
            if (this.sortField === field) {
                this.sortAsc = !this.sortAsc;
            } else {
                this.sortField = field;
                this.sortAsc = true;
            }
        },

        sortIcon(field) {
            if (this.sortField !== field) return 'bi-arrow-down-up';
            return this.sortAsc ? 'bi-sort-up' : 'bi-sort-down';
        },

        showCreateForm() {
            this.editingEntry = null;
            this.formErrors = {};
            this.resetForm();
            this.view = 'form';
        },

        showEditForm(entry) {
            this.editingEntry = entry.project_uid;
            this.formErrors = {};
            this.form = {
                project_uid: entry.project_uid || '',
                name: entry.name || '',
                root_path: entry.root_path || '',
                translation_path: entry.translation_path || '',
                translation_muids: entry.translation_muids || '',
                creator_github_handle: entry.creator_github_handle || '',
            };
            this.view = 'form';
        },

        resetForm() {
            this.form = {
                project_uid: '',
                name: '',
                root_path: '',
                translation_path: '',
                translation_muids: '',
                creator_github_handle: '',
            };
        },

        validateForm() {
            this.formErrors = {};
            if (!this.form.project_uid.trim()) {
                this.formErrors.project_uid = 'Project UID is required';
            }
            return Object.keys(this.formErrors).length === 0;
        },

        async submitForm() {
            if (!this.validateForm()) return;
            this.saving = true;
            try {
                const isEdit = !!this.editingEntry;
                const url = isEdit
                    ? `projects/project-entries/${this.editingEntry}`
                    : 'projects/project-entries/';
                const method = isEdit ? 'PUT' : 'POST';
                const res = await requestWithTokenRetry(url, {
                    method,
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify(this.form),
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Save failed');
                this.showToast(
                    isEdit ? 'Project entry updated' : 'Project entry created',
                    'success'
                );
                await this.loadEntries();
                this.view = 'list';
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            } finally {
                this.saving = false;
            }
        },

        async deleteEntry(projectUid) {
            if (!confirm(`Delete ${projectUid}? This cannot be undone.`)) return;
            try {
                const res = await requestWithTokenRetry(`projects/project-entries/${projectUid}`, {
                    method: 'DELETE',
                    credentials: 'include',
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Delete failed');
                this.showToast(`${projectUid} deleted`, 'success');
                await this.loadEntries();
            } catch (e) {
                this.showToast('Error: ' + e.message, 'error');
            }
        },

        cancelForm() {
            this.view = 'list';
            this.editingEntry = null;
        },

        showToast(message, type = 'success') {
            this.toast = { show: true, message, type };
            setTimeout(() => { this.toast.show = false; }, 4000);
        },

        async publishToGitHub() {
            if (!confirm('Commit and push project metadata to GitHub?')) return;
            this.publishing = true;
            try {
                const res = await requestWithTokenRetry('projects/project-entries/publish/', {
                    method: 'POST',
                    credentials: 'include',
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || 'Publish failed');
                this.showToast('Published to GitHub (task: ' + data.task_id + ')', 'success');
            } catch (e) {
                this.showToast('Publish error: ' + e.message, 'error');
            } finally {
                this.publishing = false;
            }
        },
    };
}
