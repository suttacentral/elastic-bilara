function tree() {
    return {
        loading: false,
        showAllContent: false,
        filterUsername: "",
        data: [],
        directoryCache: new Map(),
        cacheTTL: 5 * 60 * 1000,
        maxCacheEntries: 200,
        // Publish Modal State
        showPublishModal: false,
        publishingFile: null,
        isPublishing: false,
        userRole: "",
        async loadAllDirectories() {
            const response = await requestWithTokenRetry("directories/");
            const { directories, base } = await response.json();
            for (const directory of directories) {
                this.data.push(new Element(directory, base, false, false));
            }
        },
        async init() {
            const userInfo = getUserInfo();
            await userInfo.getRole();
            this.filterUsername = userInfo.username;
            this.userRole = userInfo.role;

            if (!this.showAllContent) {
                const response = await requestWithTokenRetry(`directories/search/${this.filterUsername}/`);
                const { matches } = await response.json();

                if (matches.length === 0 || matches.total_matches === 0) {
                    await this.loadAllDirectories();
                    return;
                }

                const rootElementsMap = new Map();
                for (const match of matches) {
                    const pathParts = match.path.split('/').filter(part => part !== '');

                    if (pathParts.length === 0) continue;

                    let currentElement = null;
                    let currentBase = null;

                    for (let i = 0; i < pathParts.length; i++) {
                        const pathPart = pathParts[i] + '/';

                        if (i === 0) {
                            if (!rootElementsMap.has(pathPart)) {
                                const newElement = new Element(pathPart + "/", null, false, false);
                                rootElementsMap.set(pathPart, newElement);
                                this.data.push(newElement);
                            }
                            currentElement = rootElementsMap.get(pathPart);
                            currentBase = pathPart;
                        } else {
                            let childElement = currentElement.children.find(child =>
                                child.name === pathPart + "/"
                            );

                            if (!childElement) {
                                childElement = new Element(pathPart + "/", currentBase, false, false);
                                currentElement.add(childElement);
                            }
                            currentElement = childElement;
                            currentBase = currentBase + "/" + pathPart;
                        }
                    }
                }
            } else {
                await this.loadAllDirectories();
            }
        },
        toggleShowAll() {
            this.showAllContent = !this.showAllContent;
            this.directoryCache.clear();
            this.data = [];
            this.init();
        },
        evictDirectoryCacheIfNeeded() {
            while (this.directoryCache.size > this.maxCacheEntries) {
                const oldestKey = this.directoryCache.keys().next().value;
                this.directoryCache.delete(oldestKey);
            }
        },
        isCacheFresh(cacheEntry) {
            if (!cacheEntry || !cacheEntry.data) {
                return false;
            }
            return Date.now() - cacheEntry.timestamp < this.cacheTTL;
        },
        hasOpenDescendants(element) {
            for (const child of element.children) {
                if (child.isOpen || this.hasOpenDescendants(child)) {
                    return true;
                }
            }
            return false;
        },
        async fetchDirectoryData(fullName, { force = false } = {}) {
            const existing = this.directoryCache.get(fullName);

            if (!force && existing && existing.data) {
                return existing.data;
            }

            if (existing && existing.inflightPromise) {
                return existing.inflightPromise;
            }

            const requestPromise = (async () => {
                const response = await requestWithTokenRetry(`directories/${fullName}`);
                return response.json();
            })();

            this.directoryCache.set(fullName, {
                data: existing ? existing.data : null,
                timestamp: existing ? existing.timestamp : 0,
                inflightPromise: requestPromise,
            });

            try {
                const data = await requestPromise;
                this.directoryCache.set(fullName, {
                    data,
                    timestamp: Date.now(),
                    inflightPromise: null,
                });
                this.evictDirectoryCacheIfNeeded();
                return data;
            } catch (error) {
                this.directoryCache.set(fullName, {
                    data: existing ? existing.data : null,
                    timestamp: existing ? existing.timestamp : 0,
                    inflightPromise: null,
                });
                throw error;
            }
        },
        hydrateElementFromData(element, data) {
            const { base, directories, files, files_with_progress } = data;
            element.children = [];

            for (const directory of directories) {
                element.add(new Element(directory, base, false, false));
            }

            const progressMap = {};
            if (files_with_progress) {
                for (const fp of files_with_progress) {
                    progressMap[fp.name] = fp;
                }
            }

            for (const file of files) {
                const fileElement = new Element(file, base, false, true);

                const progressData = progressMap[file];
                if (progressData) {
                    fileElement.progress = progressData.progress;
                    fileElement.totalKeys = progressData.total_keys || 0;
                    fileElement.translatedKeys = progressData.translated_keys || 0;
                }

                element.add(fileElement);
            }
        },
        async addData(element, { force = false } = {}) {
            const data = await this.fetchDirectoryData(element.fullName, { force });
            this.hydrateElementFromData(element, data);
        },
        async revalidateDirectory(fullName) {
            try {
                const latestData = await this.fetchDirectoryData(fullName, { force: true });
                const target = this.getElementByName(fullName);

                // Avoid clobbering nested interaction if user has opened descendants.
                if (target && target.isOpen && !this.hasOpenDescendants(target)) {
                    this.hydrateElementFromData(target, latestData);
                }
            } catch (error) {
                console.error(`Background refresh failed for ${fullName}:`, error);
            }
        },
        async open(element) {
            element.loading = true;
            element.isOpen = true;

            if (element.children.length) {
                element.loading = false;
                return;
            }

            const cacheEntry = this.directoryCache.get(element.fullName);
            if (this.isCacheFresh(cacheEntry)) {
                this.hydrateElementFromData(element, cacheEntry.data);
                element.loading = false;
                return;
            }

            if (cacheEntry && cacheEntry.data) {
                // Stale-while-revalidate: show stale data immediately, refresh in background.
                this.hydrateElementFromData(element, cacheEntry.data);
                element.loading = false;
                this.revalidateDirectory(element.fullName);
                return;
            }

            try {
                await this.addData(element);
            } finally {
                element.loading = false;
            }
        },
        renderNode(element) {
            if (!element) return "";

            // Render node links
            let result = `
                <a href="#"
                    class="navigation-list__item-link ${element.isOpen ? 'navigation-list--open' : ''}"
                    onclick="event.preventDefault();"
                    x-on:click.prevent="itemClicked('${element.fullName}')">
                    <i class="mdi ${element.isFile ? 'mdi-file-outline' : (element.isOpen ? 'mdi-folder-open-outline' : 'mdi-folder-outline')}"></i>
                    ${element.name.split("/").join("")}
                </a>`;

            const isTranslationFile = element.fullName && element.fullName.startsWith('translation/');
            if (element.isFile && isTranslationFile && element.progress !== null && element.progress >= 0) {
                const progressClass = element.progress >= 90 ? 'high' : (element.progress >= 50 ? 'medium' : 'low');
                result += `<span class="translation-progress ${progressClass}" title="${element.progress}% translated (${element.translatedKeys}/${element.totalKeys})">
                    <span class="progress-bar" style="width: ${element.progress}%"></span>
                    <span class="progress-text">${element.progress}%</span>
                </span>`;
            }

            if (element.muid && (element.fullName.split('/').length >= 5 || element.isFile)) {
                let showPublish = false;
                if (this.userRole === ROLES.admin || this.userRole === ROLES.superuser) {
                    showPublish = true;
                } else if (this.userRole === ROLES.writer) {
                    showPublish = element.fullName.includes(this.filterUsername);
                }
                if (showPublish) {
                    result += `<button class="btn btn--publish" x-on:click="openPublishModal('${element.fullName}')">Publish</button>`;
                }
            }

            if (element.loading) {
                result += `<div class="node-loading"><div class="spinner-small"></div></div>`;
            }

            // Render child nodes (only when expanded and not a file)
            if (element.isOpen && !element.isFile && element.children.length) {
                result += `<ul class="navigation-list">`;
                for (const child of element.children) {
                    result += `<li class="navigation-list__item">${this.renderNode(child)}</li>`;
                }
                result += `</ul>`;
            }

            return result;
        },
        itemClicked(name) {
            const element = this.getElementByName(name);
            if (element) {
                if (element.isFile) {
                    return this.redirectToFile(element);
                }
                element.isOpen ? this.close(element) : this.open(element);
            }
        },
        async getNames(element) {
            let nameList = [];

            if (!element.children.length) {
                await this.addData(element);
            }

            for (const child of element.children) {
                if (child.isFile) {
                    nameList.push(child.fullName);
                }
            }
            return nameList;
        },

        openPublishModal(name) {

            this.publishingFile = name;
            this.showPublishModal = true;
        },

        closePublishModal() {
            this.showPublishModal = false;
            this.publishingFile = null;
        },

        async confirmPublish() {
            if (!this.publishingFile) return;

            const element = this.getElementByName(this.publishingFile);
            if (!element) {
                this.showToast(`Error: Cannot find element for ${this.publishingFile}`, 'error');
                return;
            }

            const modifiedFiles = await this.getModifiedFiles();
            if (modifiedFiles.length === 0) {
                this.showToast('No modified files found in the repository', 'error');
                return;
            }

            let pathsToPublish = [];
            if (element.isFile) {
                // If it's a file, check if the file is in the modified list
                if (modifiedFiles.includes(this.publishingFile)) {
                    pathsToPublish = [this.publishingFile];
                }
            } else {
                // If it's a directory, filter all modified files under this directory
                const dirPrefix = this.publishingFile;
                pathsToPublish = modifiedFiles.filter(filePath => filePath.startsWith(dirPrefix));
            }

            if (pathsToPublish.length === 0) {
                this.showToast('No modified files to publish in this location', 'error');
                return;
            }

            // Group files by project head so each PR only contains files from one project
            const groupByProject = (paths) => {
                const groups = {};
                for (const path of paths) {
                    const parts = path.split('/').filter(Boolean);
                    const dirParts = parts.slice(0, -1);
                    let head;
                    if (dirParts.length === 6 && !dirParts[dirParts.length - 2].includes(dirParts[dirParts.length - 3])) {
                        head = dirParts.slice(0, -1).join('_');
                    } else if (dirParts.length > 6 && dirParts[dirParts.length - 3] && dirParts[dirParts.length - 2].includes(dirParts[dirParts.length - 3])) {
                        head = dirParts.slice(0, -2).join('_');
                    } else {
                        head = dirParts.join('_');
                    }
                    if (!groups[head]) groups[head] = [];
                    groups[head].push(path);
                }
                return Object.values(groups);
            };

            const fileGroups = groupByProject(pathsToPublish);
            const totalGroups = fileGroups.length;

            this.isPublishing = true;
            let successCount = 0;
            let errorMessages = [];

            try {
                for (const groupPaths of fileGroups) {
                    try {
                        const response = await requestWithTokenRetry('pr/', {
                            credentials: 'include',
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ paths: groupPaths })
                        });
                        if (!response.ok) {
                            const errorData = await response.json();
                            errorMessages.push(errorData.detail?.error || errorData.detail || `HTTP ${response.status}`);
                        } else {
                            successCount++;
                        }
                    } catch (err) {
                        errorMessages.push(err.message);
                    }
                }

                if (errorMessages.length === 0) {
                    this.showToast(
                        `Pull Request${totalGroups > 1 ? 's' : ''} scheduled for ${pathsToPublish.length} file(s)`,
                        'success'
                    );
                } else {
                    const succeeded = successCount > 0 ? `${successCount}/${totalGroups} succeeded. ` : '';
                    this.showToast(`${succeeded}Errors: ${errorMessages.join('; ')}`, 'error');
                }
            } catch (error) {
                console.error('Error publishing:', error);
                this.showToast(`Error: ${error.message}`, 'error');
            } finally {
                this.isPublishing = false;
                this.closePublishModal();
            }
        },

        showToast(message, type = 'success') {
            const toast = document.querySelector('sc-bilara-toast');
            if (toast) {
                toast.show(message, type);
            }
        },

        async getModifiedFiles() {
            try {
                const response = await requestWithTokenRetry('git/status');
                if (!response.ok) {
                    console.error('Failed to fetch git status');
                    return [];
                }
                const data = await response.json();
                return data.files.map(file => file.path);
            } catch (error) {
                console.error('Error fetching git status:', error);
                return [];
            }
        },

        reviewPublish() {
            if (this.publishingFile) {
                window.open(`git_status_panel.html?filter=${encodeURIComponent(this.publishingFile)}`, '_blank');
                this.closePublishModal();
            }
        },

        getElementByName(name) {
            let result = null;

            function search(query, collection) {
                collection.forEach(item => {
                    if (item.fullName === query) {
                        result = item;
                    } else if (item.children.length && result === null) {
                        search(query, item.children);
                    }
                });
            }

            search(name, this.data);
            return result;
        },
        async redirectToFile(element) {
            const response = await requestWithTokenRetry(`projects/${element.fullName}/source/`);
            const { muid: source } = await response.json();
            const muid = element.muid === source ? "" : element.muid;
            return (window.location.href = `/translation?prefix=${element.prefix}&muid=${muid}&source=${source}`);
        },
        close(element) {
            element.isOpen = false;
        },

        async calcUrl(elementFullName, elementMuid, elementPrefix) {
            if (elementFullName.includes("name")) {
                return '#';
            }

            const response = await requestWithTokenRetry(`projects/${elementFullName}/source/`);
            const { muid: source } = await response.json();
            const muid = elementMuid === source ? "" : elementMuid;
            return `/translation?prefix=${elementPrefix}&muid=${muid}&source=${source}`;
        },

        async fetchProgress(element) {
            if (!element.isFile) return;
            try {
                const response = await requestWithTokenRetry(`projects/${element.fullName}/translation-progress/`);
                if (response.ok) {
                    const data = await response.json();
                    element.progress = data.progress;
                    element.totalKeys = data.total_keys;
                    element.translatedKeys = data.translated_keys;
                    this.updateProgressInDOM(element);
                } else {
                    element.progress = -1;
                }
            } catch (error) {
                console.error('Error fetching progress:', error);
                element.progress = -1;
            }
        },

        updateProgressInDOM(element) {
            const links = document.querySelectorAll('.navigation-list__item-link');
            for (const link of links) {
                if (link.textContent.trim().includes(element.name.split("/").join("").trim())) {
                    const listItem = link.closest('.navigation-list__item');
                    if (!listItem) continue;

                    let progressSpan = listItem.querySelector('.translation-progress');

                    if (element.progress !== null && element.progress >= 0) {
                        const progressClass = element.progress >= 90 ? 'high' : (element.progress >= 50 ? 'medium' : 'low');
                        const progressHTML = `<span class="translation-progress ${progressClass}" title="${element.progress}% translated (${element.translatedKeys}/${element.totalKeys})">
                            <span class="progress-bar" style="width: ${element.progress}%"></span>
                            <span class="progress-text">${element.progress}%</span>
                        </span>`;

                        if (progressSpan) {
                            progressSpan.outerHTML = progressHTML;
                        } else {
                            link.insertAdjacentHTML('afterend', progressHTML);
                        }
                    }
                    break;
                }
            }
        }
    };
}

class Element {
    constructor(name, base, isOpen, isFile) {
        this.name = name;
        this.base = base;
        this.fullName = this.base === null ? this.name : this.base + this.name;
        this.isOpen = isOpen;
        this.isFile = isFile;
        this.muid = this.fullName.split("/").length > 3 ? getMuid(this.fullName) : null;
        this.prefix = this.isFile ? getPrefix(this.name) : null;
        this.children = [];
        this.progress = null;  // null = loading, -1 = error, 0-100 = actual progress
        this.totalKeys = 0;
        this.translatedKeys = 0;
        this.loading = false;  // Node loading state
    }

    add(child) {
        this.children.push(child);
    }
}
