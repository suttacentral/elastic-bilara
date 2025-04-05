function fetchTranslation() {
    return {
        translations: [],
        relatedProjects: [],
        htmlProjectName: '',
        htmlProject: null,
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
        async splitBasedOnUid(translations, uid, element) {
            this.OriginalTranslations = JSON.parse(JSON.stringify(translations));
            if (this.htmlProjectName) {
                const existingProject = this.translations.find(project => project.muid === this.htmlProjectName);
                if (!existingProject) {
                    this.translations.push(this.htmlProject);
                }
            }

            if (!isMergeSplitConditionMet(uid)) {
                displayMessage(
                    element,
                    "This type of uid does not support splitting."
                );
                return false;
            }

            const [sectionUid, sectionNumber] = uid.split(':');
            const isTwoLevelFormat = countChar(sectionNumber, '.') === 1;
            const isThreeLevelFormat = /[0-9]+\.[0-9]+\.[0-9]+$/.test(sectionNumber);

            // Processing two-level format: mn1:1.1
            if (isTwoLevelFormat) {
                const [integerPart, decimalPart] = sectionNumber.split('.');
                this.splitter_uid = `${sectionUid}:${integerPart}.${parseInt(decimalPart) + 1}`;

                translations.forEach(translation => {
                    let newObj = {};

                    for (let key in translation.data) {
                        const [keySectionUid, keySectionNumber] = key.split(':');
                        const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');

                        if (keySectionUid === sectionUid && keyIntegerPart === integerPart && keyDecimalPart === decimalPart) {
                            // The current paragraph to be split
                            newObj[key] = translation.data[key];
                            const newKey = `${sectionUid}:${integerPart}.${parseInt(decimalPart) + 1}`;
                            newObj[newKey] = "";
                        } else if (keySectionUid === sectionUid && keyIntegerPart === integerPart && parseInt(keyDecimalPart) >= parseInt(decimalPart) + 1) {
                            // The paragraph after the split point needs to be moved
                            const newKey = `${sectionUid}:${integerPart}.${parseInt(keyDecimalPart) + 1}`;
                            newObj[newKey] = translation.data[key];
                        } else {
                            // Unaffected paragraphs
                            newObj[key] = translation.data[key];
                        }
                    }
                    translation.data = newObj;
                });
            }

            // Processing level 3 format: dn1:1.1.1
            else if (isThreeLevelFormat) {
                const sectionMainPart = getBeforeLastDot(sectionNumber);
                const sectionLastPart = getLastNumber(sectionNumber);
                this.splitter_uid = `${sectionUid}:${sectionMainPart}${parseInt(sectionLastPart) + 1}`;
                translations.forEach(translation => {
                    let newObj = {};
                    for (let key in translation.data) {
                        const [keySectionUid, keySectionNumber] = key.split(':');
                        const keyMainPart = getBeforeLastDot(keySectionNumber);
                        const keyLastPart = getLastNumber(keySectionNumber);
                        if (keySectionUid === sectionUid && keyMainPart === sectionMainPart && keyLastPart === sectionLastPart) {
                            // The current paragraph to be split
                            newObj[key] = translation.data[key];
                            const newKey = `${sectionUid}:${sectionMainPart}${parseInt(sectionLastPart) + 1}`;
                            newObj[newKey] = "";
                        } else if (keySectionUid === sectionUid && keyMainPart === sectionMainPart && parseInt(keyLastPart) >= parseInt(sectionLastPart) + 1) {
                            // The paragraph after the split point needs to be moved
                            const newKey = `${sectionUid}:${sectionMainPart}${parseInt(keyLastPart) + 1}`;
                            newObj[newKey] = translation.data[key];
                        } else {
                            // Unaffected paragraphs
                            newObj[key] = translation.data[key];
                        }
                    }
                    translation.data = newObj;
                });
            }
            return true;
        },
        cancelSplit(translations) {
            // this.translations = this.OriginalTranslations;
            window.location.reload();
        },
        mergeBasedOnUid(translations, uid, element) {
            let newObj = {};
            this.merger_uid = uid;
            this.OriginalTranslations = JSON.parse(JSON.stringify(translations));
            if (!isMergeSplitConditionMet(uid)) {
                displayMessage(
                    element,
                    "This type of uid does not support merging.",
                );
                return false;
            }
            const regex = /:([0-9]+(\.[0-9]+)?)$/;
            if (regex.test(uid) && countChar(uid.split(':')[1], '.') === 1) {
                const [sectionUid, sectionNumber] = uid.split(':');
                const [integerPart, decimalPart] = sectionNumber.split('.');
                this.mergee_uid = `${sectionUid}:${integerPart}.${parseInt(decimalPart) + 1}`;

                let needToMergeNextSection = false;
                let nextSectionFirstKey = '';
                this.translations.forEach(translation => {
                    for (let key in translation.data) {
                        const [keySectionUid, keySectionNumber] = key.split(':');
                        const [keyIntegerPart, keyDecimalPart] = keySectionNumber.split('.');
                        if (`${keySectionUid}:${keyIntegerPart}.${keyDecimalPart}` === `${sectionUid}:${integerPart}.${decimalPart}`) {
                            let nextKey = `${sectionUid}:${integerPart}.${parseInt(decimalPart) + 1}`;
                            if (translation.data[nextKey]) {
                                newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                            } else {
                                let nextSectionIntegerPart = `${parseInt(integerPart) + 1}`;
                                possibleNextKey1 = `${sectionUid}:${nextSectionIntegerPart}.0`;
                                possibleNextKey2 = `${sectionUid}:${nextSectionIntegerPart}.1`;
                                nextKey = translation.data[possibleNextKey1] ? possibleNextKey1 : possibleNextKey2;
                                if (translation.data[nextKey]) {
                                    this.mergee_uid = nextKey;
                                    nextSectionFirstKey = nextKey;
                                    needToMergeNextSection = true;
                                    newObj[key] = `${translation.data[key]} ${translation.data[nextKey]}`;
                                } else {
                                    newObj[key] = translation.data[key];
                                }
                            }
                        } else if (keySectionUid === sectionUid && keyIntegerPart === integerPart && keyDecimalPart >= decimalPart+1) {
                            let nextKey = `${uid.split(':')[0]}:${integerPart}.${parseInt(keyDecimalPart) + 1}`;
                            if (translation.data[nextKey]) {
                                newObj[key] = translation.data[nextKey];
                            }
                        } else if (needToMergeNextSection && key.length === nextSectionFirstKey.length && key.split(':')[1].split('.')[0] === nextSectionFirstKey.split(':')[1].split('.')[0]) {
                            this.mergeSectionByNextKey(key, translation, newObj);
                        }
                        else {
                            newObj[key] = translation.data[key];
                        }
                    }
                    translation.data = newObj;
                    translation.splitting = true;
                    newObj = {};
                });
            }

            // patten: dn1:1.1.1
            const sectionRegex = /:[0-9]+\.[0-9]+\.[0-9]+$/;
            if (sectionRegex.test(uid)) {
                const [sectionUid, sectionNumber] = uid.split(':');
                const sectionMainPart = getBeforeLastDot(sectionNumber);
                const sectionLastPart = getLastNumber(sectionNumber);
                this.mergee_uid = `${sectionUid}:${sectionMainPart}.${parseInt(sectionLastPart) + 1}`;
                let needToMergeNextSection = false;
                let nextSectionFirstKey = '';
                translations.forEach(translation => {
                    for (let key in translation.data) {
                        const [keySectionUid, keySectionNumber] = key.split(':');
                        const keyMainPart = getBeforeLastDot(keySectionNumber);
                        const keyLastPart = getLastNumber(keySectionNumber);

                        const [keyChapter, keySection, keySubsection] = keySectionNumber.split('.');

                        if (`${keySectionUid}:${keyMainPart}.${keyLastPart}` === `${sectionUid}:${sectionMainPart}.${sectionLastPart}`) {
                            let nextKey = `${uid.split(':')[0]}:${sectionMainPart}${parseInt(sectionLastPart) + 1}`;
                            if (translation.data[nextKey]) {
                                newObj[key] = translation.data[key] + ' ' + translation.data[nextKey];
                            } else {
                                let SectionNumberParts = sectionNumber.split('.');
                                nextKey = keySectionUid + ':' + SectionNumberParts[0] + '.' + (parseInt(SectionNumberParts[1]) + 1) + '.1';
                                if (translation.data[nextKey]) {
                                    this.mergee_uid = nextKey;
                                    nextSectionFirstKey = nextKey;
                                    needToMergeNextSection = true;
                                    newObj[key] = translation.data[key] + ' ' + translation.data[nextKey];
                                } else {
                                    newObj[key] = translation.data[key];
                                }
                            }
                        } else if (keySectionUid === sectionUid && keyMainPart === sectionMainPart && keyLastPart >= sectionLastPart+1) {
                            let newKey = `${uid.split(':')[0]}:${sectionMainPart}${parseInt(keyLastPart) + 1}`;
                            if (translation.data[newKey]) {
                                newObj[key] = translation.data[newKey];
                            }
                        }  else if (needToMergeNextSection && key.length === nextSectionFirstKey.length && key.split(':')[1].split('.')[0] === nextSectionFirstKey.split(':')[1].split('.')[0]
                            && key.split(':')[1].split('.')[1] === nextSectionFirstKey.split(':')[1].split('.')[1]) {
                            this.mergeSectionByNextSubsectionKey(key, translation, newObj);
                        } else {
                            newObj[key] = translation.data[key];
                        }
                    }
                    translation.data = newObj;
                    newObj = {};
                });
            }
            return true;
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
            this.translations = this.OriginalTranslations;
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

function textareaAdjuster() {
    return {
        observer: null,
        init() {
            const options = { threshold: [0.1] };
            const callback = entries => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const index = entry.target.getAttribute("data-index");
                        const sections = Array.from(
                            document.querySelectorAll(
                                `.project-container__content-body__section[data-index="${index}"]`,
                            ),
                        );
                        setMaxHeight(sections.map(section => section.querySelector("textarea")));
                    }
                });
            };
            this.observer = new IntersectionObserver(callback, options);
            this.observeSections();
        },
        observeSections() {
            const sections = document.querySelectorAll(".project-container__content-body__section");

            sections.forEach(section => {
                if (!this.observer) return;
                this.observer.unobserve(section);
                this.observer.observe(section);
            });
        },
    };
}

function adjustTextareas(element) {
    const parent = element.parentElement;
    const index = parent.getAttribute("data-index");
    const sections = Array.from(
        document.querySelectorAll(`.project-container__content-body__section[data-index="${index}"]`),
    );
    setMaxHeight(sections.map(section => section.querySelector("textarea")));
}

function* generateUniqueVisibleElements() {
    const body = document.querySelector(".project-container__content-body");
    const elements = body.querySelectorAll(".project-container__content-body__section");
    for (const el of elements) {
        if (isInViewPort(el)) {
            yield el;
        } else {
            break;
        }
    }
}

function adjustVisibleTextareas() {
    const uniqueVisibleElements = generateUniqueVisibleElements();
    for (const el of uniqueVisibleElements) {
        adjustTextareas(el.querySelector("textarea"));
    }
}

function moveContentDetails() {
    const contentDetails = Array.from(document.querySelectorAll('.project-container__content-details'));
    const translationTemplate = document.querySelector('#translation-template');
    contentDetails.forEach(detail => {
        translationTemplate.appendChild(detail);
    });
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
