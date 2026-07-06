function fetchTranslation() {
    const REMARKS_PREFIX = "remarks:";
    return {
        translations: [],
        loading: true,
        relatedProjects: [],
        remarkUsers: [],
        currentUserGithubId: null,
        currentUsername: null,
        htmlProjectName: '',
        htmlProject: null,
        tagProjectName: '',
        tagProject: null,
        availableTags: [],
        hyphenatedPrefixRanges: [],
        originalTranslations: null,
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
        async init() {
            this.loading = true;
            try {
                await this.initialize();
            } finally {
                this.loading = false;
            }
        },
        async initialize() {
            const params = new URLSearchParams(window.location.search);
            this.prefix = params.get("prefix");
            const muid = params.get("muid");
            const source = params.get("source");

            this.muid = muid;
            this.sourceMuid = source;

            // Fetch current user info directly
            try {
                const userResp = await requestWithTokenRetry("users/me");
                if (userResp.ok) {
                    const userData = await userResp.json();
                    this.currentUserGithubId = userData.github_id || null;
                    this.currentUsername = userData.username || null;
                }
            } catch (e) {
                console.error('Failed to fetch current user info:', e);
            }

            await this.loadHyphenatedPrefixRanges();

            // Try loading source with original prefix; fall back to hyphenated range on failure
            try {
                await this.findOrCreateObject(source, this.prefix, true);
            } catch (error) {
                const fallbackPrefix = this.getFallbackPrefix(this.prefix);
                if (fallbackPrefix) {
                    console.info(`Prefix "${this.prefix}" not found, falling back to range prefix "${fallbackPrefix}"`);
                    this.prefix = fallbackPrefix;
                    await this.findOrCreateObject(source, this.prefix, true);
                    // Update URL to reflect the resolved prefix
                    const url = new URL(window.location);
                    url.searchParams.set("prefix", this.prefix);
                    window.history.replaceState(null, "", url);
                } else {
                    throw error;
                }
            }

            if (muid) {
                await this.findOrCreateObject(muid, this.prefix);
            }
            const projects = await this.fetchRelatedProjects(this.prefix);

            this.htmlProjectName = projects.find(project => project.includes('html'));
            if (this.htmlProjectName) {
                this.htmlProject = await this.createObject(this.htmlProjectName, this.prefix);
            }

            this.tagProjectName = projects.find(project => project.startsWith('tag'));
            await this.loadAvailableTags();

            this.relatedProjects = projects.filter(project =>
                project !== muid && project !== source &&
                project !== this.htmlProjectName
            );

            // Build remark projects per user
            const remarksMuid = this.sourceMuid || this.muid;
            this.remarkUsers = await this.fetchRemarkUsers(remarksMuid, this.prefix);
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
            if (shouldAutoLoadRemarks) {
                try {
                    await this.findOrCreateObject(myRemarkKey, this.prefix);
                    // On first visit, seed localStorage so toggle can track removals
                    if (!hasPersistedState) {
                        this.saveRelatedProjects([myRemarkKey]);
                    }
                } catch (error) {
                    console.error('Failed to auto-load own remarks:', error);
                }
            }

            const validSaved = savedRelated.filter(p => this.relatedProjects.includes(p));
            for (const project of validSaved) {
                try {
                    await this.findOrCreateObject(project, this.prefix);
                } catch (error) {
                    console.error(`Failed to restore related project ${project}:`, error);
                }
            }
            // Build the list of all loaded projects for the restore event
            const allLoaded = [...validSaved];
            if (shouldAutoLoadRemarks && myRemarkKey && !allLoaded.includes(myRemarkKey)) {
                allLoaded.push(myRemarkKey);
            }
            window.dispatchEvent(new CustomEvent('restore-related-projects', { detail: { projects: allLoaded } }));

            // Apply saved column order after all translations are loaded
            try {
                const orderKey = `bilara:col-order:${this.prefix}:${source}:${muid}`;
                const saved = JSON.parse(localStorage.getItem(orderKey));
                if (Array.isArray(saved) && saved.length > 0) {
                    const byMuid = {};
                    this.translations.forEach(t => byMuid[t.muid] = t);
                    const reordered = [];
                    const used = new Set();
                    saved.forEach(m => {
                        if (byMuid[m] && !used.has(m)) { reordered.push(byMuid[m]); used.add(m); }
                    });
                    reordered.push(...this.translations.filter(t => !used.has(t.muid)));
                    if (reordered.length === this.translations.length) {
                        this.translations.splice(0, this.translations.length, ...reordered);
                    }
                }
            } catch(e) { /* ignore corrupt data */ }

            this.updateProgress();
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
            if (!translation.data) {
                translation.data = {};
            }
            translation.data[uid] = value;
            this.updateProgress();
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
                if (value && value.trim() !== '') {
                    translatedCount++;
                }
            }

            const percentage = Math.round((translatedCount / totalKeys) * 100);
            return { translated: translatedCount, total: totalKeys, percentage };
        },
        updateProgress() {
            const progressData = this.getTranslationProgress();
            window.dispatchEvent(new CustomEvent('translation-progress-update', {
                detail: progressData
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
            if (!isMergeSplitConditionMet(uid)) {
                displayMessage(
                    element,
                    "This type of uid does not support splitting."
                );
                return false;
            }

            if (this.hasActiveOperation()) {
                const confirmed = confirm(
                    'You have an unsaved split/merge operation. ' +
                    'Do you want to discard it and start a new split?'
                );
                if (!confirmed) {
                    return false;
                }
            }

            if (localStorage.getItem('enableSplitHintDialog') === null) {
                localStorage.setItem('enableSplitHintDialog', 'true');
            }

            if (localStorage.getItem('enableSplitHintDialog') === "true") {
                document.querySelector('.dialog-split-hint')?.show();
            }

            this._ensureHtmlProjectInTranslations(translations);
            this._backupTranslations();

            const [sectionUid, sectionNumber] = uid.split(':');
            const isTwoLevelFormat = /^\d+\.\d+$/.test(sectionNumber);
            const isThreeLevelFormat = /^\d+\.\d+\.\d+$/.test(sectionNumber);

            // Processing two-level format: mn1:1.1
            if (isTwoLevelFormat) {
                this._handleTwoLevelSplit(
                    translations,
                    sectionUid,
                    sectionNumber
                );
            }
            // Processing level 3 format: dn1:1.1.1
            else if (isThreeLevelFormat) {
                this._handleThreeLevelSplit(
                    translations,
                    sectionUid,
                    sectionNumber
                );
            }

            this.updateProgress();

            return true;
        },
        _handleTwoLevelSplit(translations, sectionUid, sectionNumber) {
            const [integerPart, decimalPart] = sectionNumber.split('.');
            const splitPointNumber = parseInt(decimalPart);
            this.splitter_uid = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;

            translations.forEach(translation => {
                const newObj = {};

                for (const key in translation.data) {
                    const [keySectionUid, keySectionNumber] = key.split(':');
                    const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                    const keyDecimalNumber = parseInt(keyDecimalPart);

                    // Paragraphs that do not match the current section
                    if (keySectionUid !== sectionUid || keyIntegerPart !== integerPart) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    // Process matching paragraphs
                    if (keyDecimalNumber < splitPointNumber) {
                        newObj[key] = translation.data[key];
                    } else if (keyDecimalNumber === splitPointNumber) {
                        newObj[key] = translation.data[key];
                        const newKey = `${sectionUid}:${integerPart}.${splitPointNumber + 1}`;
                        newObj[newKey] = translation.muid.includes('html')
                            ? "{}"
                            : "";
                    } else {
                        const newKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                        newObj[newKey] = translation.data[key];
                    }
                }
                translation.data = newObj;
            });
        },
        _handleThreeLevelSplit(translations, sectionUid, sectionNumber) {
            const sectionMainPart = getBeforeLastDot(sectionNumber);
            const sectionLastPart = parseInt(getLastNumber(sectionNumber));
            this.splitter_uid = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;

            translations.forEach(translation => {
                const newObj = {};

                for (const key in translation.data) {
                    const [keySectionUid, keySectionNumber] = key.split(':');

                    if (keySectionUid !== sectionUid) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    const keyMainPart = getBeforeLastDot(keySectionNumber);
                    const keyLastPart = parseInt(getLastNumber(keySectionNumber));

                    if (keyMainPart !== sectionMainPart) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    if (keyLastPart < sectionLastPart) {
                        newObj[key] = translation.data[key];
                    } else if (keyLastPart === sectionLastPart) {
                        newObj[key] = translation.data[key];
                        const newKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;
                        newObj[newKey] = translation.muid.includes('html')
                            ? "{}"
                            : "";
                    } else {
                        const newKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                        newObj[newKey] = translation.data[key];
                    }
                }
                translation.data = newObj;
            });
        },
        cancelSplit(translations) {
            this._restoreTranslations();
            // localStorage.setItem('displayButtonForSplitOrMerge', 'false');
        },
        mergeBasedOnUid(translations, uid, element) {
            if (!isMergeSplitConditionMet(uid)) {
                displayMessage(
                    element,
                    "This type of uid does not support merging.",
                );
                return false;
            }

            let newObj = {};
            this.merger_uid = uid;
            this._ensureHtmlProjectInTranslations(translations);
            this._backupTranslations();

            if (localStorage.getItem('enableMergeHintDialog') === null) {
                localStorage.setItem('enableMergeHintDialog', 'true');
            }

            if (localStorage.getItem('enableMergeHintDialog') === "true") {
                document.querySelector('.dialog-merge-hint')?.show();
            }

            const [sectionUid, sectionNumber] = uid.split(':');
            const isTwoLevelFormat = /^\d+\.\d+$/.test(sectionNumber);
            const isThreeLevelFormat = /^\d+\.\d+\.\d+$/.test(sectionNumber);

            // Two-level format: mn1:1.1
            if (isTwoLevelFormat) {
                this._handleTwoLevelMerge(translations, sectionUid, sectionNumber);
            }
            // Three-level format: dn1:1.1.1
            else if (isThreeLevelFormat) {
                this._handleThreeLevelMerge(translations, sectionUid, sectionNumber);
            }

            this.updateProgress();

            return true;
        },
        /**
         * Handle two-level format merge (e.g., mn1:1.1 + mn1:1.2)
         * @param {Array} translations - Translation objects array
         * @param {string} sectionUid - Section UID (e.g., 'mn1')
         * @param {string} sectionNumber - Section number (e.g., '1.1')
         */
        _handleTwoLevelMerge(translations, sectionUid, sectionNumber) {
            const [integerPart, decimalPart] = sectionNumber.split('.');
            const decimalNumber = parseInt(decimalPart);
            this.mergee_uid = `${sectionUid}:${integerPart}.${decimalNumber + 1}`;

            let needToMergeNextSection = false;
            let nextSectionFirstKey = '';

            translations.forEach(translation => {
                const newObj = {};

                for (const key in translation.data) {
                    const [keySectionUid, keySectionNumber] = key.split(':');

                    // If it does not match the current section, keep it directly.
                    if (keySectionUid !== sectionUid) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                    const keyDecimalNumber = parseInt(keyDecimalPart);

                    // If it does not match the current section, keep it directly.
                    if (keyIntegerPart !== integerPart) {
                        // If cross-section merging is needed, check if it is a paragraph of the target section
                        if (needToMergeNextSection) {
                            const nextSectionNumber = parseInt(nextSectionFirstKey.split(':')[1].split('.')[0]);
                            const currentSectionNumber = parseInt(keyIntegerPart);

                            if (currentSectionNumber === nextSectionNumber) {
                                this.mergeSectionByNextKey(key, translation, newObj);
                                continue;
                            }
                        }
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    // Process the paragraph of the current section
                    if (keyDecimalNumber < decimalNumber) {
                        // Paragraphs before the merge point remain unchanged.
                        newObj[key] = translation.data[key];
                    } else if (keyDecimalNumber === decimalNumber) {
                        // Merge point: merge current paragraph with next one
                        const nextKey = `${sectionUid}:${integerPart}.${decimalNumber + 1}`;

                        if (translation.data[nextKey]) {
                            // The next paragraph within the same section exists
                            newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                        } else {
                            // Try to merge across sections
                            const nextSectionIntegerPart = parseInt(integerPart) + 1;
                            const possibleNextKey1 = `${sectionUid}:${nextSectionIntegerPart}.0`;
                            const possibleNextKey2 = `${sectionUid}:${nextSectionIntegerPart}.1`;
                            const crossSectionNextKey = translation.data[possibleNextKey1]
                                ? possibleNextKey1
                                : possibleNextKey2;

                            if (translation.data[crossSectionNextKey]) {
                                this.mergee_uid = crossSectionNextKey;
                                nextSectionFirstKey = crossSectionNextKey;
                                needToMergeNextSection = true;
                                newObj[key] = `${translation.data[key]} ${translation.data[crossSectionNextKey]}`;
                            } else {
                                // No mergeable paragraph exists, keep it unchanged
                                newObj[key] = translation.data[key];
                            }
                        }
                    } else {
                        // Paragraphs after the merge point: shift down by decrementing the number
                        const nextKey = `${sectionUid}:${integerPart}.${keyDecimalNumber + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = translation.data[nextKey];
                        }
                        // If no next key exists, this paragraph is deleted (merged into previous)
                    }
                }

                translation.data = newObj;
                translation.splitting = true;
            });
        },

        /**
         * Handle three-level format merge (e.g., dn1:1.1.1 + dn1:1.1.2)
         * @param {Array} translations - Translation objects array
         * @param {string} sectionUid - Section UID (e.g., 'dn1')
         * @param {string} sectionNumber - Section number (e.g., '1.1.1')
         */
        _handleThreeLevelMerge(translations, sectionUid, sectionNumber) {
            const sectionMainPart = getBeforeLastDot(sectionNumber);
            const sectionLastPart = parseInt(getLastNumber(sectionNumber));
            this.mergee_uid = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;

            let needToMergeNextSection = false;
            let nextSectionFirstKey = '';

            translations.forEach(translation => {
                const newObj = {};

                for (const key in translation.data) {
                    const [keySectionUid, keySectionNumber] = key.split(':');

                    // If it does not match the current section, keep it directly.
                    if (keySectionUid !== sectionUid) {
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    const keyMainPart = getBeforeLastDot(keySectionNumber);
                    const keyLastPart = parseInt(getLastNumber(keySectionNumber));

                    // If it does not match the current subsection, keep it directly.
                    if (keyMainPart !== sectionMainPart) {
                        // If cross-subsection merging is needed, check if it is a paragraph of the target subsection
                        if (needToMergeNextSection) {
                            const [nextChapter, nextSection] = nextSectionFirstKey.split(':')[1].split('.');
                            const [keyChapter, keySection] = keySectionNumber.split('.');

                            if (keyChapter === nextChapter && keySection === nextSection) {
                                this.mergeSectionByNextSubsectionKey(key, translation, newObj);
                                continue;
                            }
                        }
                        newObj[key] = translation.data[key];
                        continue;
                    }

                    // Process the paragraph of the current subsection
                    if (keyLastPart < sectionLastPart) {
                        // Paragraphs before the merge point remain unchanged.
                        newObj[key] = translation.data[key];
                    } else if (keyLastPart === sectionLastPart) {
                        // Merge point: merge current paragraph with next one
                        const nextKey = `${sectionUid}:${sectionMainPart}${sectionLastPart + 1}`;

                        if (translation.data[nextKey]) {
                            // The next paragraph within the same subsection exists
                            newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                        } else {
                            // Try to merge across subsections
                            const [chapter, section] = sectionNumber.split('.');
                            const nextSection = parseInt(section) + 1;
                            const crossSubsectionNextKey = `${sectionUid}:${chapter}.${nextSection}.1`;

                            if (translation.data[crossSubsectionNextKey]) {
                                this.mergee_uid = crossSubsectionNextKey;
                                nextSectionFirstKey = crossSubsectionNextKey;
                                needToMergeNextSection = true;
                                newObj[key] = `${translation.data[key]} ${translation.data[crossSubsectionNextKey]}`;
                            } else {
                                // No mergeable paragraph exists, keep it unchanged
                                newObj[key] = translation.data[key];
                            }
                        }
                    } else {
                        // Paragraphs after the merge point: shift down by decrementing the number
                        const nextKey = `${sectionUid}:${sectionMainPart}${keyLastPart + 1}`;
                        if (translation.data[nextKey]) {
                            newObj[key] = translation.data[nextKey];
                        }
                        // If no next key exists, this paragraph is deleted (merged into previous)
                    }
                }

                translation.data = newObj;
                translation.splitting = true;
            });
        },
        mergeSectionByNextKey(key, translation, newObj) {
            let nextSectionKeySectionUid = key.split(':')[0];
            let nextSectionKeySectionNumber = key.split(':')[1];
            let nextSectionKeyIntegerPart = nextSectionKeySectionNumber.split('.')[0];
            let nextSectionKeyDecimalPart = nextSectionKeySectionNumber.split('.')[1];
            let nextKey = nextSectionKeySectionUid + ':' + nextSectionKeyIntegerPart + '.' + (parseInt(nextSectionKeyDecimalPart) + 1);
            if (translation.data[nextKey]) {
                newObj[key] = translation.data[nextKey];
            }
        },
        mergeSectionByNextSubsectionKey(key, translation, newObj) {
            let nextSectionKeySectionUid = key.split(':')[0];
            let nextSectionKeySectionNumber = key.split(':')[1];
            let SectionNumberParts = nextSectionKeySectionNumber.split('.');
            let nextKey = nextSectionKeySectionUid + ':' + SectionNumberParts[0] + '.' + SectionNumberParts[1] + '.' + (parseInt(SectionNumberParts[2]) + 1);
            if (translation.data[nextKey]) {
                newObj[key] = translation.data[nextKey];
            }
        },
        cancelMerge(translations) {
            this._restoreTranslations();
        },
        isMergeHighlightedRow(uid) {
            return this.merger_uid === uid || this.mergee_uid === uid;
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
                } catch (error) {
                    throw new Error(error);
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
                } catch (error) {
                    throw new Error(error);
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
                if (!data.data) {
                    throw new Error("Invalid data format from the API");
                }
                return data;
            } catch (error) {
                throw new Error(error);
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
                throw new Error(error);
            }
        },
        async handleEnter(event, uid, segment, translation, originalValue = '') {
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

                // Save only when content is modified.
                if (segment !== originalValue) {
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
                        throw new Error(error);
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
                throw new Error(error);
            }
        },
        async updateHandler(muid, data, element, btnId='btn-translation-commit') {
            const badgeId = `translation-badge-${muid}-${Object.keys(data)[0]}`;
            if (Object.keys(data).length === 1) {
                hideBadge(badgeId);
            }
            try {
                displayBadge(badgeId, BadgeStatus.PENDING);
                const response = await requestWithTokenRetry(`projects/${muid}/${this.prefix}/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(data),
                });
                if (!response.ok) {
                    const body = await response.json().catch(() => null);
                    throw new Error(body?.detail ?? `Server error (${response.status})`);
                }
                const { task_id: taskID } = await response.json();
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
                throw new Error(error);
            }
        },
        async updateHandlerForSplit(muid, prefix, element) {
            try {
                let payload = {
                    muid: muid,
                    prefix: prefix,
                    splitter_uid: this.splitter_uid,
                }
                const response = await requestWithTokenRetry(`projects/split/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!response.ok) {
                    const body = await response.json().catch(() => null);
                    let errorMessage = `Server error (${response.status})`;
                    if (body?.detail) {
                        errorMessage = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
                    }
                    throw new Error(errorMessage);
                }
                const result = await response.json();
                await this.refreshHtmlProjectAfterSplitMerge(prefix);
                this._commitSplitMergeOperation();

                const publishModeByPath = this._buildSplitMergePublishModeMap(result);
                const affectedFiles = [
                    this._buildAffectedFile(result.path, muid, 'main', publishModeByPath),
                    ...(result.affected || []).map(a => this._buildAffectedFile(a.path, a.muid, 'related', publishModeByPath))
                ];

                return {
                    affectedFiles,
                    prefix,
                    autoPublishedPaths: result.auto_published_paths || [],
                    manualPublishPaths: result.manual_publish_paths || [],
                    autoPublishTaskId: result.auto_publish_task_id || null,
                };
            } catch (error) {
                throw error;
            }
        },
        async updateHandlerForMerge(muid, prefix, element) {
            try {
                let payload = {
                    muid: muid,
                    prefix: prefix,
                    merger_uid: this.merger_uid,
                    mergee_uid: this.mergee_uid,
                }
                const response = await requestWithTokenRetry(`projects/merge/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                if (!response.ok) {
                    const body = await response.json().catch(() => null);
                    let errorMessage = `Server error (${response.status})`;
                    if (body?.detail) {
                        errorMessage = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
                    }
                    throw new Error(errorMessage);
                }
                const result = await response.json();
                await this.refreshHtmlProjectAfterSplitMerge(prefix);
                this._commitSplitMergeOperation();

                const publishModeByPath = this._buildSplitMergePublishModeMap(result);
                const affectedFiles = [
                    this._buildAffectedFile(result.path, muid, 'main', publishModeByPath),
                    ...(result.affected || []).map(a => this._buildAffectedFile(a.path, a.muid, 'related', publishModeByPath))
                ];

                return {
                    affectedFiles,
                    prefix,
                    autoPublishedPaths: result.auto_published_paths || [],
                    manualPublishPaths: result.manual_publish_paths || [],
                    autoPublishTaskId: result.auto_publish_task_id || null,
                };
            } catch (error) {
                throw error;
            }
        },
        _buildSplitMergePublishModeMap(result) {
            const publishModeByPath = new Map();
            for (const path of result.auto_published_paths || []) {
                publishModeByPath.set(path, 'auto');
            }
            for (const path of result.manual_publish_paths || []) {
                publishModeByPath.set(path, 'manual');
            }
            return publishModeByPath;
        },
        _buildAffectedFile(path, muid, type, publishModeByPath) {
            return {
                path,
                muid,
                type,
                publishMode: publishModeByPath.get(path) || 'manual',
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
                throw new Error(error);
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
            const index = this.translations.findIndex(t => t.muid === project);
            if (index > -1) {
                this.translations.splice(index, 1);
                const saved = this.getSavedRelatedProjects().filter(p => p !== project);
                this.saveRelatedProjects(saved);
            } else {
                try {
                    await this.findOrCreateObject(project, this.prefix);
                    const saved = this.getSavedRelatedProjects();
                    if (!saved.includes(project)) {
                        saved.push(project);
                        this.saveRelatedProjects(saved);
                    }
                } catch (error) {
                    throw new Error(error);
                }
            }
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
    const regex = /:([0-9]+(\.[0-9]+)?)$/;
    const sectionRegex = /:[0-9]+\.[0-9]+\.[0-9]+$/;

    return (regex.test(uid) || sectionRegex.test(uid));
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
