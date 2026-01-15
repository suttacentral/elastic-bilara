function tree() {
    return {
        loading: false,
        showAllContent: false,
        filterUsername: "",
        data: [],
        // Publish Modal State
        showPublishModal: false,
        publishingFile: null,
        isPublishing: false,
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
            this.data = [];
            this.init();
        },
        async addData(element) {
            const response = await requestWithTokenRetry(`directories/${element.fullName}`);
            const { base, directories, files, files_with_progress } = await response.json();
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
        async open(element) {
            element.loading = true;
            element.isOpen = true;

            if (!element.children.length) {
                await this.addData(element);
            }
            element.loading = false;
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
                result += `<button class="btn btn--publish" x-on:click="openPublishModal('${element.fullName}')">Publish</button>`;
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

            // this.isPublishing = true;
            // try {
            //     const response = await fetch('pr/', {
            //         credentials: 'include',
            //         method: 'POST',
            //         headers: {
            //             'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
            //             'Content-Type': 'application/json'
            //         },
            //         body: JSON.stringify({ paths: pathsToPublish })
            //     });

            //     if (!response.ok) {
            //         const errorData = await response.json();
            //         this.showToast(`Error: ${errorData.detail?.error || errorData.detail || 'Failed to publish file'}`, 'error');
            //     } else {
            //         console.log('Publish request sent successfully');
            //         const fileCount = pathsToPublish.length;
            //         this.showToast(`Pull Request scheduled for ${fileCount} modified file(s)`, 'success');
            //     }
            // } catch (error) {
            //     console.error('Error publishing file:', error);
            //     this.showToast(`Error: ${error.message}`, 'error');
            // } finally {
            //     this.isPublishing = false;
            //     this.closePublishModal();
            // }
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
