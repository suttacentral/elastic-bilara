function tree() {
    return {
        loading: false,
        showAllContent: false,
        filterUsername: "",
        data: [],
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
            const { base, directories, files } = await response.json();
            for (const directory of directories) {
                element.add(new Element(directory, base, false, false));
            }
            for (const file of files) {
                element.add(new Element(file, base, false, true));
            }
        },
        async open(element) {
            if (element.children.length) {
                return (element.isOpen = true);
            }
            await this.addData(element);
            element.isOpen = true;
        },
        render(element) {
            if (!element) {
                return this.data.map(dir => this.render(dir)).join("");
            }
            let result = `<li class="navigation-list__item">
                <a x-bind:href="${element.isFile} ? await calcUrl('${element.fullName}', '${element.muid}', '${element.prefix}') : '#'"
                    onclick="event.preventDefault();"
                    class="navigation-list__item-link"
                    :class="{'navigation-list--open':${element.isOpen}}"
                    x-on:click.prevent="itemClicked('${element.fullName}')"><i x-data="{isFile: ${
                        element.isFile
                    }}" class="mdi"
                    :class="{'mdi-file-outline': isFile, 'mdi-folder-outline': !isFile && !${
                        element.isOpen
                    },'mdi-folder-open-outline': ${element.isOpen} && !isFile}"></i> ${element.name.split("/").join("")}
                </a>`;
            if (element.muid && element.children.some(child => child.isFile) && !element.isFile) {
                result += `<button class="btn btn--publish" x-on:click="await triggerPullRequest('${
                    element.fullName
                }')">Publish ${element.name.split("/").join("")}</button>`;
            }
            if (element.isOpen && !element.isFile) {
                result += `<ul class="navigation-list">${element.children
                    .map(child => this.render(child))
                    .join("")}</ul>`;
            }
            result += "</li>";
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

        async triggerPullRequest(name) {
            this.loading = true;
            const element = this.getElementByName(name);
            const names = await this.getNames(element);
            const fullPaths = names.map(name => `/app/checkouts/unpublished/${name}`);
            const pathsString = JSON.stringify(fullPaths).replace(/"/g, "&quot;");
            const modalHtml = getPullRequestModalHTML(pathsString);
            this.loading = false;
            document.body.insertAdjacentHTML("beforeend", modalHtml);
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
    }

    add(child) {
        this.children.push(child);
    }
}
