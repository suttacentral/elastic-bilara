const search = () => {
    return {
        closed: true,
        projects: [],
        suggestions: [],
        projectQuery: "",
        selectedProjects: {},
        size: 100,
        page: 0,
        currentPage: 0,
        isNextPage: false,
        fields: {
            uid: "",
        },
        results: {},
        // Editable search results support
        editableMusids: {},       // { muid: bool } — cached can_edit per muid
        originalValues: {},       // { "uid::muid": string } — snapshot on focus
        resultEntries: [],        // reactive array for x-for: [ { uid, segments: [ { muid, segment } ] } ]
        async init() {
            try {
                const response = await requestWithTokenRetry(`projects/`);
                const { projects } = await response.json();
                if (!projects) {
                    throw new Error("Invalid data format from the API");
                }
                this.projects = projects;
                const params = new URLSearchParams(window.location.search);
                const muid = params.get("muid");
                const source = params.get("source");
                if (muid) {
                    this.toggleSelectedProjects(muid);
                }
                if (source) {
                    this.toggleSelectedProjects(source);
                }
            } catch (error) {
                throw new Error(error);
            }
        },
        updateSuggestions() {
            if (!this.projectQuery) {
                this.suggestions = [];
                return;
            }
            this.suggestions = this.projects.filter(project =>
                project.toLowerCase().startsWith(this.projectQuery.toLowerCase()),
            );
        },
        toggleSelectedProjects(project) {
            this.selectedProjects[project] = !this.selectedProjects[project];
            if (project in this.fields) {
                return delete this.fields[project];
            }
            this.fields[project] = "";
        },
        async searchHandler(event = null) {
            if (event !== null) {
                this.currentPage = 0;
                this.page = this.currentPage;
                this.isNextPage = false;
                this.results = {};
            }
            this.page = this.currentPage;
            this.prefetchedData = null;
            try {
                const params = this.constructQueryParams();
                const response = await requestWithTokenRetry(`search/?${params.toString()}`);
                const { results } = await response.json();
                if (!results) {
                    throw new Error("Invalid data format from the API");
                }
                this.results = results;
                this.originalValues = {};
                await this._fetchEditPermissions(results);
                this._buildResultEntries();
                this.currentPage = this.page;
                this.page++;
                await this.prefetchNextPage();
            } catch (error) {
                throw new Error(error);
            }
        },
        async prefetchNextPage() {
            const nextPageParams = new URLSearchParams(this.constructQueryParams());
            nextPageParams.set("page", this.page);
            const response = await requestWithTokenRetry(`search/?${nextPageParams.toString()}`);
            const { results } = await response.json();
            if (!results) {
                throw new Error("Invalid data format from the API");
            }
            this.prefetchedData = results;
            this.isNextPage = Object.keys(this.prefetchedData).length !== 0;
        },
        async nextHandler() {
            if (this.prefetchedData) {
                this.results = this.prefetchedData;
                this.prefetchedData = null;
                this.currentPage = this.page;
                this.page++;
                this.originalValues = {};
                await this._fetchEditPermissions(this.results);
                this._buildResultEntries();
                if (this.isNextPage) {
                    await this.prefetchNextPage();
                }
            } else {
                await this.searchHandler();
            }
        },
        async previousHandler() {
            if (this.currentPage > 0) {
                this.page = --this.currentPage;
                await this.searchHandler();
            }
        },
        constructQueryParams() {
            const params = new URLSearchParams();
            this.size = this.size <= 100 ? this.size : 10;
            params.set("size", this.size);
            params.set("page", this.currentPage);
            for (const [key, value] of Object.entries(this.fields)) {
                params.set(key, value);
            }
            return params;
        },
        // ---- Editable search results helpers ----
        /** Extract prefix from uid, e.g. "mn1:1.1" → "mn1", "an1.1:0.1" → "an1.1" */
        getPrefixFromUid(uid) {
            return uid.split(':')[0];
        },
        /** Check if a muid is editable (from cache). Requires admin role. */
        canEditMuid(muid, isAdmin) {
            return !!isAdmin && !!this.editableMusids[muid];
        },
        /** Fetch can_edit for all unique muids in results that haven't been checked yet */
        async _fetchEditPermissions(results) {
            const muids = new Set();
            for (const segments of Object.values(results)) {
                for (const muid of Object.keys(segments)) {
                    if (!(muid in this.editableMusids)) {
                        muids.add(muid);
                    }
                }
            }
            const promises = [...muids].map(async (muid) => {
                try {
                    const resp = await requestWithTokenRetry(`projects/${muid}/can-edit/`);
                    const data = await resp.json();
                    this.editableMusids[muid] = !!data.can_edit;
                } catch {
                    this.editableMusids[muid] = false;
                }
            });
            await Promise.all(promises);
        },
        /** Build the reactive resultEntries array from raw results dict */
        _buildResultEntries() {
            this.resultEntries = Object.entries(this.results).map(([uid, muidSegments]) => ({
                uid,
                segments: Object.entries(muidSegments).map(([muid, segment]) => ({
                    muid,
                    segment,
                })),
            }));
        },
        /** Called on textarea focus to snapshot original value */
        searchResultFocus(uid, muid) {
            const key = uid + '::' + muid;
            if (!(key in this.originalValues)) {
                this.originalValues[key] = this.results[uid]?.[muid] || '';
            }
        },
        /** Called on textarea input to update in-memory data */
        searchResultInput(uid, muid, value) {
            if (this.results[uid]) {
                this.results[uid][muid] = value;
            }
            // Also update the reactive entry
            const entry = this.resultEntries.find(e => e.uid === uid);
            if (entry) {
                const seg = entry.segments.find(s => s.muid === muid);
                if (seg) seg.segment = value;
            }
        },
        /** Called on Enter to save edited search result */
        async searchResultSave(uid, muid, currentValue) {
            const key = uid + '::' + muid;
            const original = this.originalValues[key];
            // Only save if actually modified
            if (currentValue === original) return;
            // Update original to new value so subsequent Enter without changes won't re-save
            this.originalValues[key] = currentValue;

            const prefix = this.getPrefixFromUid(uid);
            const badgeId = `search-badge-${muid}-${uid}`;

            try {
                // Ensure badge element exists
                const textarea = document.getElementById(`search-textarea-${muid}-${uid}`);
                if (textarea) {
                    let badge = document.getElementById(badgeId);
                    if (!badge) {
                        badge = document.createElement('sc-bilara-translation-edit-status');
                        badge.id = badgeId;
                        badge.className = 'search__results-status';
                        textarea.parentElement.appendChild(badge);
                    }
                }

                displayBadge(badgeId, BadgeStatus.PENDING);
                const response = await requestWithTokenRetry(`projects/${muid}/${prefix}/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ [uid]: currentValue }),
                });
                await response.json();
                displayBadge(badgeId, BadgeStatus.COMMITTED);
            } catch (error) {
                displayBadge(badgeId, BadgeStatus.ERROR);
                throw new Error(error);
            }
        },
        scrollTop(selector) {
            document.querySelector(selector).scrollTop = 0;
        },
    };
};
