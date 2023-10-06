function fetchTranslation() {
	return {
		translations: [],
		relatedProjects: [],
		async init() {
			const params = new URLSearchParams(window.location.search);
			this.prefix = params.get("prefix");
			const muid = params.get("muid");
			const source = params.get("source");

			await this.findOrCreateObject(muid, this.prefix);
			await this.findOrCreateObject(source, this.prefix, true);

			this.translations.sort((a, b) => (b.isSource ?? 0) - (a.isSource ?? 0));

			const projects = await this.fetchRelatedProjects(this.prefix);
			this.relatedProjects = projects.filter(
				(project) => project !== muid && project !== source,
			);
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
		async findOrCreateObject(key, prefix, source = false) {
			let obj = this.translations.find((item) => key in item);
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
		async fetchData(key, prefix) {
			try {
				const response = await requestWithTokenRetry(
					`projects/${key}/${prefix}/`,
				);
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
				try {
					const muid = translation.muid;
					await this.updateHandler(
						muid,
						{ [uid]: segment },
						event.target.nextElementSibling,
					);
				} catch (error) {
					throw new Error(error);
				}
			}
			const nextLi = event.target.parentElement.nextElementSibling;
			if (nextLi) {
				const nextTextarea = nextLi.querySelector("textarea");
				if (nextTextarea) {
					nextTextarea.focus();
				}
			}
		},
		async updateHandler(muid, data, element) {
			try {
				const response = await requestWithTokenRetry(
					`projects/${muid}/${this.prefix}/`,
					{
						credentials: "include",
						method: "PATCH",
						headers: { "Content-Type": "application/json" },
						body: JSON.stringify(data),
					},
				);
				const { task_id: taskID } = await response.json();
				if (!taskID) {
					throw new Error("Invalid data format from the API");
				}
				await this.pollUpdateStatus(taskID, element);
			} catch (error) {
				throw new Error(error);
			}
		},
		async fetchRelatedProjects(prefix) {
			try {
				const response = await requestWithTokenRetry(
					`projects/?prefix=${prefix}`,
				);
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
			const index = this.translations.findIndex((t) => t.muid === project);
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
		async getUpdateStatus(taskID) {
			try {
				const response = await requestWithTokenRetry(`tasks/${taskID}/`);
				const data = await response.json();
				if (!data.status) {
					throw new Error("Invalid data format from the API");
				}
				return data.status;
			} catch (error) {
				throw new Error(error);
			}
		},
		async pollUpdateStatus(taskID, element) {
			let status = await this.getUpdateStatus(taskID);
			switch (status.toUpperCase()) {
				case "SUCCESS":
					element.classList.remove("loading", "failure");
					element.classList.add("success");
					setTimeout(() => element.classList.remove("success"), 30000);
					break;
				case "FAILURE":
					element.classList.remove("loading", "success");
					element.classList.add("failure");
					break;
				default:
					element.classList.remove("success", "failure");
					element.classList.add("loading");
					setTimeout(() => this.pollUpdateStatus(taskID, element), 750);
			}
		},
	};
}
