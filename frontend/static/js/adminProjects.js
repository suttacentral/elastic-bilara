function projects() {
    return {
        isVisible: false,
        showAdd: false,
        showRemove: false,
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
        base: "root/",
        directories: [],
        files: [],
        users: [],
        user: null,
        languageCode: "",
        validLanguageCode: true,
        invalidData: false,
        created: { status: false, username: "", paths: [] },
        async init() {
            await this.getProjects(this.base);
            await this.getUsers();
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
        checkLanguageCode() {
            this.validLanguageCode = this.languageCode.length === 2 || this.languageCode.length === 3;
        },
        clearCreatedData() {
            this.created.status = false;
            this.created.username = "";
            this.created.paths = [];
        },
        async handleSubmit() {
            this.clearCreatedData();
            if (this.user === null || this.user === "") return (this.invalidData = true);
            if (!this.validLanguageCode) return (this.invalidData = true);
            this.loading = true;
            const params = new URLSearchParams({
                user_github_id: this.user,
                root_path: this.base,
                translation_language: this.languageCode,
            });
            const response = await requestWithTokenRetry(`projects/create/?${params.toString()}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
            });
            const { new_project_paths: createdPaths, user } = await response.json();
            this.loading = false;
            this.created.status = true;
            this.created.username = user;
            this.created.paths = createdPaths.flat();
            setTimeout(() => {
                this.clearCreatedData();
            }, 10000);
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
