let fileTree = function () {
	return {
		levels: [],
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
					const parts = path.split("-").filter((p) => p);

					if (parts.length === 1) {
						currentLevel.push({
							title: parts[0],
							children: [],
							muid: fullProjectPath,
							author: fullProjectPath,
						});
						return;
					}

					let existingDir = currentLevel.find((dir) => dir.title === parts[0]);

					if (!existingDir) {
						existingDir = { title: parts[0], children: [], author: fullProjectPath };
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

				if (!data.root_paths) {
					throw new Error("Invalid data format from the API");
				}

				const paths = data.root_paths.map(
					(path) => `/${muid.replaceAll("-", "/")}${path.replace(/^.*unpublished\/[^\/]+/, "")}`,
				);

				function addOrUpdatePathInStructure(path, currentLevel) {
					const parts = path.split("/").filter((p) => p);

					if (parts.length === 1) {
						let existingItem = currentLevel.find((item) => item.title === parts[0]);
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

					let existingDir = currentLevel.find((dir) => dir.title === parts[0]);

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
				iconHtml = `<i class='mdi mdi-file-document-outline text-neutral-600'></i>`;
			} else if (obj.children) {
				iconHtml = `<i class='mdi mdi-folder-outline text-sky-700'></i>`;
			} else {
				iconHtml = `<i class='mdi mdi-file-outline text-neutral-600'></i>`;
			}

			let html = `<a href="#" 
                            class="flex gap-1 px-5 py-1 my-1 hover:bg-green-50 rounded"
                            :class="{'has-children':level.children}" 
                            @click.prevent="${clickAction}">
                            ${iconHtml} ${obj.title}
                        </a>`;

			if (!isJsonFile && obj.children) {
				html += `<ul style="display:none;" x-ref="${ref}" class="pl-5 transition-all duration-500 opacity-0">
                            <template x-for='(level,i) in level.children'>
                                <li x-html="renderLevel(level,i)"></li>
                            </template>
                        </ul>`;
			}
			return html;
		},
		hasChildren(muid) {
			const parts = muid.split("-");
			let currentLevel = this.levels;

			for (const part of parts) {
				const existingDir = currentLevel.find((dir) => dir.title === part);
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
				el.classList.add("opacity-100");
			}, 10);
		},
		hideLevel(el) {
			el.style.display = "none";
			el.classList.remove("opacity-100");
			el.previousElementSibling.querySelector("i.mdi").classList.remove("mdi-folder-open-outline");
			el.previousElementSibling.querySelector("i.mdi").classList.add("mdi-folder-outline");

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
	};
};
