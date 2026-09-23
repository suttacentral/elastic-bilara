const HTML_PREVIEW_PREFERENCE_KEY = 'bilara:translation:html-preview-enabled';

function setTranslationDocumentTitle(uid) {
    document.title = uid ? `Bilara - ${uid}` : 'Bilara';
}

function getStoredHtmlPreviewEnabled() {
    return localStorage.getItem(HTML_PREVIEW_PREFERENCE_KEY) === 'true';
}

function setStoredHtmlPreviewEnabled(enabled) {
    localStorage.setItem(HTML_PREVIEW_PREFERENCE_KEY, String(!!enabled));
}

function shouldRenderHtmlPreview(muid, enabled) {
    return !!enabled && typeof muid === 'string' && muid.startsWith('root-');
}

function sanitizeBilaraHtml(value) {
    if (!window.DOMPurify || typeof window.DOMPurify.sanitize !== 'function') {
        throw new Error('DOMPurify is required for HTML preview');
    }

    return window.DOMPurify.sanitize(String(value ?? ''), {
        ALLOWED_TAGS: [
            'a', 'abbr', 'b', 'br', 'cite', 'code', 'del', 'em', 'i', 'ins',
            'kbd', 'mark', 'q', 's', 'samp', 'small', 'span', 'strong', 'sub',
            'sup', 'time', 'u', 'var',
        ],
        ALLOWED_ATTR: ['datetime', 'dir', 'href', 'lang', 'title'],
        ALLOWED_URI_REGEXP: /^(?:https?:|#)/i,
        ALLOW_ARIA_ATTR: false,
        ALLOW_DATA_ATTR: false,
    });
}

function fetchTranslation() {
    const REMARKS_PREFIX = "remarks:";
    return {
        translations: [],
        loading: true,
        loadError: '',
        relatedProjects: [],
        remarkUsers: [],
        currentUserGithubId: null,
        currentUsername: null,
        currentUserRole: null,
        htmlProjectName: '',
        htmlProject: null,
        htmlDraftOverrides: {},
        htmlValidation: {
            status: 'idle',
            errors: [],
            warnings: [],
            checkedSegments: 0,
        },
        tagProjectName: '',
        tagProject: null,
        availableTags: [],
        hyphenatedPrefixRanges: [],
        progressState: {
            translationMuid: null,
            translated: 0,
            total: 0,
        },
        originalTranslations: null,
        structureDraft: null,
        structureDraftError: "",
        structurePreviewLoading: false,
        relatedProjectLoads: 0,
        columnOrderSaveErrorShown: false,
        relatedProjectsLocked() {
            return this.structurePreviewLoading || !!this.structureDraft;
        },
        dirtySegments: {},
        structureRevisions: {},
        splitter_uid: null,
        merger_uid: null,
        mergee_uid: null,
        affectedFiles: [],
        affectedPrefix: '',
        isRemarkProject(key) {
            return key && key.startsWith(REMARKS_PREFIX);
        },
        getRemarkGithubId(key) {
            return key ? parseInt(key.substring(REMARKS_PREFIX.length), 10) : null;
        },
        makeRemarkKey(githubId) {
            return REMARKS_PREFIX + githubId;
        },
        getRemarkLabel(key) {
            const gid = this.getRemarkGithubId(key);
            if (gid === this.currentUserGithubId) return 'My Remarks';
            const user = this.remarkUsers.find(u => u.github_id === gid);
            return user ? `Remarks (${user.username})` : `Remarks (${gid})`;
        },
        getProjectIcon(key) {
            if (this.isRemarkProject(key)) return 'bi-chat-left-text';
            if (key.startsWith('comment')) return 'bi-chat-dots';
            if (key.startsWith('reference')) return 'bi-link-45deg';
            if (key.startsWith('tag')) return 'bi-tag';
            if (key.startsWith('translation')) return 'bi-translate';
            if (key.startsWith('variant')) return 'bi-diagram-2';
            return 'bi-file-text';
        },
        getProjectType(key) {
            if (!key) return 'other';
            if (this.isRemarkProject(key)) return 'remarks';
            if (key.startsWith('translation')) return 'translation';
            if (key.startsWith('variant')) return 'variant';
            if (key.startsWith('comment')) return 'comment';
            if (key.startsWith('reference')) return 'reference';
            if (key.startsWith('tag')) return 'tag';
            return 'other';
        },
        getMuidOwner(key) {
            const ownedTypes = new Set(['translation', 'comment']);
            const type = this.getProjectType(key);
            if (!ownedTypes.has(type)) return null;
            const parts = key.split('-');
            if (parts.length < 3) return null;
            return parts.slice(2).join('-').toLowerCase();
        },
        getTranslationOwner(key) {
            if (!key || !key.startsWith('translation-')) return null;
            return this.getMuidOwner(key);
        },
        isCurrentUserMuid(key) {
            const username = (this.currentUsername || '').toLowerCase();
            return !!username && this.getMuidOwner(key) === username;
        },
        isCurrentUserTranslation(key) {
            return !!key && key.startsWith('translation-') && this.isCurrentUserMuid(key);
        },
        invalidateHtmlValidation() {
            if (this.htmlValidation.status !== 'checking') {
                this.htmlValidation.status = 'idle';
            }
        },
        async validateHtmlProject() {
            if (!this.htmlProjectName || this.htmlValidation.status === 'checking') return;

            this.htmlValidation.status = 'checking';
            try {
                const response = await requestWithTokenRetry(
                    `projects/${this.htmlProjectName}/${this.prefix}/html-validation/`,
                    {
                        credentials: 'include',
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(this.structureDraft
                            ? {segments: this.translations.find(t => t.muid === this.htmlProjectName).data}
                            : { overrides: this.htmlDraftOverrides }),
                    },
                );
                if (!response.ok) {
                    const body = await response.json().catch(() => null);
                    throw new Error(body?.detail ?? `Server error (${response.status})`);
                }

                const result = await response.json();
                this.htmlValidation = {
                    status: result.valid ? 'valid' : 'invalid',
                    errors: result.errors || [],
                    warnings: result.warnings || [],
                    checkedSegments: result.checked_segments || 0,
                };

                const dialog = document.querySelector('.dialog-html-validation');
                if (!result.valid || this.htmlValidation.warnings.length > 0) {
                    dialog?.show?.();
                } else {
                    document.querySelector('sc-bilara-toast')?.show(
                        `HTML is valid (${this.htmlValidation.checkedSegments} segments checked).`,
                        'success',
                    );
                }
            } catch (error) {
                this.htmlValidation = {
                    status: 'error',
                    errors: [],
                    warnings: [],
                    checkedSegments: 0,
                };
                document.querySelector('sc-bilara-toast')?.show(
                    `HTML validation failed: ${error.message}`,
                    'danger',
                    5000,
                );
            }
        },
        focusHtmlValidationIssue(issue) {
            document.querySelector('.dialog-html-validation')?.hide?.();
            window.dispatchEvent(new CustomEvent('show-html-source'));
            requestAnimationFrame(() => {
                const textarea = document.getElementById(
                    `translation-textarea-${this.htmlProjectName}-${issue.uid}`,
                );
                if (!textarea) return;
                textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
                textarea.focus();
                const offset = Math.max(0, Math.min(Number(issue.offset) || 0, textarea.value.length));
                textarea.setSelectionRange(offset, offset);
            });
        },
        async init() {
            this.loading = true;
            this.loadError = '';
            try {
                await this.initialize();
            } catch (error) {
                this.loadError = error.message || 'Could not load this text. Retry loading.';
            } finally {
                this.loading = false;
            }
        },
        async initialize() {
            const params = new URLSearchParams(window.location.search);
            this.prefix = params.get("prefix");
            setTranslationDocumentTitle(this.prefix);
            const source = await this.resolveSource(params);
            const muid = params.get("muid");

            this.muid = muid;
            this.sourceMuid = source;
            await this.resumeStructureOperation();

            const currentUserPromise = this.loadCurrentUserForTranslation();
            await this.loadHyphenatedPrefixRanges();

            // Try loading source with original prefix; fall back to hyphenated range on failure
            try {
                await this.findOrCreateObject(source, this.prefix, true);
            } catch (error) {
                const fallbackPrefix = this.getFallbackPrefix(this.prefix);
                if (fallbackPrefix) {
                    console.info(`Prefix "${this.prefix}" not found, falling back to range prefix "${fallbackPrefix}"`);
                    this.prefix = fallbackPrefix;
                    setTranslationDocumentTitle(this.prefix);
                    await this.findOrCreateObject(source, this.prefix, true);
                    // Update URL to reflect the resolved prefix
                    const url = new URL(window.location);
                    url.searchParams.set("prefix", this.prefix);
                    window.history.replaceState(null, "", url);
                } else {
                    throw error;
                }
            }

            const remarksMuid = this.sourceMuid || this.muid;
            const [targetProject, projects, remarkUsers] = await Promise.all([
                muid ? this.createObject(muid, this.prefix) : Promise.resolve(null),
                this.fetchRelatedProjects(this.prefix),
                this.fetchRemarkUsers(remarksMuid, this.prefix),
                this.loadAvailableTags(),
                currentUserPromise,
            ]);

            if (targetProject && !this.translations.some(item => item.muid === targetProject.muid)) {
                this.translations.push(targetProject);
            }
            this.remarkUsers = remarkUsers;

            this.htmlProjectName = projects.find(project => project.includes('html'));
            this.tagProjectName = projects.find(project => project.startsWith('tag'));

            const canViewHtmlProject = ['administrator', 'superuser'].includes(this.currentUserRole);
            this.relatedProjects = projects.filter(project =>
                project !== muid &&
                project !== source &&
                (project !== this.htmlProjectName || canViewHtmlProject)
            );

            // Build remark projects per user
            const myRemarkKey = this.currentUserGithubId ? this.makeRemarkKey(this.currentUserGithubId) : null;

            // Always include current user's remark in related projects
            if (myRemarkKey && !this.relatedProjects.includes(myRemarkKey)) {
                this.relatedProjects.push(myRemarkKey);
            }
            // Add other users who have remarks
            for (const u of this.remarkUsers) {
                const key = this.makeRemarkKey(u.github_id);
                if (!this.relatedProjects.includes(key)) {
                    this.relatedProjects.push(key);
                }
            }

            // Sort relatedProjects by type
            const typeOrder = { translation: 0, variant: 1, comment: 2, reference: 3, tag: 4, other: 5, remarks: 6 };
            this.relatedProjects.sort((a, b) => {
                const ta = typeOrder[this.getProjectType(a)] ?? 5;
                const tb = typeOrder[this.getProjectType(b)] ?? 5;
                if (ta !== tb) return ta - tb;
                return a.localeCompare(b);
            });

            // Restore previously saved related project selections
            const savedRelated = this.getSavedRelatedProjects();
            const storageKey = `relatedProjects_${this.muid}`;
            const hasPersistedState = localStorage.getItem(storageKey) !== null;

            // Auto-load current user's remarks only if:
            // 1. No persisted state exists (first time), default to showing
            // 2. Persisted state includes myRemarkKey, user chose to keep it
            const shouldAutoLoadRemarks = myRemarkKey && (!hasPersistedState || savedRelated.includes(myRemarkKey));
            const ownRemarkPromise = shouldAutoLoadRemarks
                ? this.createObject(myRemarkKey, this.prefix).catch(error => {
                    console.error('Failed to auto-load own remarks:', error);
                    return null;
                })
                : Promise.resolve(null);
            const [htmlProject, ownRemark] = await Promise.all([
                this.htmlProjectName
                    ? this.createObject(this.htmlProjectName, this.prefix)
                    : Promise.resolve(null),
                ownRemarkPromise,
            ]);

            this.htmlProject = htmlProject;
            if (ownRemark && !this.translations.some(item => item.muid === ownRemark.muid)) {
                this.translations.push(ownRemark);
            }
            // On first visit, seed localStorage so toggle can track removals
            if (ownRemark && !hasPersistedState) {
                this.saveRelatedProjects([myRemarkKey]);
            }

            const validSaved = savedRelated.filter(p => this.relatedProjects.includes(p));
            const loadedSaved = await this.restoreRelatedProjectsInOrder(validSaved);
            // Build the list of all loaded projects for the restore event
            const allLoaded = [...loadedSaved];
            if (shouldAutoLoadRemarks && myRemarkKey && !allLoaded.includes(myRemarkKey)) {
                allLoaded.push(myRemarkKey);
            }
            window.dispatchEvent(new CustomEvent('restore-related-projects', { detail: { projects: allLoaded } }));

            this.applySavedColumnOrder();

            this.updateProgress();
        },
        getColumnOrderKey() {
            const scope = this.muid || `source:${this.sourceMuid}`;
            return `bilara:col-order:v2:${scope}`;
        },
        getSavedColumnOrder() {
            try {
                const stored = localStorage.getItem(this.getColumnOrderKey());
                // Only migrate this sutta's old preference when no project preference exists.
                const legacyKey = `bilara:col-order:${this.prefix}:${this.sourceMuid}:${this.muid}`;
                const saved = JSON.parse(stored === null ? localStorage.getItem(legacyKey) : stored);
                if (!Array.isArray(saved) || !saved.every(muid => typeof muid === 'string')) return [];
                const order = [...new Set(saved)];
                if (stored === null) this.persistColumnOrder(order);
                return order;
            } catch (error) {
                return [];
            }
        },
        applySavedColumnOrder() {
            const saved = this.getSavedColumnOrder();
            const remaining = new Map(this.translations.map(item => [item.muid, item]));
            const reordered = [];
            for (const muid of saved) {
                if (remaining.has(muid)) {
                    reordered.push(remaining.get(muid));
                    remaining.delete(muid);
                }
            }
            reordered.push(...remaining.values());
            this.translations.splice(0, this.translations.length, ...reordered);
        },
        saveColumnOrder() {
            const visible = this.translations.map(item => item.muid);
            const visibleSet = new Set(visible);
            const complete = [...new Set([...this.getSavedColumnOrder(), ...visible])];
            let index = 0;
            // Keep unavailable/unselected columns in their slots while reordering visible ones.
            const order = complete.map(muid => visibleSet.has(muid) ? visible[index++] : muid);
            this.persistColumnOrder(order);
        },
        persistColumnOrder(order) {
            try {
                localStorage.setItem(this.getColumnOrderKey(), JSON.stringify(order));
            } catch (error) {
                console.warn('Failed to persist column order to localStorage.', error);
                if (!this.columnOrderSaveErrorShown) {
                    const toast = document.querySelector('sc-bilara-toast');
                    if (toast) {
                        toast.show('Column order could not be saved in this browser.', 'warning');
                    }
                    this.columnOrderSaveErrorShown = true;
                }
            }
        },
        async loadCurrentUserForTranslation() {
            try {
                const userData = await getCurrentUser();
                this.currentUserGithubId = userData.github_id || null;
                this.currentUsername = userData.username || null;
                this.currentUserRole = userData.role || null;
                return userData;
            } catch (e) {
                console.error('Failed to fetch current user info:', e);
            }
            return null;
        },
        async resolveSource(params) {
            const existingSource = params.get("source");
            if (existingSource) {
                return existingSource;
            }

            const path = params.get("path");
            if (!path) {
                throw new Error("Translation URL is missing both source and path");
            }

            const response = await requestWithTokenRetry(`projects/${path}/source/`);
            if (!response.ok) {
                throw new Error(`Unable to resolve source for project path: ${path}`);
            }

            const { muid: source } = await response.json();
            if (!source) {
                throw new Error(`Source response is missing muid for project path: ${path}`);
            }

            if (params.get("muid") === source) {
                params.set("muid", "");
            }
            params.set("source", source);
            params.delete("path");

            const canonicalUrl = new URL(window.location.href);
            canonicalUrl.search = params.toString();
            window.history.replaceState(window.history.state, "", canonicalUrl);
            return source;
        },
        async loadHyphenatedPrefixRanges() {
            try {
                const response = await fetch("/static/merged_sutta_ranges.json", {
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    this.hyphenatedPrefixRanges = [];
                    return;
                }
                const ranges = await response.json();
                this.hyphenatedPrefixRanges = Array.isArray(ranges) ? ranges : [];
            } catch (error) {
                this.hyphenatedPrefixRanges = [];
            }
        },
        parseHyphenatedPrefixRange(rangePrefix) {
            const match = /^(.+?)(\d+)-(\d+)$/.exec(rangePrefix);
            if (!match) {
                return null;
            }
            const start = Number(match[2]);
            const end = Number(match[3]);
            if (Number.isNaN(start) || Number.isNaN(end) || start > end) {
                return null;
            }
            return {
                original: rangePrefix,
                base: match[1],
                start,
                end,
                width: end - start,
            };
        },
        getFallbackPrefix(prefix) {
            if (!prefix || this.parseHyphenatedPrefixRange(prefix)) {
                return null;
            }

            const inputMatch = /^(.+?)(\d+)$/.exec(prefix);
            if (!inputMatch) {
                return null;
            }

            const inputBase = inputMatch[1];
            const inputNumber = Number(inputMatch[2]);
            if (Number.isNaN(inputNumber)) {
                return null;
            }

            let bestMatch = null;
            for (const rangePrefix of this.hyphenatedPrefixRanges) {
                const parsedRange = this.parseHyphenatedPrefixRange(rangePrefix);
                if (!parsedRange) {
                    continue;
                }
                if (parsedRange.base !== inputBase) {
                    continue;
                }
                if (inputNumber < parsedRange.start || inputNumber > parsedRange.end) {
                    continue;
                }
                if (!bestMatch || parsedRange.width < bestMatch.width) {
                    bestMatch = parsedRange;
                }
            }

            return bestMatch ? bestMatch.original : null;
        },

        getValue(translation, uid) {
            return translation.data[uid] || "";
        },
        setValue(translation, uid, value) {
            if (!this.canEditStructureSegment(translation.muid, uid)) return;
            if (!translation.data) {
                translation.data = {};
            }
            const previousValue = translation.data[uid] || "";
            if (!this.structureDraft && !this.isRemarkProject(translation.muid)) {
                const key = translation.muid + ':' + uid;
                if (!Object.hasOwn(this.dirtySegments, key)) this.dirtySegments[key] = previousValue;
                if (this.dirtySegments[key] === value) delete this.dirtySegments[key];
            }
            if (this.structureDraft && previousValue !== value) {
                this.structureDraft.reviewed = this.structureDraft.reviewed.filter(muid => muid !== translation.muid);
                this.structureDraftError = '';
            }
            translation.data[uid] = value;
            if (translation.muid && translation.muid.startsWith('html-')) {
                this.htmlDraftOverrides[uid] = value;
                this.invalidateHtmlValidation();
            }
            this.updateProgressForValueChange(translation, uid, previousValue, value);
        },
        hasTranslatedText(value) {
            return typeof value === "string" && value.trim() !== "";
        },
        updateProgressForValueChange(translation, uid, previousValue, nextValue) {
            if (translation.muid !== this.progressState.translationMuid) {
                return;
            }

            const sourceTranslation = this.translations.find(t => t.isSource);
            if (
                !sourceTranslation?.data ||
                !Object.prototype.hasOwnProperty.call(sourceTranslation.data, uid)
            ) {
                return;
            }

            const wasTranslated = this.hasTranslatedText(previousValue);
            const isTranslated = this.hasTranslatedText(nextValue);
            if (wasTranslated === isTranslated) {
                return;
            }

            this.progressState.translated += isTranslated ? 1 : -1;
            this.publishProgress();
        },
        /**
         * Calculate translation progress
         * @returns {Object} { translated: number, total: number, percentage: number }
         */
        getTranslationProgress() {
            const sourceTranslation = this.translations.find(t => t.isSource);
            const editableTranslation = this.translations.find(
                t => t.canEdit && !t.isSource && !this.isRemarkProject(t.muid)
            );

            if (!sourceTranslation || !editableTranslation) {
                return { translated: 0, total: 0, percentage: 0 };
            }

            const sourceData = sourceTranslation.data || {};
            const translationData = editableTranslation.data || {};
            const totalKeys = Object.keys(sourceData).length;

            if (totalKeys === 0) {
                return { translated: 0, total: 0, percentage: 0 };
            }

            let translatedCount = 0;
            for (const key of Object.keys(sourceData)) {
                const value = translationData[key];
                if (this.hasTranslatedText(value)) {
                    translatedCount++;
                }
            }

            const percentage = Math.round((translatedCount / totalKeys) * 100);
            return { translated: translatedCount, total: totalKeys, percentage };
        },
        updateProgress() {
            const progressData = this.getTranslationProgress();
            const editableTranslation = this.translations.find(
                t => t.canEdit && !t.isSource && !this.isRemarkProject(t.muid)
            );
            this.progressState.translationMuid = editableTranslation?.muid || null;
            this.progressState.translated = progressData.translated;
            this.progressState.total = progressData.total;
            this.publishProgress();
        },
        publishProgress() {
            const { translated, total } = this.progressState;
            const percentage = total > 0
                ? Math.round((translated / total) * 100)
                : 0;
            window.dispatchEvent(new CustomEvent('translation-progress-update', {
                detail: { translated, total, percentage }
            }));
        },
        _backupTranslations() {
            this.originalTranslations = JSON.parse(
                JSON.stringify(this.translations)
            );
        },
        _restoreTranslations() {
            if (this.originalTranslations) {
                this.translations = JSON.parse(
                    JSON.stringify(this.originalTranslations)
                );
                this.originalTranslations = null;
                this.updateProgress();
            }
        },
        _commitSplitMergeOperation() {
            this.originalTranslations = null;
            this.updateProgress();
        },
        hasActiveOperation() {
            return this.originalTranslations !== null;
        },
        _ensureHtmlProjectInTranslations(translations = this.translations) {
            if (!this.htmlProjectName || !this.htmlProject) return;

            const existingProject = translations.find(project => project.muid === this.htmlProjectName);
            if (!existingProject) {
                translations.push(this.htmlProject);
            }
        },
        async withGuard(data, flag, action) {
            if (data[flag]) return;
            data[flag] = true;
            await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
            try {
                await action();
            } finally {
                data[flag] = false;
            }
        },
        async splitBasedOnUid(translations, uid, element) {
            return this.startStructureDraft('split', uid, element);
        },
        async mergeBasedOnUid(translations, uid, element) {
            return this.startStructureDraft('merge', uid, element);
        },
        async startStructureDraft(operation, uid, element) {
            if (this.relatedProjectsLocked()) return false;
            if (this.relatedProjectLoads) {
                displayMessage(element, 'Wait for related projects to finish loading before splitting or merging.');
                return false;
            }
            if (Object.keys(this.dirtySegments).length) {
                displayMessage(element, 'Save your pending edits with Enter before splitting or merging.');
                return false;
            }
            const root = this.translations.find(t => t.isSource);
            if (!root?.muid.startsWith('root-')) {
                displayMessage(element, 'Split and merge are only available on root text.');
                return false;
            }
            this.structurePreviewLoading = true;
            try {
                const response = await requestWithTokenRetry('projects/structure/preview/', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({muid: root.muid, prefix: this.prefix, operation, uid}),
                });
                const preview = await response.json();
                if (!response.ok) throw new Error(preview.detail || 'Could not preview operation');
                this._backupTranslations();
                this.structureDraftError = '';
                this.structureDraft = {preview, reviewed: [], submission: null,
                    htmlOverrides: {...this.htmlDraftOverrides}};
                this.splitter_uid = preview.splitter_uid;
                this.merger_uid = preview.merger_uid;
                this.mergee_uid = preview.mergee_uid;
                for (const project of preview.projects) {
                    let column = this.translations.find(t => t.muid === project.muid);
                    if (!column && project.manual) {
                        column = {muid: project.muid, prefix: this.prefix, canEdit: true};
                        this.translations.push(column);
                        // Original text is available in the merge comparison for newly shown columns.
                        this.originalTranslations.push({...column, _structureAdded: true, data: project.before});
                    }
                    if (column) column.data = JSON.parse(JSON.stringify(project.data));
                }
                this.invalidateHtmlValidation();
                this.updateProgress();
                return true;
            } catch (error) {
                displayMessage(element, error.message);
                return false;
            } finally {
                this.structurePreviewLoading = false;
            }
        },
        canEditStructureSegment(muid, uid) {
            if (this.structurePreviewLoading) return false;
            if (!this.structureDraft) return true;
            const {preview, submission} = this.structureDraft;
            return !submission && preview.projects.some(project => project.muid === muid) &&
                (uid === preview.uid || (preview.operation === 'split' && uid === preview.splitter_uid));
        },
        structurePendingReviews() {
            const draft = this.structureDraft;
            return draft ? draft.preview.manual_projects.filter(muid => !draft.reviewed.includes(muid)) : [];
        },
        isStructureResult(muid, uid) {
            const preview = this.structureDraft?.preview;
            return !!preview && preview.projects.some(project => project.muid === muid) &&
                (uid === preview.uid || (preview.operation === 'split' && uid === preview.splitter_uid));
        },
        structureResultLabel(muid, uid) {
            if (!this.isStructureResult(muid, uid)) return '';
            const preview = this.structureDraft.preview;
            const role = preview.operation === 'merge' ? 'Merged segment' : uid === preview.splitter_uid ? 'New segment' : 'Retained segment';
            const column = this.translations.find(project => project.muid === muid);
            return role + ' · ' + uid + (column?.canEdit && !this.structureDraft.submission ? ' · Editable' : ' · Read-only');
        },
        async submitStructureDraftFromReview() {
            if (this.splitMergeProcessing || !this.structureDraft) return;
            this.structureDraftError = '';
            if (!this.structureDraft.submission && this.structurePendingReviews().length) {
                this.structureDraftError = 'Check each required project before confirming.';
                document.querySelector('.structure-draft-review input:not(:checked)')?.focus();
                return;
            }
            const operation = this.structureDraft.preview.operation === 'split' ? 'Split' : 'Merge';
            this.splitMergeProcessing = true;
            try {
                const result = await this.confirmStructureDraft(this.sourceMuid, this.prefix);
                if (!result) return;
                this.splitting = false;
                this.merging = false;
                this.affectedFiles = result.affectedFiles;
                this.affectedPrefix = result.prefix;
                const pending = ['pending', 'failed'].includes(result.publicationStatus);
                document.querySelector('sc-bilara-toast')?.show(pending
                    ? operation + ' saved. Automatic publication has not been queued. Ask an administrator to commit and push the affected files.'
                    : operation + ' saved. ' + result.autoPublishedPaths.length + ' files queued for GitHub unpublished',
                    pending ? 'warning' : 'success', 5000);
                this.$nextTick(() => document.querySelector('.dialog-affected-files')?.show());
            } catch (error) {
                this.structureDraftError = error.message;
            } finally {
                this.splitMergeProcessing = false;
            }
        },
        getStructureMergeSummary() {
            const preview = this.structureDraft?.preview;
            if (preview?.operation !== 'merge') return '';
            const summary = `Merge ${preview.mergee_uid} into ${preview.merger_uid}.`;
            return preview.merge_crosses_section
                ? summary + ' This crosses a section boundary. If the next segment is the only segment in its section, that section will no longer have a separate UID; its content is merged into the preceding segment.'
                : summary;
        },
        cancelSplit() { this.cancelStructureDraft(); },
        cancelMerge() { this.cancelStructureDraft(); },
        cancelStructureDraft() {
            if (this.structureDraft?.submission) {
                throw new Error('The submitted operation must be checked before cancelling. Click Confirm to check its status.');
            }
            this.htmlDraftOverrides = this.structureDraft?.htmlOverrides || {};
            this._restoreTranslations();
            this.translations = this.translations.filter(t => !t._structureAdded);
            this.htmlProject = this.translations.find(t => t.muid === this.htmlProjectName) || this.htmlProject;
            this.structureDraft = null;
            this.structureDraftError = '';
            this.splitting = false;
            this.merging = false;
            this.invalidateHtmlValidation();
        },
        isMergeHighlightedRow(uid) {
            return this.merger_uid === uid;
        },
        isSplitHighlightedRow(uid, splittingUid) {
            return splittingUid === uid || this.splitter_uid === uid;
        },
        getMergePreviewParts(translation, uid) {
            if (!this.originalTranslations || uid !== this.merger_uid) {
                return null;
            }

            const originalTranslation = this.originalTranslations.find(item => item.muid === translation.muid);
            const currentText = translation && translation.data
                ? translation.data[uid] || ""
                : "";
            const mergerText = originalTranslation && originalTranslation.data
                ? originalTranslation.data[this.merger_uid] || currentText
                : currentText;
            const mergeeText = originalTranslation && originalTranslation.data
                ? originalTranslation.data[this.mergee_uid] || ""
                : "";
            if (!mergerText && !mergeeText) {
                return null;
            }

            return {
                mergerUid: this.merger_uid,
                mergerText,
                mergeeUid: this.mergee_uid,
                mergeeText
            };
        },
        getSplitPreviewPart(translation, uid, splittingUid) {
            if (!this.originalTranslations || (uid !== splittingUid && uid !== this.splitter_uid)) {
                return null;
            }

            const role = uid === splittingUid ? "original" : "new";
            const label = role === "original" ? uid + " current" : uid + " new";
            const currentText = translation && translation.data
                ? translation.data[uid] || ""
                : "";
            const originalTranslation = this.originalTranslations.find(item => item.muid === translation.muid);
            const originalText = originalTranslation && originalTranslation.data
                ? originalTranslation.data[splittingUid] || currentText
                : currentText;

            return {
                role,
                label,
                text: role === "original"
                    ? (originalText || "Current segment is empty")
                    : (currentText || "New empty segment")
            };
        },
        redirectToHtml() {
            const params = new URLSearchParams(window.location.search);
            const prefix = params.get("prefix");
            const muid = 'html-pli-ms';
            const source = params.get("source");
            return (window.location.href = `/translation?prefix=${prefix}&muid=${muid}&source=${source}`);
        },
        async findOrCreateObject(key, prefix, source = false) {
            let obj = this.translations.find(item => item.muid === key);
            if (!obj) {
                try {
                    const remarksMuid = this.sourceMuid || this.muid;
                    let data;
                    if (this.isRemarkProject(key)) {
                        const gid = this.getRemarkGithubId(key);
                        data = await this.fetchRemarksData(remarksMuid, prefix, gid);
                        // Only the current user can edit their own remarks
                        data.can_edit = (gid === this.currentUserGithubId);
                    } else {
                        data = await this.fetchData(key, prefix);
                    }
                    obj = { canEdit: false, muid: key, prefix: prefix };
                    obj["data"] = data.data;
                    obj["canEdit"] = data["can_edit"];
                    obj.materialized = data.materialized;
                } catch (error) {
                    throw error;
                }
                if (source) {
                    obj.isSource = true;
                }
                this.translations.push(obj);
            }
            return obj;
        },
        async createObject(key, prefix, source = false) {
            let obj = this.translations.find(item => item.muid === key);
            if (!obj) {
                try {
                    const remarksMuid = this.sourceMuid || this.muid;
                    let data;
                    if (this.isRemarkProject(key)) {
                        const gid = this.getRemarkGithubId(key);
                        data = await this.fetchRemarksData(remarksMuid, prefix, gid);
                        data.can_edit = (gid === this.currentUserGithubId);
                    } else {
                        data = await this.fetchData(key, prefix);
                    }
                    obj = { canEdit: false, muid: key, prefix: prefix };
                    obj["data"] = data.data;
                    obj["canEdit"] = data["can_edit"];
                    obj.materialized = data.materialized;
                } catch (error) {
                    throw error;
                }
                if (source) {
                    obj.isSource = true;
                }
            }
            return obj;
        },
        async fetchData(key, prefix) {
            try {
                const response = await requestWithTokenRetry(`projects/${key}/${prefix}/`);
                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || `Server error (${response.status})`);
                }
                if (!data.data) {
                    throw new Error("Invalid data format from the API");
                }
                this.structureRevisions[key] = data.structure_revision;
                return data;
            } catch (error) {
                throw error;
            }
        },
        async refreshHtmlProject(prefix = this.prefix) {
            if (!this.htmlProjectName) return;

            const data = await this.fetchData(this.htmlProjectName, prefix);
            const existingProject = this.translations.find(project => project.muid === this.htmlProjectName);
            const targetProject = existingProject || this.htmlProject || {
                canEdit: false,
                muid: this.htmlProjectName,
                prefix,
            };

            targetProject.data = data.data;
            targetProject.canEdit = data.can_edit;
            targetProject.prefix = prefix;
            this.htmlProject = targetProject;
        },
        async refreshHtmlProjectAfterSplitMerge(prefix) {
            try {
                await this.refreshHtmlProject(prefix);
            } catch (error) {
                console.error("Failed to refresh HTML project after split/merge:", error);
                const toast = document.querySelector("sc-bilara-toast");
                if (toast) {
                    toast.show("HTML column could not be refreshed. Please reload the page.", "warning", 5000);
                }
            }
        },
        async fetchRemarkUsers(muid, prefix) {
            try {
                const response = await requestWithTokenRetry(`remarks/users/${muid}/${prefix}/`);
                if (!response.ok) return [];
                const data = await response.json();
                return Array.isArray(data) ? data : [];
            } catch (error) {
                console.error('Failed to fetch remark users:', error);
                return [];
            }
        },
        async fetchRemarksData(muid, prefix, githubId) {
            try {
                let url = `remarks/${muid}/${prefix}/`;
                if (githubId != null) {
                    url += `?github_id=${githubId}`;
                }
                const response = await requestWithTokenRetry(url);
                const data = await response.json();
                if (!Array.isArray(data)) {
                    throw new Error("Invalid remarks data format from the API");
                }
                const normalizedData = data.reduce((acc, item) => {
                    if (item && item.segment_id) {
                        acc[item.segment_id] = item.remark_value || "";
                    }
                    return acc;
                }, {});
                return {
                    data: normalizedData,
                    can_edit: true,
                };
            } catch (error) {
                throw error;
            }
        },
        async handleEnter(event, uid, segment, translation, originalValue = '') {
            if (this.structurePreviewLoading || this.structureDraft) return;
            if (translation.canEdit) {
                if (event.shiftKey) {
                    event.target.value += "\n";
                    return;
                }
                // Find the textarea in the next row of the same column.
                const currentTextarea = event.target;
                const currentCell = currentTextarea.closest('.translation-cell');
                const currentRow = currentTextarea.closest('.translation-row');
                const nextRow = currentRow?.nextElementSibling;
                if (nextRow && currentCell) {
                    const colIndex = Array.from(currentCell.parentElement.children).indexOf(currentCell);
                    const nextTextarea = nextRow.querySelector('.translation-row__cells')?.children[colIndex]?.querySelector('textarea');
                    if (nextTextarea) {
                        nextTextarea.focus();
                        // Move cursor to the end of the text
                        const textLength = nextTextarea.value.length;
                        nextTextarea.setSelectionRange(textLength, textLength);
                    }
                }

                // Ordinary edits are compared with saved content, not the latest focus value.
                const key = translation.muid + ':' + uid;
                const modified = this.isRemarkProject(translation.muid)
                    ? segment !== originalValue
                    : Object.hasOwn(this.dirtySegments, key) && segment !== this.dirtySegments[key];
                if (modified) {
                    // Validate tag values before saving
                    if (translation.muid && translation.muid.startsWith('tag')) {
                        const invalidTags = this.getInvalidTags(segment);
                        if (invalidTags.length > 0) {
                            const toast = document.querySelector('sc-bilara-toast');
                            if (toast) {
                                toast.show(`Invalid tags: ${invalidTags.join(', ')}`, 'warning');
                            }
                            return;
                        }
                    }
                    try {
                        if (this.isRemarkProject(translation.muid)) {
                            await this.updateRemarkHandler(uid, segment);
                        } else {
                            await this.updateHandler(
                                translation.muid,
                                { [uid]: segment },
                                document.querySelector("span.project-header__message"),
                            );
                        }
                    } catch (error) {
                        throw error;
                    }
                }
            }
        },
        async updateRemarkHandler(uid, value) {
            const remarksMuid = this.sourceMuid || this.muid;
            const remarkPayload = {
                muid: remarksMuid,
                prefix: this.prefix,
                segment_id: uid,
                remark_value: value,
            };
            try {
                let response = await requestWithTokenRetry("remarks/", {
                    credentials: "include",
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(remarkPayload),
                });

                // PUT updates existing remarks; fallback to POST for first-time creation.
                if (response.status === 404) {
                    response = await requestWithTokenRetry("remarks/", {
                        credentials: "include",
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(remarkPayload),
                    });
                }

                if (!response.ok) {
                    const body = await response.json().catch(() => null);
                    throw new Error(body?.detail ?? "Failed to save remark");
                }
            } catch (error) {
                throw error;
            }
        },
        async updateHandler(muid, data, element, btnId='btn-translation-commit') {
            if (this.structureDraft) throw new Error('Confirm or cancel the structure draft before saving.');
            const badgeId = `translation-badge-${muid}-${Object.keys(data)[0]}`;
            if (Object.keys(data).length === 1) {
                hideBadge(badgeId);
            }
            try {
                displayBadge(badgeId, BadgeStatus.PENDING);
                const response = await requestWithTokenRetry(`projects/${muid}/${this.prefix}/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json", ...(this.structureRevisions[muid] ? {"X-Structure-Revision": this.structureRevisions[muid]} : {}) },
                    body: JSON.stringify(data),
                });
                if (!response.ok) {
                    const body = await response.json().catch(() => null);
                    throw new Error(body?.detail ?? `Server error (${response.status})`);
                }
                if (muid && muid.startsWith('html-')) {
                    Object.keys(data).forEach(uid => delete this.htmlDraftOverrides[uid]);
                }
                const { materialized } = await response.json();
                const column = this.translations.find(t => t.muid === muid);
                if (column) column.materialized = materialized;
                for (const [uid, value] of Object.entries(data)) {
                    const key = muid + ":" + uid;
                    if (column?.data[uid] === value) delete this.dirtySegments[key];
                    else if (column) this.dirtySegments[key] = value;
                }
                // if (!taskID) {
                //     displayMessage(
                //         element,
                //         "There has been an error. Please retry in a few moments. If the issue persists, please contact the administrator.",
                //         "failure",
                //     );
                // }
                if (Object.keys(data).length > 1) {
                    // displayMessage(
                    //     element,
                    //     "Your changes have reached the server. They are being processed at the moment. This may take some time. Please continue your work as normal.",
                    // );
                    const toast = document.querySelector('sc-bilara-toast');
                    toast.show('Your changes have reached the server. They are being processed at the moment. This may take some time. Please continue your work as normal.', 'success');
                }
                if (Object.keys(data).length === 1) {
                    displayBadge(badgeId, BadgeStatus.COMMITTED);
                }
            } catch (error) {
                displayBadge(badgeId, BadgeStatus.ERROR);
                throw error;
            }
        },
        async updateHandlerForSplit(muid, prefix) {
            return this.confirmStructureDraft(muid, prefix);
        },
        async updateHandlerForMerge(muid, prefix) {
            return this.confirmStructureDraft(muid, prefix);
        },
        async confirmStructureDraft(muid, prefix) {
            const draft = this.structureDraft;
            if (!draft) throw new Error('Generate a preview before confirming');
            const preview = draft.preview;
            if (!draft.submission) {
                if (preview.manual_projects.some(muid => !draft.reviewed.includes(muid))) {
                    throw new Error('Review every manual project before confirming.');
                }
                const edits = {};
                for (const column of this.translations) {
                    const original = preview.projects.find(p => p.muid === column.muid);
                    if (!original) continue;
                    const changes = {};
                    for (const [uid, value] of Object.entries(column.data)) {
                        if (value !== original.data[uid]) changes[uid] = value;
                    }
                    if (Object.keys(changes).length) edits[column.muid] = changes;
                }
                draft.submission = {muid, prefix: this.prefix, operation: preview.operation,
                    uid: preview.uid, revision: preview.revision, edits,
                    reviewed: [...draft.reviewed],
                    operation_id: crypto.randomUUID()};
            } else {
                const statusResponse = await requestWithTokenRetry('projects/structure/status/', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({muid, prefix: this.prefix, operation_id: draft.submission.operation_id}),
                });
                const status = await statusResponse.json().catch(() => ({}));
                if (!statusResponse.ok) throw new Error(status.detail?.message || status.detail || 'Operation is still pending; retry confirmation.');
                if (status.status === 'complete') return this.applyStructureResult(status);
                if (status.status !== 'not_found') throw new Error('Unknown structure operation status. Retry confirmation.');
            }
            return this.submitStructureOperation(draft.submission);
        },
        async submitStructureOperation(submission) {
            localStorage.setItem(this.structureRecoveryKey(), JSON.stringify(submission));
            const response = await requestWithTokenRetry(`projects/${submission.operation}/`, {
                credentials: 'include', method: 'PATCH', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(submission),
            });
            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                if (response.status >= 400 && response.status < 500 && error.detail?.code === 'submission_rejected') {
                    if (this.structureDraft) this.structureDraft.submission = null;
                    localStorage.removeItem(this.structureRecoveryKey());
                }
                throw new Error(error.detail?.message || error.detail || 'Submission interrupted. Click Confirm to check and resume the operation.');
            }
            return this.applyStructureResult(await response.json());
        },
        structureRecoveryKey() {
            return `bilara:structure:${this.sourceMuid}:${this.prefix}`;
        },
        async resumeStructureOperation() {
            const saved = localStorage.getItem(this.structureRecoveryKey());
            if (!saved) return;
            let submission;
            try {
                submission = JSON.parse(saved);
            } catch (error) {
                throw new Error('Saved structure operation recovery data is corrupted. The record has been preserved; contact an administrator to recover the operation.');
            }
            const response = await requestWithTokenRetry('projects/structure/status/', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({muid: submission.muid, prefix: submission.prefix, operation_id: submission.operation_id}),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) throw new Error(result.detail?.message || result.detail || 'A structure operation is pending. Retry loading to resume it.');
            if (result.status === 'complete') {
                if (['pending', 'failed'].includes(result.publication_status)) {
                    document.querySelector('sc-bilara-toast')?.show('Structure changes are saved. Automatic publication is not confirmed. Ask an administrator to commit and push the affected files.', 'warning', 10000);
                }
                return this.applyStructureResult(result);
            }
            if (result.status === 'not_found') return this.submitStructureOperation(submission);
            throw new Error('Unknown structure operation status. Retry loading to resume it.');
        },
        applyStructureResult(result) {
            // Virtual translations share the root's revision but have no file in the result.
            for (const column of this.translations) {
                if (column.muid.startsWith('translation-') && column.materialized === false && column.prefix === this.prefix) {
                    this.structureRevisions[column.muid] = result.structure_revision;
                }
            }
            for (const project of result.projects) {
                const column = this.translations.find(t => t.muid === project.muid);
                if (column) {
                    column.data = project.data;
                    column.materialized = true;
                }
                this.structureRevisions[project.muid] = result.structure_revision;
            }
            this.structureDraft = null;
            this.htmlDraftOverrides = {};
            this.dirtySegments = {};
            this.htmlProject = this.translations.find(t => t.muid === this.htmlProjectName) || this.htmlProject;
            this.invalidateHtmlValidation();
            this._commitSplitMergeOperation();
            localStorage.removeItem(this.structureRecoveryKey());
            const modes = this._buildSplitMergePublishModeMap(result);
            return {affectedFiles: result.projects.map(p => this._buildAffectedFile('/' + p.path, p.muid, p.muid === this.sourceMuid ? 'main' : 'related', modes)),
                prefix: this.prefix, autoPublishedPaths: result.auto_published_paths || [],
                autoPublishTaskId: result.auto_publish_task_id || null,
                publicationStatus: result.publication_status};
        },
        _buildSplitMergePublishModeMap(result) {
            const publishModeByPath = new Map();
            for (const path of result.auto_publish_pending_paths || []) {
                publishModeByPath.set(path, 'pending');
            }
            for (const path of result.auto_published_paths || []) {
                publishModeByPath.set(path, 'auto');
            }
            return publishModeByPath;
        },
        _buildAffectedFile(path, muid, type, publishModeByPath) {
            return {
                path,
                muid,
                type,
                publishMode: publishModeByPath.get(path) || 'pending',
            };
        },
        async fetchRelatedProjects(prefix) {
            try {
                const response = await requestWithTokenRetry(`projects/?prefix=${prefix}`);
                const data = await response.json();
                if (!data.projects) {
                    throw new Error("Invalid data format from the API");
                }
                return data.projects;
            } catch (error) {
                throw error;
            }
        },
        async loadAvailableTags() {
            try {
                const response = await requestWithTokenRetry('tags/');
                const data = await response.json();
                this.availableTags = Array.isArray(data) ? data : [];
            } catch (error) {
                this.availableTags = [];
            }
        },
        validateTagValue(value) {
            if (!value || !value.trim()) return true;
            const tags = value.split(',').map(t => t.trim()).filter(t => t);
            const validNames = new Set(this.availableTags.map(t => t.tag));
            return tags.every(t => validNames.has(t));
        },
        getInvalidTags(value) {
            if (!value || !value.trim()) return [];
            const tags = value.split(',').map(t => t.trim()).filter(t => t);
            const validNames = new Set(this.availableTags.map(t => t.tag));
            return tags.filter(t => !validNames.has(t));
        },
        async toggleRelatedProject(project) {
            if (this.relatedProjectsLocked()) return false;
            const index = this.translations.findIndex(t => t.muid === project);
            if (index > -1) {
                this.translations.splice(index, 1);
                const saved = this.getSavedRelatedProjects().filter(p => p !== project);
                this.saveRelatedProjects(saved);
            } else {
                this.relatedProjectLoads++;
                try {
                    await this.findOrCreateObject(project, this.prefix);
                    const saved = this.getSavedRelatedProjects();
                    if (!saved.includes(project)) {
                        saved.push(project);
                        this.saveRelatedProjects(saved);
                    }
                    this.applySavedColumnOrder();
                    this.saveColumnOrder();
                } catch (error) {
                    throw error;
                } finally {
                    this.relatedProjectLoads--;
                }
            }
            return true;
        },
        getSavedRelatedProjects() {
            try {
                const key = `relatedProjects_${this.muid}`;
                return JSON.parse(localStorage.getItem(key)) || [];
            } catch {
                return [];
            }
        },
        saveRelatedProjects(projects) {
            const key = `relatedProjects_${this.muid}`;
            localStorage.setItem(key, JSON.stringify(projects));
        },
        async restoreRelatedProjectsInOrder(projects) {
            const results = await Promise.all(projects.map(async project => {
                try {
                    const obj = await this.createObject(project, this.prefix);
                    return { project, obj };
                } catch (error) {
                    console.error(`Failed to restore related project ${project}:`, error);
                    return { project, obj: null };
                }
            }));

            const loadedProjects = [];
            for (const { project, obj } of results) {
                if (!obj) continue;
                if (!this.translations.some(item => item.muid === obj.muid)) {
                    this.translations.push(obj);
                }
                loadedProjects.push(project);
            }
            return loadedProjects;
        },
    };
}

function countChar(str, char) {
    return str.split(char).length - 1;
}

function getLastNumber(str) {
    return str.split('.').pop();
}

function getBeforeLastDot(str) {
    return str.substring(0, str.lastIndexOf('.') + 1);
}

function isMergeSplitConditionMet(uid, key) {
    return /^[^:]+:[0-9]+(?:\.[0-9]+)*$/.test(uid);
}

function escapeHtml(text) {
    const el = document.createElement('span');
    el.textContent = text || '';
    return el.innerHTML;
}

function tokenizeForRootMatch(text) {
    const tokens = [];
    const tokenRegex = /[\p{L}\p{M}\p{N}]+/gu;
    const value = String(text || '');
    let match;

    while ((match = tokenRegex.exec(value)) !== null) {
        tokens.push({
            value: match[0].normalize('NFC').toLocaleLowerCase(),
            start: match.index,
            end: match.index + match[0].length,
        });
    }

    return tokens;
}

function findRootMatchSpans(hintTokens, rootTokens) {
    const runs = [];

    for (let hintIndex = 0; hintIndex < hintTokens.length; hintIndex++) {
        for (let rootIndex = 0; rootIndex < rootTokens.length; rootIndex++) {
            if (hintTokens[hintIndex].value !== rootTokens[rootIndex].value) continue;
            if (
                hintIndex > 0 &&
                rootIndex > 0 &&
                hintTokens[hintIndex - 1].value === rootTokens[rootIndex - 1].value
            ) {
                continue;
            }

            let length = 0;
            while (
                hintIndex + length < hintTokens.length &&
                rootIndex + length < rootTokens.length &&
                hintTokens[hintIndex + length].value === rootTokens[rootIndex + length].value
            ) {
                length++;
            }

            runs.push({
                startToken: hintIndex,
                endToken: hintIndex + length - 1,
                length,
            });
        }
    }

    const usedTokens = new Array(hintTokens.length).fill(false);
    return runs
        .sort((a, b) => b.length - a.length || a.startToken - b.startToken)
        .filter(run => {
            for (let index = run.startToken; index <= run.endToken; index++) {
                if (usedTokens[index]) return false;
            }
            for (let index = run.startToken; index <= run.endToken; index++) {
                usedTokens[index] = true;
            }
            return true;
        })
        .map(run => ({
            start: hintTokens[run.startToken].start,
            end: hintTokens[run.endToken].end,
        }))
        .sort((a, b) => a.start - b.start);
}

function highlightRootMatches(hintSegment, rootText) {
    const segment = String(hintSegment || '');
    const hintTokens = tokenizeForRootMatch(segment);
    const rootTokens = tokenizeForRootMatch(rootText);

    if (hintTokens.length === 0 || rootTokens.length === 0) {
        return escapeHtml(segment);
    }

    const spans = findRootMatchSpans(hintTokens, rootTokens);
    if (spans.length === 0) {
        return escapeHtml(segment);
    }

    let highlighted = '';
    let cursor = 0;
    for (const span of spans) {
        highlighted += escapeHtml(segment.slice(cursor, span.start));
        highlighted += `<mark class="translation-cell__hints-match">${escapeHtml(segment.slice(span.start, span.end))}</mark>`;
        cursor = span.end;
    }
    highlighted += escapeHtml(segment.slice(cursor));

    return highlighted;
}

if (typeof window !== 'undefined') {
    window.highlightRootMatches = highlightRootMatches;
}

async function getHints(uid, muid, sourceMuid, sourceValue) {
    const params = new URLSearchParams({
        segment_id: uid,
        target_muid: muid,
        source_muid: sourceMuid,
        text_value: sourceValue,
    });
    const response = await requestWithTokenRetry(`search/hints/?${params.toString()}`);
    return await response.json();
}
