function shift() {
    return {
        isVisible: false,
        loading: false,
        validPath: true,
        base: "",
        directories: [],
        files: [],
        exact: false,
        isRoot: false,
        segment: "",
        segmentIDs: [],
        selectedIDs: [],
        data: [],
        message: false,

        async init() {
            await this.getProjects(this.base);
            this.$watch("base", async () => {
                if (this.validateBase() && this.base.endsWith(".json")) {
                    this.loading = true;
                    const response = await requestWithTokenRetry(
                        `projects/${getMuid(this.base)}/${getPrefix(this.base)}/`,
                    );
                    const data = await response.json();
                    this.loading = false;
                    this.segmentIDs = Object.keys(data.data);
                    this.selectedIDs = [];
                }
            });
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
                this.segmentIDs = [];
                this.selectedIDs = [];
                this.data = [];
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
        addSegment(segment) {
            if (this.segmentIDs.includes(segment) && !this.selectedIDs.includes(segment)) {
                this.data = [];
                this.selectedIDs.push(segment);
                this.segmentIDs = this.segmentIDs.filter(id => id !== segment);
                this.segment = "";
            }
        },
        removeSegment(segment) {
            this.data = [];
            this.segmentIDs.push(segment);
            this.segmentIDs.sort();
            this.selectedIDs = this.selectedIDs.filter(id => id !== segment);
        },
        async handleSubmit(dry) {
            this.loading = true;
            const params = new URLSearchParams({ exact: this.exact, dry_run: dry });
            const response = await requestWithTokenRetry(`projects/${this.base}/?${params.toString()}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(this.selectedIDs),
            });
            const data = await response.json();
            this.loading = false;
            if (!dry && data.message) {
                await this.clearData();
                this.showMessage();
                return;
            }
            this.data = data.results;
        },
        shouldDisplay(index, segmentID) {
            if (!this.data.length) return false;
            return this.data[index].data_after[segmentID] !== this.data[index].data_before[segmentID];
        },
        async clearData() {
            this.base = "";
            await this.getProjects(this.base);
        },
        showMessage() {
            this.message = true;
            setTimeout(() => {
                this.message = false;
            }, 5000);
        },
    };
}

function adjust() {
    return {
        textareas: [],
        idGroups: [],
        init() {
            this.textareas = Array.from(document.querySelectorAll("textarea"));
            const idSet = new Set(this.textareas.map(textarea => textarea.id.split("before")[0].split("after")[0]));
            this.idGroups = Array.from(idSet);

            this.createObservers();
        },
        createObserver(idPrefix) {
            const observer = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        setMaxHeight([
                            document.querySelector(`textarea[id^='${idPrefix}before']`),
                            document.querySelector(`textarea[id^='${idPrefix}after']`),
                        ]);
                    }
                });
            });
            return observer;
        },
        createObservers() {
            for (let idGroup of this.idGroups) {
                const observer = this.createObserver(idGroup);
                const groupTextareas = this.textareas.filter(textarea => textarea.id.startsWith(idGroup));
                groupTextareas.forEach(textarea => {
                    textarea.style.overflow = "hidden";
                    observer.observe(textarea);
                });
            }
        },
    };
}
