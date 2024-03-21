function roots() {
    return {
        isVisible: false,
        directories: [],
        files: [],
        suggestions: [],
        base: "root/",
        isFile: false,
        rootData: [{ id: "", value: "" }],
        message: false,
        async getData(base) {
            try {
                const response = await requestWithTokenRetry(`directories/${this.checkIsFile() ? base + "/" : base}`);
                const data = await response.json();
                if (response.status === 404) {
                    throw new Error(data.detail);
                }
                this.directories = data.directories?.map(dir => data.base + dir);
                this.files = data.files?.map(file => data.base + file);
            } catch (error) {
                this.directories = [];
                this.files = [];
                this.handleMessage(
                    `You are going to create a new ${this.checkIsFile() ? "file" : "directory"}: ${base}`,
                    "bg-sky-100",
                    true,
                );
            }
        },
        checkIsFile() {
            this.isFile = this.base.endsWith(".json");
            return this.isFile;
        },
        showMessage() {
            const items = [...this.directories, ...this.files];
            if (this.base === "root/") {
                this.message = false;
                return;
            }
            items.forEach(item => {
                if (this.base.endsWith(item)) this.message = false;
            });
        },
        handleMessage(textContent, bgColor, toggle) {
            const p = document.getElementById("rootCreateMessage");
            p.textContent = textContent;
            p.className = `text-center mt-2 w-full p-2 rounded ${bgColor} ${
                bgColor === "bg-red-500" ? "text-white" : "text-black"
            }`;
            this.message = toggle;
        },
        async handleInput() {
            if (!this.base.startsWith("root/")) {
                this.base = "root/";
            }
            if (this.errorTimeoutId) this.cleanTimeout(this.errorTimeoutId);
            if (this.successTimeoutId) this.cleanTimeout(this.successTimeoutId);
            this.rootData = [{ id: "", value: "" }];
            this.checkIsFile();
            this.showMessage();
            if (this.base.endsWith("/") || this.base.endsWith(".json")) {
                await this.getData(this.base);
            }
        },
        async handleKeyUp(event) {
            if (event.key === "Backspace") {
                this.showMessage();
                if (this.base[this.base.length - 1] !== "/") {
                    await this.getData(this.base.slice(0, this.base.lastIndexOf("/") + 1));
                }
            }
        },
        addInputPair(index) {
            if (index === this.rootData.length - 1) this.rootData.push({ id: "", value: "" });
        },
        cleanTimeout(prop) {
            clearTimeout(this[prop]);
            this[prop] = null;
        },
        async create() {
            if (this.errorTimeoutId) this.cleanTimeout("errorTimeoutId");
            if (this.successTimeoutId) this.cleanTimeout("successTimeoutId");
            let body = null;
            if (this.checkIsFile()) {
                const data = this.rootData.reduce((obj, item) => {
                    if (item.id) {
                        obj[item.id] = item.value;
                    }
                    return obj;
                }, {});
                body = JSON.stringify(data);
            }

            const path = this.base.endsWith("/") ? this.base : this.base + "/";
            const options = {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            };
            if (body) options.body = body;
            this.handleLoading(true);
            const response = await requestWithTokenRetry(`projects/${path}`, options);
            this.handleLoading(false);
            const data = await response.json();
            if (!response.ok) {
                this.handleMessage(data.detail, "bg-red-500", true);
                this.errorTimeoutId = setTimeout(() => {
                    this.message = false;
                }, 15000);
            } else {
                this.handleMessage(data.detail, "bg-green-50", true);
                this.successTimeoutId = setTimeout(() => {
                    this.message = false;
                }, 5000);
                this.cleanData();
            }
        },
        handleLoading(toggle) {
            const container = document.getElementById("loadingContainer");
            const classes = ["loading"];
            if (toggle) for (const className of classes) container.classList.add(className);
            else for (const className of classes) container.classList.remove(className);
        },
        cleanData() {
            this.base = "root/";
            this.isFile = false;
            this.rootData = [{ id: "", value: "" }];
            this.directories = [];
            this.files = [];
        },
    };
}
