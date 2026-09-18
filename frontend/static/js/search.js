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
        editStructureRevisions: {},
        editLoads: {},
        // Editable search results support
        editableMusids: {},       // { muid: bool } — cached can_edit per muid
        originalValues: {},       // { "uid::muid": string } — snapshot on focus
        resultEntries: [],        // reactive array for x-for: [ { uid, segments: [ { muid, segment } ] } ]
        // Sorted field keys for UI rendering (uid excluded, rendered separately)
        sortedFieldKeys() {
            return Object.keys(this.fields)
                .filter(k => k !== 'uid')
                .sort((a, b) => this._fieldPriority(a) - this._fieldPriority(b));
        },
        _fieldPriority(key) {
            if (key.startsWith('translation')) return 0;
            if (key.startsWith('comment')) return 1;
            if (key.startsWith('root')) return 3;
            return 2; // tag, reference, variant, etc.
        },
        // Search-and-replace support
        replacementText: "",      // bound to the Replacement input
        replacedItems: {},        // { "uid::muid": true } — replaced but not yet submitted
        submittedItems: {},       // { "uid::muid": true } — successfully submitted
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
                throw error;
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
                const { results, detail } = await response.json();
                if (!response.ok) throw new Error(detail || "Search failed");
                if (!results) {
                    throw new Error("Invalid data format from the API");
                }
                this.results = results;
                this._buildResultEntries();
                await this._fetchEditPermissions(results);
                this.currentPage = this.page;
                this.page++;
                await this.prefetchNextPage();
            } catch (error) {
                throw error;
            }
        },
        async triggerSearch(event = null, { collapseOptions = undefined } = {}) {
            const shouldCollapseOptions = collapseOptions ?? event?.currentTarget?.dataset?.collapseOptions !== "false";
            await this.searchHandler(event);
            this.scrollTop("#resultsContainer");
            if (shouldCollapseOptions && Object.keys(this.results).length && "optionsExpanded" in this) {
                this.optionsExpanded = false;
            }
        },
        async prefetchNextPage() {
            const nextPageParams = new URLSearchParams(this.constructQueryParams());
            nextPageParams.set("page", this.page);
            const response = await requestWithTokenRetry(`search/?${nextPageParams.toString()}`);
            const { results, detail } = await response.json();
            if (!response.ok) throw new Error(detail || "Search failed");
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
                this._buildResultEntries();
                await this._fetchEditPermissions(this.results);
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
            this.editStructureRevisions = {};
            this.editLoads = {};
            this.originalValues = {};
            this.replacedItems = {};
            this.submittedItems = {};
            this.resultEntries = Object.entries(this.results).map(([uid, muidSegments]) => ({
                uid,
                segments: Object.entries(muidSegments).map(([muid, segment]) => ({
                    muid,
                    segment,
                })),
            }));
        },
        /** Load content and its structure version together before allowing edits. */
        async searchResultFocus(uid, muid) {
            if (muid.startsWith('root-')) return;
            const key = uid + '::' + muid;
            if (this.editStructureRevisions[key]) return;
            if (this.editLoads[key]) return this.editLoads[key];
            const loads = this.editLoads;
            loads[key] = this._loadEditSnapshot(uid, muid);
            try {
                await loads[key];
            } finally {
                delete loads[key];
            }
        },
        async _loadEditSnapshot(uid, muid) {
            const results = this.results;
            const prefix = this.getPrefixFromUid(uid);
            const response = await requestWithTokenRetry(`projects/${muid}/${prefix}/`);
            const snapshot = await response.json();
            if (!response.ok) throw new Error(snapshot.detail || 'Could not load the text for editing.');
            if (this.results !== results) throw new Error('Search results changed. Select the text again.');
            if (!snapshot.can_edit || !snapshot.structure_revision ||
                !Object.hasOwn(snapshot.data || {}, uid)) {
                throw new Error('This segment is no longer available for editing. Search again.');
            }
            const key = uid + '::' + muid;
            this.searchResultInput(uid, muid, snapshot.data[uid]);
            this.originalValues[key] = snapshot.data[uid];
            this.editStructureRevisions[key] = snapshot.structure_revision;
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
        /** Return HTML with search/replacement keywords wrapped in <mark> tags */
        getHighlightedSegment(segment, uid, muid) {
            if (!segment) return '';
            const key = uid + '::' + muid;
            let term;
            if (this.replacedItems[key]) {
                term = this.replacementText;
            } else {
                term = this.fields[muid];
                if (!term) {
                    for (const [k, v] of Object.entries(this.fields)) {
                        if (k !== 'uid' && v) { term = v; break; }
                    }
                }
            }
            const escaped = this._escapeHtml(segment);
            if (!term) return escaped;
            const escapedTerm = this._escapeHtml(term).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(escapedTerm, 'gi');
            return escaped.replace(regex, '<mark class="search__highlight">$&</mark>');
        },
        _escapeHtml(text) {
            const el = document.createElement('span');
            el.textContent = text;
            return el.innerHTML;
        },
        /** Called on Enter to save edited search result */
        async searchResultSave(uid, muid, currentValue) {
            const key = uid + '::' + muid;
            const original = this.originalValues[key];
            // Only save if actually modified
            if (currentValue === original) return;
            await this._saveSegment(uid, muid, currentValue);
        },
        async _saveSegment(uid, muid, currentValue) {
            const key = uid + '::' + muid;
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

                const revision = this.editStructureRevisions[key];
                if (!revision) throw new Error("Load the segment for editing before saving.");
                displayBadge(badgeId, BadgeStatus.PENDING);
                const response = await requestWithTokenRetry(`projects/${muid}/${prefix}/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json", "X-Structure-Revision": revision },
                    body: JSON.stringify({ [uid]: currentValue }),
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.detail || "Save failed");
                this.originalValues[key] = currentValue;
                displayBadge(badgeId, BadgeStatus.COMMITTED);
            } catch (error) {
                displayBadge(badgeId, BadgeStatus.ERROR);
                throw error;
            }
        },
        /** Check if a segment contains the search term that would be replaced */
        hasReplaceTerm(muid, segment) {
            let searchTerm = this.fields[muid];
            if (!searchTerm) {
                // Only allow fallback for the user's own translation muid
                const userMuid = new URLSearchParams(window.location.search).get('muid');
                if (muid === userMuid) {
                    for (const [key, value] of Object.entries(this.fields)) {
                        if (key !== 'uid' && value) {
                            searchTerm = value;
                            break;
                        }
                    }
                }
            }
            return !!(searchTerm && segment && segment.includes(searchTerm));
        },
        /** Replace search keyword in a single segment with replacementText */
        async replaceSegment(uid, muid, seg) {
            // Find the search term for this muid
            let searchTerm = this.fields[muid];
            if (!searchTerm) {
                // Fallback: use the first non-uid field that has a value
                for (const [key, value] of Object.entries(this.fields)) {
                    if (key !== 'uid' && value) {
                        searchTerm = value;
                        break;
                    }
                }
            }
            if (!searchTerm) return;

            await this.searchResultFocus(uid, muid);
            const newValue = seg.segment.replaceAll(searchTerm, this.replacementText);
            seg.segment = newValue;
            if (this.results[uid]) {
                this.results[uid][muid] = newValue;
            }
            this.replacedItems[uid + '::' + muid] = true;
        },
        /** Submit a single replaced segment to the server */
        async submitReplacement(uid, muid, currentValue) {
            await this._saveSegment(uid, muid, currentValue);
            this.submittedItems[uid + '::' + muid] = true;
        },
        scrollTop(selector) {
            document.querySelector(selector).scrollTop = 0;
        },
    };
};
