function fileTree() {
    return {
        levels: [],
        paths: {},
        loading: false,
        async init() {
            this.loading = true;
            try {
                const response = await requestWithTokenRetry("projects/?prefix=translation");
                const data = await response.json();

                if (!data.projects) {
                    throw new Error("Invalid data format from the API");
                }

                function addPathToStructure(path, currentLevel, fullProjectPath) {
                    const parts = path.split("-").filter(p => p);

                    if (parts.length === 1) {
                        currentLevel.push({
                            title: parts[0],
                            children: [],
                            muid: fullProjectPath,
                            author: fullProjectPath,
                        });
                        return;
                    }

                    let existingDir = currentLevel.find(dir => dir.title === parts[0]);

                    if (!existingDir) {
                        existingDir = {
                            title: parts[0],
                            children: [],
                            author: fullProjectPath,
                        };
                        currentLevel.push(existingDir);
                    }

                    addPathToStructure(parts.slice(1).join("-"), existingDir.children, fullProjectPath);
                }

                const structure = [];
                for (const project of data.projects) {
                    addPathToStructure(project, structure, project);
                }
                this.levels = structure;
            } catch (error) {
                throw new Error(error);
            } finally {
                this.loading = false;
            }
        },
        async rootPaths(muid) {
            this.loading = true;
            try {
                const response = await requestWithTokenRetry(`projects/${muid}/`);
                const data = await response.json();

                if (!data.paths) {
                    throw new Error("Invalid data format from the API");
                }

                const paths = data.paths.map(
                    path => `/${muid.replaceAll("-", "/")}${path.replace(/^.*unpublished\/[^\/]+/, "")}`,
                );

                function addOrUpdatePathInStructure(path, currentLevel) {
                    const parts = path.split("/").filter(p => p);

                    if (parts.length === 1) {
                        let existingItem = currentLevel.find(item => item.title === parts[0]);
                        if (!existingItem) {
                            const objToAdd = { title: parts[0], author: muid };
                            if (parts[0].endsWith(".json")) {
                                currentLevel.push(objToAdd);
                            } else {
                                objToAdd.children = [];
                                currentLevel.push(objToAdd);
                            }
                        }
                        return;
                    }

                    let existingDir = currentLevel.find(dir => dir.title === parts[0]);

                    if (!existingDir) {
                        existingDir = { title: parts[0], children: [], author: muid };
                        currentLevel.push(existingDir);
                    }
                    addOrUpdatePathInStructure(parts.slice(1).join("/"), existingDir.children);
                }

                for (const path of paths) {
                    addOrUpdatePathInStructure(path, this.levels);
                }
            } catch (error) {
                throw new Error(error);
            } finally {
                this.loading = false;
            }
        },
        renderLevel(obj, i) {
            const ref = "l" + Math.random().toString(36).substring(7);
            const isJsonFile = obj.title.endsWith(".json");

            let clickAction;

            if (isJsonFile) {
                const source = encodeURIComponent(obj.title.split("_")[1].replace(".json", ""));
                const prefix = encodeURIComponent(obj.title.split("_")[0]);
                const muid = encodeURIComponent(obj.author);
                clickAction = `window.location.href='/translation?prefix=${prefix}&muid=${muid}&source=${source}'`;
            } else if (obj.muid) {
                clickAction = `loadProjectData($event, '${obj.muid}')`;
            } else {
                clickAction = `toggleLevel($refs.${ref})`;
            }

            let iconHtml;

            if (isJsonFile) {
                iconHtml = `<i class='mdi mdi-file-document-outline'></i>`;
            } else if (obj.children) {
                iconHtml = `<i class='mdi mdi-folder-outline'></i>`;
            } else {
                iconHtml = `<i class='mdi mdi-file-outline'></i>`;
            }

            let buttonHtml = "";
            if (obj.isLastDir) {
                const key = `${obj.author}:${obj.title}`;
                const children = JSON.stringify(obj.children).replace(/"/g, "&quot;");
                if (!this.paths.hasOwnProperty(key)) {
                    this.paths[key] = obj.children.map(child => child.title);
                }
                buttonHtml = `<div class="publish-container"><button class="btn btn--publish" x-on:click="await triggerPullRequest('${key}', $event, '${children}')">Publish ${obj.title}</button><div></div></div>`;
            }
            let html = `<a href="#" 
                            class="navigation-list__item-link"
                            :class="{'has-children':level.children}" 
                            @click.prevent="${clickAction}">
                            ${iconHtml} ${obj.title}
                        </a>`;
            if (buttonHtml) html = `<div class="container-flex">${html} ${buttonHtml} </div>`
            if (!isJsonFile && obj.children) {
                html += `<ul style="display:none;" x-ref="${ref}" class="navigation-list">
                            <template x-for='(level,i) in level.children'>
                                <li class='navigation-list__item' x-html="renderLevel(level,i)"></li>
                            </template>
                        </ul>`;
            }
            return html;
        },
        hasChildren(muid) {
            const parts = muid.split("-");
            let currentLevel = this.levels;

            for (const part of parts) {
                const existingDir = currentLevel.find(dir => dir.title === part);
                if (!existingDir) {
                    return false;
                }
                currentLevel = existingDir.children;
            }

            return currentLevel && currentLevel.length > 0;
        },
        async loadProjectData(event, muid) {
            const nextElement = event.target.nextElementSibling;
            if (!this.hasChildren(muid)) {
                await this.rootPaths(muid);
                await this.updateLastDirStatus(this.levels, muid);
            }
            this.toggleLevel(nextElement);
        },
        showLevel(el) {
            if (el.style.length === 1 && el.style.display === "none") {
                el.removeAttribute("style");
            } else {
                el.style.removeProperty("display");
            }
            setTimeout(() => {
                el.previousElementSibling.querySelector("i.mdi").classList.add("mdi-folder-open-outline");
                el.previousElementSibling.querySelector("i.mdi").classList.remove("mdi-folder-outline");
                el.previousElementSibling.querySelector("i.mdi").parentElement.classList.add("navigation-list--open");
            }, 10);
        },
        hideLevel(el) {
            el.style.display = "none";
            el.previousElementSibling.querySelector("i.mdi").classList.remove("mdi-folder-open-outline");
            el.previousElementSibling.querySelector("i.mdi").classList.add("mdi-folder-outline");
            el.previousElementSibling.querySelector("i.mdi").parentElement.classList.remove("navigation-list--open");

            const refs = el.querySelectorAll("ul[x-ref]");
            for (let i = 0; i < refs.length; ++i) {
                this.hideLevel(refs[i]);
            }
        },
        toggleLevel(el) {
            if (el.style.length && el.style.display === "none") {
                this.showLevel(el);
            } else {
                this.hideLevel(el);
            }
        },
        async updateLastDirStatus(currentLevel, muid) {
            let obj = {};
            for (const item in this.levels) {
                if (item.author === muid) {
                    obj = item;
                }
            }

            for (let i = 0; i < currentLevel.length; i++) {
                let node = currentLevel[i];
                if (node.hasOwnProperty("children")) {
                    if (node.children.some(child => child.hasOwnProperty("children"))) {
                        this.updateLastDirStatus(node.children, muid);
                    } else {
                        if (!node.hasOwnProperty("muid")) {
                            const response = await requestWithTokenRetry(`projects/${muid}/can-edit/`);
                            const { can_edit: canEdit } = await response.json();
                            node.isLastDir = canEdit;
                        }
                    }
                }
            }
        },
        async triggerPullRequest(key, event, childrenString) {
            this.loading = true;
            const children = JSON.parse(childrenString);
            const params = new URLSearchParams();
            const [muid, prefix] = key.split(":");
            params.set("muid", muid);
            params.set("prefix", prefix);
            params.set("_type", "file_path");
            let data = [];
            try {
                const response = await requestWithTokenRetry(`projects/${muid}/?${params.toString()}`);
                if (response.status !== 200) throw new Error();
                const result = await response.json();
                if (result.paths.length !== children.length) throw new Error();
                data = result.paths;
            } catch (error) {
                for (const child of children) {
                    params.set("prefix", child.title.split("_")[0]);
                    const response = await requestWithTokenRetry(`projects/${muid}/?${params.toString()}`);
                    if (response.status !== 200) throw new Error();
                    const result = await response.json();
                    const source = child.title.split("_")[1].replace(".json", "");
                    const filteredPaths = result.paths.filter(path =>
                        path.includes(`/${prefix}/${child.title.replace(source, muid)}`),
                    );
                    data.push(...filteredPaths);
                }
            }
            const dataString = JSON.stringify(data).replace(/"/g, "&quot;");
            const modalHtml = getPullRequestModalHTML(dataString);
            this.loading = false;
            document.body.insertAdjacentHTML("beforeend", modalHtml);
        },
    };
}
