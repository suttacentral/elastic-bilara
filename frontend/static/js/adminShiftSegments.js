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
        muid: null,
        prefix: null,
        segment: "",
        segmentIDs: [],
        selectedIDs: [],
        data: [],

        async init() {
            await this.getProjects(this.base);
            this.$watch("base", async () => {
                if (this.validateBase() && this.base.endsWith(".json")) {
                    this.loading = true;
                    if (!this.muid) this.muid = getMuid(this.base);
                    if (!this.prefix) this.prefix = getPrefix(this.base);
                    const response = await requestWithTokenRetry(`projects/${this.muid}/${this.prefix}/`);
                    const data = await response.json();
                    this.loading = false;
                    this.segmentIDs = Object.keys(data.data);
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
                this.selectedIDs.push(segment);
                this.segmentIDs = this.segmentIDs.filter(id => id !== segment);
                this.segment = "";
            }
        },
        removeSegment(segment) {
            this.segmentIDs.push(segment);
            this.segmentIDs.sort();
            this.selectedIDs = this.selectedIDs.filter(id => id !== segment);
        },
        async handleSubmit(dry) {
            this.loading = true;
            const params = new URLSearchParams({ exact: this.exact, dry_run: dry });
            console.log(params.toString());
            const response = await requestWithTokenRetry(`projects/${this.base}/?${params.toString()}`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(this.selectedIDs),
            });
            const data = await response.json();
            this.loading = false;
            this.data = data.results;
        },
        // getValue() {
        //     return translation.data[uid] || ""
        // }
        shouldDisplay(index, segmentID) {
            return this.data[index].data_after[segmentID] !== this.data[index].data_before[segmentID];
        },
    };
}
