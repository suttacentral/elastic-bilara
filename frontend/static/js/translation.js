function fetchTranslation() {
    return {
        translations: [],
        relatedProjects: [],
        htmlProjectName: '',
        htmlProject: null,
        originalTranslations: null,
        splitter_uid: null,
        merger_uid: null,
        mergee_uid: null,
        async init() {
            const params = new URLSearchParams(window.location.search);
            this.prefix = params.get("prefix");
            const muid = params.get("muid");
            const source = params.get("source");

            await this.findOrCreateObject(source, this.prefix, true);
            if (muid) {
                await this.findOrCreateObject(muid, this.prefix);
            }
            const projects = await this.fetchRelatedProjects(this.prefix);
            this.relatedProjects = projects.filter(project => project !== muid && project !== source);

            this.htmlProjectName = projects.find(project => project.includes('html'));
            if (this.htmlProjectName) {
                this.htmlProject = await this.createObject(this.htmlProjectName, this.prefix);
            }
        },
        getValue(translation, uid) {
            return translation.data[uid] || "";
        },
        setValue(translation, uid, value) {
            if (!translation.data) {
                translation.data = {};
            }
            translation.data[uid] = value;
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
            }
        },
        hasActiveOperation() {
            return this.originalTranslations !== null;
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

            if (localStorage.getItem('displayButtonForSplitOrMerge') === null) {
                localStorage.setItem('displayButtonForSplitOrMerge', 'true');
            }

            if (localStorage.getItem('enableSplitHintDialog') === null) {
                localStorage.setItem('enableSplitHintDialog', 'true');
            }

            if (localStorage.getItem('enableSplitHintDialog') === "true") {
                document.querySelector('.dialog-split-hint')?.show();
            }

            this._backupTranslations();

            if (this.htmlProjectName) {
                const existingProject = this.translations.find(project => project.muid === this.htmlProjectName);
                if (!existingProject) {
                    this.translations.push(this.htmlProject);
                }
            }

            const [sectionUid, sectionNumber] = uid.split(':');
            const isTwoLevelFormat = /^[0-9]+\.[0-9]+$/.test(sectionNumber);
            const isThreeLevelFormat = /[0-9]+\.[0-9]+\.[0-9]+$/.test(sectionNumber);

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
            localStorage.setItem('displayButtonForSplitOrMerge', 'false');
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
            this.originalTranslations = JSON.parse(JSON.stringify(translations));
            if (this.htmlProjectName) {
                const existingProject = this.translations.find(project => project.muid === this.htmlProjectName);
                if (!existingProject) {
                    this.translations.push(this.htmlProject);
                }
            }

            if (localStorage.getItem('displayButtonForSplitOrMerge') === null) {
                localStorage.setItem('displayButtonForSplitOrMerge', 'true');
            }

            if (localStorage.getItem('enableMergeHintDialog') === null) {
                localStorage.setItem('enableMergeHintDialog', true);
            }

            if (localStorage.getItem('enableMergeHintDialog') === "true") {
                document.querySelector('.dialog-merge-hint')?.show();
            }

            const [sectionUid, sectionNumber] = uid.split(':');
            const regex = /:([0-9]+(\.[0-9]+)?)$/;
            // Two-level format: mn1:1.1
            if (regex.test(uid) && countChar(uid.split(':')[1], '.') === 1) {
                this._handleTwoLevelMerge(translations, sectionUid, sectionNumber);
            }
            // Three-level format: dn1:1.1.1
            else {
                const sectionRegex = /^:[0-9]+\.[0-9]+\.[0-9]+$/;
                if (sectionRegex.test(uid)) {
                    this._handleThreeLevelMerge(translations, sectionUid, sectionNumber);
                }
            }
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

            this.translations.forEach(translation => {
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
            nextKey = nextSectionKeySectionUid + ':' + nextSectionKeyIntegerPart + '.' + (parseInt(nextSectionKeyDecimalPart) + 1);
            if (translation.data[nextKey]) {
                newObj[key] = translation.data[nextKey];
            }
        },
        mergeSectionByNextSubsectionKey(key, translation, newObj) {
            let nextSectionKeySectionUid = key.split(':')[0];
            let nextSectionKeySectionNumber = key.split(':')[1];
            let SectionNumberParts = nextSectionKeySectionNumber.split('.');
            nextKey = nextSectionKeySectionUid + ':' + SectionNumberParts[0] + '.' + SectionNumberParts[1] + '.' + (parseInt(SectionNumberParts[2]) + 1);
            if (translation.data[nextKey]) {
                newObj[key] = translation.data[nextKey];
            }
        },
        cancelMerge(translations) {
            this._restoreTranslations();
            localStorage.setItem('displayButtonForSplitOrMerge', 'false');
        },
        redirectToHtml() {
            const params = new URLSearchParams(window.location.search);
            const prefix = params.get("prefix");
            const muid = 'html-pli-ms';
            const source = params.get("source");
            return (window.location.href = `/translation?prefix=${prefix}&muid=${muid}&source=${source}`);
        },
        async findOrCreateObject(key, prefix, source = false) {
            let obj = this.translations.find(item => key in item);
            if (!obj) {
                try {
                    const data = await this.fetchData(key, prefix);
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
            let obj = this.translations.find(item => key in item);
            if (!obj) {
                try {
                    const data = await this.fetchData(key, prefix);
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
        async handleEnter(event, uid, segment, translation) {
            if (translation.canEdit) {
                if (event.shiftKey) {
                    event.target.value += "\n";
                    return;
                }
                const nextSection = event.target.parentElement.nextElementSibling;
                if (nextSection) {
                    const nextTextarea = nextSection.querySelector("textarea");
                    if (nextTextarea) {
                        nextTextarea.focus();
                    }
                }
                try {
                    const muid = translation.muid;
                    await this.updateHandler(
                        muid,
                        { [uid]: segment },
                        document.querySelector("p.project-header__message"),
                    );
                } catch (error) {
                    throw new Error(error);
                }
            }
        },
        async updateHandler(muid, data, element, btnId='btn-translation-commit') {
            const badgeId = `translation-badge-${muid}-${Object.keys(data)[0]}`;
            if (Object.keys(data).length === 1) {
                hideBadge(badgeId);
                insertSpinner(badgeId);
            } else {
                addLoadingAttribute(btnId);
            }
            addLoadingAttribute(btnId);
            try {
                const response = await requestWithTokenRetry(`projects/${muid}/${this.prefix}/`, {
                    credentials: "include",
                    method: "PATCH",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(data),
                });
                const { task_id: taskID } = await response.json();
                if (!taskID) {
                    displayMessage(
                        element,
                        "There has been an error. Please retry in a few moments. If the issue persists, please contact the administrator.",
                        "failure",
                    );
                }
                if (Object.keys(data).length > 1) {
                    displayMessage(
                        element,
                        "Your changes have reached the server. They are being processed at the moment. This may take some time. Please continue your work as normal.",
                    );
                }
                if (Object.keys(data).length === 1) {
                    removeSpinner();
                    displayBadge(badgeId, BadgeStatus.COMMITTED);
                }
            } catch (error) {
                displayBadge(badgeId, BadgeStatus.ERROR);
                throw new Error(error);
            } finally {
                removeLoadingAttribute(btnId);
            }
        },
        async updateHandlerForSplit(muid, prefix, element) {
            try {
                payload = {
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
                const { task_id: taskID } = await response.json();
                if (!taskID) {
                    displayMessage(
                        element,
                        "There has been an error. Please retry in a few moments. If the issue persists, please contact the administrator.",
                        "failure",
                    );
                }

                localStorage.setItem('displayButtonForSplitOrMerge', 'true');

                displayMessage(
                    element,
                    "Your changes have reached the server. They are being processed at the moment. This may take some time. Please continue your work as normal.",
                );

                this.redirectToHtml();
            } catch (error) {
                throw new Error(error);
            }
        },
        async updateHandlerForMerge(muid, prefix, element) {
            try {
                payload = {
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
                const { task_id: taskID } = await response.json();
                if (!taskID) {
                    displayMessage(
                        element,
                        "There has been an error. Please retry in a few moments. If the issue persists, please contact the administrator.",
                        "failure",
                    );
                }

                localStorage.setItem('displayButtonForSplitOrMerge', 'true');

                displayMessage(
                    element,
                    "Your changes have reached the server. They are being processed at the moment. This may take some time. Please continue your work as normal.",
                );

                this.redirectToHtml();
            } catch (error) {
                throw new Error(error);
            }
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
        async toggleRelatedProject(project) {
            const index = this.translations.findIndex(t => t.muid === project);
            if (index > -1) {
                this.translations.splice(index, 1);
            } else {
                try {
                    await this.findOrCreateObject(project, this.prefix);
                } catch (error) {
                    throw new Error(error);
                }
            }
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
